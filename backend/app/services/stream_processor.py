import time
import json
import hashlib
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.pipeline import (
    PipelineModel,
    PipelineMetricSnapshotModel,
    PipelineAlertModel,
    PipelineAnomalyModel,
)
from app.services.stream_validator import validate_stream_record, RecordValidationResult

logger = logging.getLogger("datapulse.stream.processor")

class PipelineStreamState:
    """
    In-memory bounded state for a single pipeline.
    Ensures bounded memory consumption regardless of stream volume.
    """
    def __init__(self, max_history: int = 1000):
        self.recent_hashes: deque = deque(maxlen=max_history)
        self.recent_hashes_set: set = set()
        # Per-column numeric values deque for sliding Z-score calculations
        self.numeric_windows: Dict[str, deque] = {}
        # Cooldown timestamps for alert deduplication: dedup_key -> datetime
        self.alert_cooldowns: Dict[str, datetime] = {}
        # Ingestion metrics for throughput calculations
        self.window_records: int = 0
        self.window_start: float = time.time()

    def add_hash(self, h: str) -> bool:
        """Returns True if duplicate, False if unique."""
        is_dup = h in self.recent_hashes_set
        if len(self.recent_hashes) == self.recent_hashes.maxlen:
            oldest = self.recent_hashes.popleft()
            self.recent_hashes_set.discard(oldest)
        self.recent_hashes.append(h)
        self.recent_hashes_set.add(h)
        return is_dup

    def add_numeric_sample(self, column: str, value: float, max_len: int = 200):
        if column not in self.numeric_windows:
            self.numeric_windows[column] = deque(maxlen=max_len)
        self.numeric_windows[column].append(value)

    def get_numeric_stats(self, column: str) -> Optional[Tuple[float, float, int]]:
        """Returns (mean, std, count) if sufficient samples exist."""
        window = self.numeric_windows.get(column)
        if not window or len(window) < 10:
            return None
        n = len(window)
        mean = sum(window) / n
        variance = sum((x - mean) ** 2 for x in window) / (n - 1)
        std = variance ** 0.5
        return (mean, std, n)

