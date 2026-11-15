import time
import logging
import random
import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.db.session import SessionLocal
from app.models.pipeline import PipelineModel
from app.schemas.pipeline import SimulatorConfigRequest, SimulatorStatusResponse
from app.services.stream_processor import stream_processor

logger = logging.getLogger("datapulse.stream.simulator")

class StreamSimulatorService:
    def __init__(self):
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._configs: Dict[str, SimulatorConfigRequest] = {}
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._last_records: Dict[str, Dict[str, Any]] = {}

    def is_running(self, pipeline_id: str) -> bool:
        thread = self._threads.get(pipeline_id)
        return bool(thread and thread.is_alive())

    def get_status(self, pipeline_id: str) -> SimulatorStatusResponse:
        running = self.is_running(pipeline_id)
        stats = self._stats.get(pipeline_id, {})
        cfg = self._configs.get(pipeline_id, SimulatorConfigRequest())

        return SimulatorStatusResponse(
            pipeline_id=pipeline_id,
            is_running=running,
            rate_records_per_sec=cfg.rate_records_per_sec,
            batch_size=cfg.batch_size,
            records_generated=stats.get("records_generated", 0),
            started_at=stats.get("started_at"),
            is_simulated=True,
        )

    def start_simulator(
        self,
        pipeline_id: str,
        config: SimulatorConfigRequest,
    ) -> SimulatorStatusResponse:
        if self.is_running(pipeline_id):
            self.stop_simulator(pipeline_id)

        self._configs[pipeline_id] = config
        self._stats[pipeline_id] = {
            "records_generated": 0,
            "started_at": datetime.now(timezone.utc),
        }
        stop_event = threading.Event()
        self._stop_events[pipeline_id] = stop_event

        thread = threading.Thread(
            target=self._run_simulation_thread,
            args=(pipeline_id, config, stop_event),
            name=f"DataPulseSimulator-{pipeline_id[:8]}",
            daemon=True,
        )
        self._threads[pipeline_id] = thread
        thread.start()

        logger.info(
            f"Simulator started for pipeline {pipeline_id} at {config.rate_records_per_sec} records/sec"
        )
        return self.get_status(pipeline_id)

    def stop_simulator(self, pipeline_id: str) -> SimulatorStatusResponse:
        stop_event = self._stop_events.get(pipeline_id)
        if stop_event:
            stop_event.set()

        thread = self._threads.get(pipeline_id)
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
            logger.info(f"Simulator stopped for pipeline {pipeline_id}")

        self._threads.pop(pipeline_id, None)
        self._stop_events.pop(pipeline_id, None)
        return self.get_status(pipeline_id)

    def _run_simulation_thread(
        self,
        pipeline_id: str,
        config: SimulatorConfigRequest,
        stop_event: threading.Event,
    ):
        interval = max(0.02, float(config.batch_size) / float(config.rate_records_per_sec))

        while not stop_event.is_set():
            try:
                # Wait for interval or stop signal
                if stop_event.wait(interval):
                    break

                db = SessionLocal()
                try:
                    pipeline = (
                        db.query(PipelineModel)
                        .filter(PipelineModel.id == pipeline_id)
                        .first()
                    )
                    if not pipeline or pipeline.status == "stopped":
                        logger.info(f"Stopping simulator: pipeline {pipeline_id} is stopped or removed.")
                        break

                    schema_def = pipeline.schema_definition or {}
                    fields = schema_def.get("fields", [])

                    batch = []
                    for _ in range(config.batch_size):
                        record = self._generate_simulated_record(fields, config, pipeline_id)
                        batch.append(record)
                        self._last_records[pipeline_id] = record

                    # Ingest generated batch via processing engine
                    stream_processor.process_records(db, pipeline, batch)

                    self._stats[pipeline_id]["records_generated"] += len(batch)
                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Simulator thread error for {pipeline_id}: {e}")
                if stop_event.wait(1.0):
                    break

    def _generate_simulated_record(
        self,
        fields: list,
        config: SimulatorConfigRequest,
        pipeline_id: str,
    ) -> Dict[str, Any]:
        """Generates realistic synthetic record based on schema."""
        # 1. Duplicate injection
        if (
            random.random() < config.duplicate_rate
            and pipeline_id in self._last_records
        ):
            dup = dict(self._last_records[pipeline_id])
            dup["simulator_timestamp"] = datetime.now(timezone.utc).isoformat()
            return dup

        record: Dict[str, Any] = {
            "is_simulated": True,
            "simulator_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        should_inject_anomaly = random.random() < config.anomaly_rate
        should_inject_schema_error = random.random() < config.schema_violation_rate

        for f in fields:
            name = f["name"]
            ftype = f.get("type", "string")
            required = f.get("required", False)

            # Schema violation injection: omit required field or inject invalid type
            if should_inject_schema_error and required and random.random() < 0.5:
                # Omit field completely
                continue
            elif should_inject_schema_error and random.random() < 0.3:
                # Type corruption
                record[name] = {"invalid_nested_type": True} if ftype != "json" else "not_a_json_dict"
                continue

            # Field generation by type
            if ftype == "string":
                if "id" in name.lower() or "uuid" in name.lower():
                    record[name] = str(uuid.uuid4())[:8]
                elif "email" in name.lower():
                    record[name] = f"user_{random.randint(100, 999)}@example.com"
                elif "status" in name.lower():
                    record[name] = random.choice(["active", "pending", "completed"])
                elif "currency" in name.lower():
                    record[name] = random.choice(["USD", "EUR", "GBP"])
                else:
                    record[name] = f"sample_{name}_{random.randint(10, 99)}"

            elif ftype in {"integer", "float"}:
                # Baseline distribution
                base = (
                    random.uniform(10.0, 100.0)
                    if "amount" in name.lower() or "price" in name.lower()
                    else random.uniform(18.0, 75.0)
                    if "age" in name.lower()
                    else random.uniform(20.0, 30.0)
                )

                # Anomaly injection: 3-sigma extreme outlier
                if should_inject_anomaly:
                    base = base * random.choice([8.0, 15.0, -5.0])

                record[name] = int(round(base)) if ftype == "integer" else round(base, 2)

            elif ftype == "boolean":
                record[name] = random.choice([True, False])

            elif ftype == "datetime":
                record[name] = datetime.now(timezone.utc).isoformat()

            elif ftype == "json":
                record[name] = {"event": "click", "code": random.randint(100, 500)}

        return record

stream_simulator = StreamSimulatorService()