class StreamProcessingEngine:
    def __init__(self):
        self._states: Dict[str, PipelineStreamState] = {}

    def _get_or_create_state(self, pipeline_id: str) -> PipelineStreamState:
        if pipeline_id not in self._states:
            self._states[pipeline_id] = PipelineStreamState()
        return self._states[pipeline_id]

    def _hash_record(self, record: Dict[str, Any]) -> str:
        # Strip transient simulator/metadata fields for pure content fingerprinting
        filtered = {k: v for k, v in record.items() if not k.startswith("_") and k not in {"is_simulated", "simulator_timestamp"}}
        canonical = json.dumps(filtered, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def process_records(
        self,
        db: Session,
        pipeline: PipelineModel,
        records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Processes an incoming batch of JSON stream records:
        - Validates against pipeline schema definition
        - Detects duplicates using sliding memory buffer
        - Detects numerical 3-sigma outliers using sliding window
        - Updates pipeline counters & records metric snapshots
        - Generates deduplicated alerts if error/anomaly rates spike
        """
        start_time = time.perf_counter()
        state = self._get_or_create_state(pipeline.id)
        now_utc = datetime.now(timezone.utc)

        schema_def = pipeline.schema_definition or {}
        numeric_fields = {
            f["name"]: f["type"]
            for f in schema_def.get("fields", [])
            if f.get("type") in {"integer", "float"}
        }

        accepted_count = 0
        rejected_count = 0
        validation_errors: List[Dict[str, Any]] = []
        anomalies_detected: List[Dict[str, Any]] = []

        new_anomalies_to_persist: List[PipelineAnomalyModel] = []

        for record in records:
            # 1. Schema Validation
            val_result: RecordValidationResult = validate_stream_record(record, schema_def)

            if not val_result.is_valid:
                rejected_count += 1
                for err in val_result.errors:
                    validation_errors.append({
                        "record_sample": record,
                        "error": err,
                    })
                continue

            # 2. Duplicate Detection
            h = self._hash_record(record)
            is_duplicate = state.add_hash(h)
            if is_duplicate:
                # Flag duplicate as data-quality warning
                anom = PipelineAnomalyModel(
                    pipeline_id=pipeline.id,
                    column_name="_record",
                    anomaly_type="duplicate_record",
                    severity="low",
                    description="Duplicate stream record detected within sliding memory window.",
                    record_sample=record,
                    detected_at=now_utc,
                )
                new_anomalies_to_persist.append(anom)
                anomalies_detected.append({
                    "column": "_record",
                    "type": "duplicate_record",
                    "severity": "low",
                    "description": "Duplicate stream record detected within sliding window.",
                })

            # 3. Numeric Sliding-Window Anomaly Detection
            for num_col in numeric_fields.keys():
                val = record.get(num_col)
                if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                    val_float = float(val)
                    stats = state.get_numeric_stats(num_col)
                    if stats:
                        mean, std, count = stats
                        if std > 0:
                            z_score = abs(val_float - mean) / std
                            if z_score > 3.0:
                                severity = "critical" if z_score > 5.0 else "high" if z_score > 4.0 else "medium"
                                anom = PipelineAnomalyModel(
                                    pipeline_id=pipeline.id,
                                    column_name=num_col,
                                    anomaly_type="zscore_outlier",
                                    severity=severity,
                                    description=(
                                        f"Numeric outlier in `{num_col}`: value {val_float:.2f} "
                                        f"exceeded 3σ fence (z-score: {z_score:.2f}σ, baseline: {mean:.2f} ± {std:.2f})."
                                    ),
                                    metric_value=val_float,
                                    expected_range={"mean": round(mean, 2), "std": round(std, 2), "z_score": round(z_score, 2)},
                                    record_sample=record,
                                    detected_at=now_utc,
                                )
                                new_anomalies_to_persist.append(anom)
                                anomalies_detected.append({
                                    "column": num_col,
                                    "type": "zscore_outlier",
                                    "severity": severity,
                                    "description": anom.description,
                                })

                    # Feed sliding window after checking outlier against existing baseline
                    state.add_numeric_sample(num_col, val_float)

            accepted_count += 1

        # Calculate processing duration
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 4. Update Pipeline Aggregates
        pipeline.total_records_ingested += len(records)
        pipeline.total_records_processed += accepted_count
        pipeline.total_records_failed += rejected_count

        if pipeline.total_records_ingested > 0:
            pipeline.success_rate = round(
                (pipeline.total_records_processed / pipeline.total_records_ingested) * 100.0, 2
            )

        # Smooth latency with exponential moving average
        if pipeline.avg_latency_ms == 0.0:
            pipeline.avg_latency_ms = round(latency_ms, 2)
        else:
            pipeline.avg_latency_ms = round((pipeline.avg_latency_ms * 0.7) + (latency_ms * 0.3), 2)

        # Estimate current throughput (records/sec)
        time_since_window = time.time() - state.window_start
        state.window_records += len(records)
        if time_since_window >= 1.0:
            pipeline.current_throughput_rps = round(state.window_records / time_since_window, 1)
            state.window_records = 0
            state.window_start = time.time()

        pipeline.last_ingestion_at = now_utc

        # Adjust status if failure rate in current batch is excessive
        batch_failure_rate = (rejected_count / len(records)) if records else 0.0
        if batch_failure_rate >= 0.25 and pipeline.status == "active":
            pipeline.status = "degraded"
        elif batch_failure_rate < 0.10 and pipeline.status == "degraded":
            pipeline.status = "active"

        # 5. Persist anomalies
        for a in new_anomalies_to_persist:
            db.add(a)

        # 6. Periodic Metric Snapshot
        error_rate = round(batch_failure_rate * 100.0, 2)
        snapshot = PipelineMetricSnapshotModel(
            pipeline_id=pipeline.id,
            timestamp=now_utc,
            records_in_interval=len(records),
            records_processed=accepted_count,
            records_failed=rejected_count,
            throughput_rps=pipeline.current_throughput_rps,
            avg_latency_ms=round(latency_ms, 2),
            error_rate=error_rate,
            status=pipeline.status,
        )
        db.add(snapshot)

        # 7. Deduplicated Alerts Trigger
        self._check_and_emit_alerts(
            db=db,
            pipeline=pipeline,
            state=state,
            total_records=len(records),
            failed_records=rejected_count,
            anomaly_count=len(anomalies_detected),
            validation_errors=validation_errors,
            anomalies=anomalies_detected,
            now=now_utc,
        )

        # 8. Calculate Holistic Pipeline Health Score (0-100)
        pipeline.health_score = self.calculate_pipeline_health(pipeline, db)

        db.commit()

        # 9. Real-time Telemetry Broadcast via WebSocket
        try:
            from app.services.websocket_manager import websocket_manager
            telemetry_packet = {
                "type": "telemetry_update",
                "pipeline_id": pipeline.id,
                "timestamp": now_utc.isoformat(),
                "pipeline": {
                    "id": pipeline.id,
                    "name": pipeline.name,
                    "status": pipeline.status,
                    "health_score": pipeline.health_score,
                    "total_records_ingested": pipeline.total_records_ingested,
                    "total_records_processed": pipeline.total_records_processed,
                    "total_records_failed": pipeline.total_records_failed,
                    "success_rate": pipeline.success_rate,
                    "current_throughput_rps": pipeline.current_throughput_rps,
                    "avg_latency_ms": pipeline.avg_latency_ms,
                    "last_ingestion_at": pipeline.last_ingestion_at.isoformat() if pipeline.last_ingestion_at else None,
                },
                "batch_summary": {
                    "records_received": len(records),
                    "records_accepted": accepted_count,
                    "records_rejected": rejected_count,
                    "latency_ms": round(latency_ms, 2),
                },
                "recent_anomalies": anomalies_detected[:5],
                "recent_violations": validation_errors[:5],
                "latest_snapshot": {
                    "timestamp": now_utc.isoformat(),
                    "throughput_rps": pipeline.current_throughput_rps,
                    "avg_latency_ms": round(latency_ms, 2),
                    "error_rate": error_rate,
                    "records_processed": accepted_count,
                    "records_failed": rejected_count,
                    "status": pipeline.status,
                },
            }
            websocket_manager.broadcast_sync(pipeline.id, telemetry_packet)
        except Exception as e:
            logger.debug(f"Telemetry broadcast notice for {pipeline.id}: {e}")

        return {
            "pipeline_id": pipeline.id,
            "status": pipeline.status,
            "records_received": len(records),
            "records_accepted": accepted_count,
            "records_rejected": rejected_count,
            "validation_errors": validation_errors[:10],  # Return top errors to avoid giant responses
            "anomalies_detected": anomalies_detected[:10],
            "avg_latency_ms": round(latency_ms, 2),
        }

    def calculate_pipeline_health(self, pipeline: PipelineModel, db: Session) -> float:
        """
        Calculates an explainable multi-factor pipeline health score (0.0 to 100.0).
        Evaluates success rate, active unresolved alerts, and processing latency.
        """
        if pipeline.status == "stopped":
            return 0.0

        score = 100.0

        # Factor 1: Success rate impact (up to -40 pts)
        if pipeline.total_records_ingested > 0:
            failure_pct = 100.0 - pipeline.success_rate
            score -= min(40.0, failure_pct * 1.5)

        # Factor 2: Active Unresolved Alerts (critical -20, error -10, warning -5)
        unresolved_alerts = (
            db.query(PipelineAlertModel)
            .filter(
                PipelineAlertModel.pipeline_id == pipeline.id,
                PipelineAlertModel.resolved == False,
            )
            .all()
        )
        for alert in unresolved_alerts:
            if alert.severity == "critical":
                score -= 20.0
            elif alert.severity == "error":
                score -= 10.0
            elif alert.severity == "warning":
                score -= 5.0

        # Factor 3: Processing Latency penalty (>50ms -5, >200ms -15)
        if pipeline.avg_latency_ms > 200.0:
            score -= 15.0
        elif pipeline.avg_latency_ms > 50.0:
            score -= 5.0

        return round(max(0.0, min(100.0, score)), 1)

    def _check_and_emit_alerts(
        self,
        db: Session,
        pipeline: PipelineModel,
        state: PipelineStreamState,
        total_records: int,
        failed_records: int,
        anomaly_count: int,
        validation_errors: List[Dict[str, Any]],
        anomalies: List[Dict[str, Any]],
        now: datetime,
    ):
        """Generates deduplicated alerts with evidence and a 60-second cooldown window."""
        cooldown_seconds = 60
        cooldown_delta = timedelta(seconds=cooldown_seconds)

        # Condition A: High processing failure rate (> 20%)
        if total_records > 0 and (failed_records / total_records) >= 0.20:
            dedup_key = f"{pipeline.id}:high_failure_rate"
            failure_pct = (failed_records / total_records) * 100
            self._upsert_alert(
                db=db,
                pipeline_id=pipeline.id,
                severity="critical" if failure_pct >= 50.0 else "error",
                alert_type="high_failure_rate",
                title=f"High failure rate on {pipeline.name}",
                description=f"Batch experienced {failed_records} failed records out of {total_records} ({failure_pct:.1f}% failure rate).",
                dedup_key=dedup_key,
                evidence={
                    "total_records": total_records,
                    "failed_records": failed_records,
                    "failure_rate": round(failure_pct, 2),
                },
                now=now,
                cooldown_delta=cooldown_delta,
            )

        # Condition B: Repeated schema violations (>= 3 in batch)
        if failed_records >= 3:
            dedup_key = f"{pipeline.id}:repeated_schema_violations"
            self._upsert_alert(
                db=db,
                pipeline_id=pipeline.id,
                severity="error" if failed_records >= 5 else "warning",
                alert_type="repeated_schema_violations",
                title=f"Repeated schema violations on {pipeline.name}",
                description=f"Received {failed_records} schema violation events in recent stream batch.",
                dedup_key=dedup_key,
                evidence={
                    "violation_count": failed_records,
                    "sample_errors": [v.get("error", {}) for v in validation_errors[:3]],
                },
                now=now,
                cooldown_delta=cooldown_delta,
            )

        # Condition C: Anomaly Spike (>= 2 in batch)
        if anomaly_count >= 2:
            dedup_key = f"{pipeline.id}:anomaly_spike"
            self._upsert_alert(
                db=db,
                pipeline_id=pipeline.id,
                severity="error" if any(a.get("severity") in {"critical", "high"} for a in anomalies) else "warning",
                alert_type="anomaly_spike",
                title=f"Statistical anomaly spike on {pipeline.name}",
                description=f"Detected {anomaly_count} numerical outlier incidents exceeding 3σ variance boundaries.",
                dedup_key=dedup_key,
                evidence={
                    "anomaly_count": anomaly_count,
                    "anomalies": anomalies[:3],
                },
                now=now,
                cooldown_delta=cooldown_delta,
            )

    def check_inactivity_alert(
        self,
        db: Session,
        pipeline: PipelineModel,
        now: datetime,
        max_inactive_seconds: int = 600,
    ):
        """Checks for unexpected stream inactivity when pipeline is active."""
        if pipeline.status != "active" or not pipeline.last_ingestion_at:
            return

        last_utc = pipeline.last_ingestion_at.replace(tzinfo=timezone.utc)
        inactive_seconds = (now - last_utc).total_seconds()

        if inactive_seconds > max_inactive_seconds:
            dedup_key = f"{pipeline.id}:inactivity"
            self._upsert_alert(
                db=db,
                pipeline_id=pipeline.id,
                severity="warning",
                alert_type="inactivity",
                title=f"Unexpected inactivity on {pipeline.name}",
                description=f"Active stream has not ingested any events for {int(inactive_seconds)} seconds (threshold: {max_inactive_seconds}s).",
                dedup_key=dedup_key,
                evidence={
                    "last_ingestion_at": last_utc.isoformat(),
                    "inactive_seconds": int(inactive_seconds),
                    "threshold_seconds": max_inactive_seconds,
                },
                now=now,
                cooldown_delta=timedelta(seconds=120),
            )

    def _upsert_alert(
        self,
        db: Session,
        pipeline_id: str,
        severity: str,
        alert_type: str,
        title: str,
        description: str,
        dedup_key: str,
        evidence: Optional[Dict[str, Any]],
        now: datetime,
        cooldown_delta: timedelta,
    ):
        """Deduplicates alerts within cooldown period and broadcasts notifications."""
        existing = (
            db.query(PipelineAlertModel)
            .filter(
                PipelineAlertModel.pipeline_id == pipeline_id,
                PipelineAlertModel.dedup_key == dedup_key,
                PipelineAlertModel.resolved == False,
            )
            .order_by(PipelineAlertModel.last_occurred_at.desc())
            .first()
        )

        alert_to_broadcast = None
        event_type = "alert_created"

        if existing and (now - existing.last_occurred_at.replace(tzinfo=timezone.utc)) < cooldown_delta:
            existing.occurrence_count += 1
            existing.last_occurred_at = now
            existing.description = description
            if evidence:
                existing.evidence = evidence
            alert_to_broadcast = existing
            event_type = "alert_updated"
        else:
            alert = PipelineAlertModel(
                pipeline_id=pipeline_id,
                severity=severity,
                alert_type=alert_type,
                title=title,
                description=description,
                dedup_key=dedup_key,
                evidence=evidence,
                occurrence_count=1,
                first_occurred_at=now,
                last_occurred_at=now,
                resolved=False,
                acknowledged=False,
                created_at=now,
            )
            db.add(alert)
            alert_to_broadcast = alert

        db.flush()

        # Real-time WebSocket Alert Broadcast
        try:
            from app.services.websocket_manager import websocket_manager
            websocket_manager.broadcast_sync(
                pipeline_id,
                {
                    "type": event_type,
                    "pipeline_id": pipeline_id,
                    "timestamp": now.isoformat(),
                    "alert": {
                        "id": alert_to_broadcast.id,
                        "pipeline_id": pipeline_id,
                        "severity": alert_to_broadcast.severity,
                        "alert_type": alert_to_broadcast.alert_type,
                        "title": alert_to_broadcast.title,
                        "description": alert_to_broadcast.description,
                        "dedup_key": alert_to_broadcast.dedup_key,
                        "occurrence_count": alert_to_broadcast.occurrence_count,
                        "first_occurred_at": alert_to_broadcast.first_occurred_at.isoformat(),
                        "last_occurred_at": alert_to_broadcast.last_occurred_at.isoformat(),
                        "resolved": alert_to_broadcast.resolved,
                        "acknowledged": alert_to_broadcast.acknowledged,
                        "evidence": alert_to_broadcast.evidence,
                    },
                },
            )
        except Exception as e:
            logger.debug(f"Alert broadcast notice: {e}")

stream_processor = StreamProcessingEngine()
