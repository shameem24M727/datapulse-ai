import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.pipeline import (
    PipelineModel,
    PipelineMetricSnapshotModel,
    PipelineAlertModel,
    PipelineAnomalyModel,
)
from app.schemas.pipeline import (
    PipelineCreateRequest,
    PipelineUpdateRequest,
    PipelineSummarySchema,
    PipelineDetailSchema,
    PipelineMetricSnapshotSchema,
    PipelineAlertSchema,
    StreamRecordIngestRequest,
    StreamIngestResponse,
    SimulatorConfigRequest,
    SimulatorStatusResponse,
)
from app.services.stream_processor import stream_processor
from app.services.stream_simulator import stream_simulator
from app.services.websocket_manager import websocket_manager
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel
from app.core.roles import Permission, UserRole
from app.core.security import decode_access_token
from app.api.deps import (
    get_current_active_user,
    get_current_organization,
    require_permission,
)
from app.core.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger("datapulse.pipelines.endpoint")
router = APIRouter()

MAX_BATCH_SIZE = 500

@router.post("/", response_model=PipelineSummarySchema, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    request: PipelineCreateRequest,
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_CREATE)),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """Creates a new pipeline with a defined schema scoped to caller's organization."""
    pipeline = PipelineModel(
        name=request.name.strip(),
        description=request.description,
        source=request.source,
        destination=request.destination,
        schedule=request.schedule or "Real-time Continuous",
        schema_definition=request.schema_definition.model_dump(),
        status="active",
        organization_id=org.id,
        created_by_user_id=current_user.id,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    # Invalidate pipeline lists and overview metrics
    cache_service.invalidate_pipelines(org.id)

    return pipeline

@router.get("/", response_model=List[PipelineSummarySchema])
def list_pipelines(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (active, stopped, degraded)"),
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """Retrieves all registered data pipelines belonging to caller's organization."""
    cache_key = cache_service.build_key(org.id, "pipelines", f"list:status={status_filter or 'all'}")
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    query = db.query(PipelineModel).filter(PipelineModel.organization_id == org.id)
    if status_filter:
        query = query.filter(PipelineModel.status == status_filter)
    pipelines = query.order_by(PipelineModel.created_at.desc()).all()
    result = [PipelineSummarySchema.model_validate(p).model_dump() for p in pipelines]
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_PIPELINE_LIST)
    return result

@router.get("/{pipeline_id}", response_model=PipelineDetailSchema)
def get_pipeline_detail(
    pipeline_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """Retrieves complete pipeline details scoped to organization. Enforces IDOR protection."""
    cache_key = cache_service.build_key(org.id, "pipelines", pipeline_id, "detail")
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    pipeline = (
        db.query(PipelineModel)
        .filter(PipelineModel.id == pipeline_id, PipelineModel.organization_id == org.id)
        .first()
    )
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found in current organization.",
        )
    result = PipelineDetailSchema.model_validate(pipeline).model_dump()
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_PIPELINE_DETAIL)
    return result

@router.put("/{pipeline_id}", response_model=PipelineSummarySchema)
def update_pipeline(
    pipeline_id: str,
    request: PipelineUpdateRequest,
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """Updates pipeline configuration scoped to organization."""
    pipeline = (
        db.query(PipelineModel)
        .filter(PipelineModel.id == pipeline_id, PipelineModel.organization_id == org.id)
        .first()
    )
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found in current organization.",
        )

    if request.name is not None:
        pipeline.name = request.name.strip()
    if request.description is not None:
        pipeline.description = request.description
    if request.source is not None:
        pipeline.source = request.source
    if request.destination is not None:
        pipeline.destination = request.destination
    if request.status is not None:
        pipeline.status = request.status
    if request.schema_definition is not None:
        pipeline.schema_definition = request.schema_definition.model_dump()

    db.commit()
    db.refresh(pipeline)

    # Invalidate cached pipeline details and lists
    cache_service.invalidate_pipelines(org.id, pipeline_id)

    return pipeline

@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_DELETE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Stops any active simulator and deletes pipeline with cascading records."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    # Stop simulator if running
    if stream_simulator.is_running(pipeline_id):
        stream_simulator.stop_simulator(pipeline_id)

    pipeline_name = pipeline.name
    db.delete(pipeline)
    db.commit()

    # Invalidate pipeline cache
    cache_service.invalidate_pipelines(org.id, pipeline_id)

    return {"message": f"Pipeline '{pipeline_name}' deleted successfully.", "id": pipeline_id}

@router.post("/{pipeline_id}/start", response_model=PipelineSummarySchema)
def start_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Transitions pipeline status to active."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )
    pipeline.status = "active"
    db.commit()
    db.refresh(pipeline)

    # Invalidate pipeline cache
    cache_service.invalidate_pipelines(org.id, pipeline_id)

    websocket_manager.broadcast_sync(
        pipeline.id,
        {
            "type": "status_change",
            "pipeline_id": pipeline.id,
            "status": pipeline.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return pipeline

@router.post("/{pipeline_id}/stop", response_model=PipelineSummarySchema)
async def stop_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Transitions pipeline status to stopped and halts active simulator."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    # Halt simulator if running
    if stream_simulator.is_running(pipeline_id):
        stream_simulator.stop_simulator(pipeline_id)

    pipeline.status = "stopped"
    db.commit()
    db.refresh(pipeline)

    # Invalidate pipeline cache
    cache_service.invalidate_pipelines(org.id, pipeline_id)

    websocket_manager.broadcast_sync(
        pipeline.id,
        {
            "type": "status_change",
            "pipeline_id": pipeline.id,
            "status": pipeline.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return pipeline

@router.post("/{pipeline_id}/ingest", response_model=StreamIngestResponse)
def ingest_stream_records(
    pipeline_id: str,
    payload: StreamRecordIngestRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """
    Ingests single or batch JSON records into a registered pipeline.
    Validates against pipeline schema, detects duplicates & statistical outliers,
    records processing latency, and generates deduplicated alerts if needed.
    """
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    if pipeline.status == "stopped":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline '{pipeline.name}' is currently STOPPED. Start the pipeline before ingesting records.",
        )

    # Normalize records list
    records: List[dict] = []
    if payload.records is not None:
        records.extend(payload.records)
    elif payload.record is not None:
        records.append(payload.record)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload must include either 'record' or 'records'.",
        )

    if not records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Records batch cannot be empty.",
        )

    if len(records) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size ({len(records)}) exceeds maximum allowed limit of {MAX_BATCH_SIZE} records.",
        )

    # Process via StreamProcessingEngine
    result = stream_processor.process_records(db=db, pipeline=pipeline, records=records)

    # Invalidate metrics and alerts cache for this pipeline
    cache_service.invalidate_alerts(org.id, pipeline.id)
    cache_service.delete(cache_service.build_key(org.id, "pipelines", pipeline.id, "metrics"))

    return StreamIngestResponse(
        pipeline_id=pipeline.id,
        status=result["status"],
        records_received=result["records_received"],
        records_accepted=result["records_accepted"],
        records_rejected=result["records_rejected"],
        validation_errors=result.get("validation_errors"),
        anomalies_detected=result.get("anomalies_detected"),
        avg_latency_ms=result["avg_latency_ms"],
    )

# ── Simulator Control Endpoints ───────────────────────────────────────────────

@router.post("/{pipeline_id}/simulator/start", response_model=SimulatorStatusResponse)
async def start_stream_simulator(
    pipeline_id: str,
    config: SimulatorConfigRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Starts a development stream simulator background task."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    if pipeline.status == "stopped":
        pipeline.status = "active"
        db.commit()

    return stream_simulator.start_simulator(pipeline_id, config)

@router.post("/{pipeline_id}/simulator/stop", response_model=SimulatorStatusResponse)
def stop_stream_simulator(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Halts an active stream simulator."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )
    return stream_simulator.stop_simulator(pipeline_id)

@router.get("/{pipeline_id}/simulator/status", response_model=SimulatorStatusResponse)
def get_simulator_status(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_READ)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Retrieves current running status of the stream simulator."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )
    return stream_simulator.get_status(pipeline_id)

# ── Telemetry & Observability Endpoints ───────────────────────────────────────

@router.get("/{pipeline_id}/metrics", response_model=List[PipelineMetricSnapshotSchema])
def get_pipeline_metrics(
    pipeline_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_READ)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Retrieves time-series metric snapshots for the pipeline."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    cache_key = cache_service.build_key(org.id, "pipelines", pipeline_id, f"metrics:limit={limit}")
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    snapshots = (
        db.query(PipelineMetricSnapshotModel)
        .filter(PipelineMetricSnapshotModel.pipeline_id == pipeline_id)
        .order_by(PipelineMetricSnapshotModel.timestamp.desc())
        .limit(limit)
        .all()
    )
    result = [PipelineMetricSnapshotSchema.model_validate(s).model_dump() for s in snapshots]
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_PIPELINE_METRICS)
    return result

@router.get("/{pipeline_id}/alerts", response_model=List[PipelineAlertSchema])
def get_pipeline_alerts(
    pipeline_id: str,
    unresolved_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.ALERT_READ)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Retrieves deduplicated pipeline alerts."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    cache_key = cache_service.build_key(org.id, "pipelines", pipeline_id, f"alerts:unresolved={unresolved_only}")
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    query = db.query(PipelineAlertModel).filter(PipelineAlertModel.pipeline_id == pipeline_id)
    if unresolved_only:
        query = query.filter(PipelineAlertModel.resolved == False)

    alerts = query.order_by(PipelineAlertModel.last_occurred_at.desc()).all()
    result = [PipelineAlertSchema.model_validate(a).model_dump() for a in alerts]
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_PIPELINE_ALERTS)
    return result

# ── Alert Action Endpoints ───────────────────────────────────────────────────

@router.get("/alerts/{alert_id}", response_model=PipelineAlertSchema)
def get_alert_detail(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.ALERT_READ)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Retrieves detailed information for a specific alert."""
    alert = (
        db.query(PipelineAlertModel)
        .join(PipelineModel, PipelineAlertModel.pipeline_id == PipelineModel.id)
        .filter(
            PipelineAlertModel.id == alert_id,
            PipelineModel.organization_id == org.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )
    return alert

@router.post("/alerts/{alert_id}/acknowledge", response_model=PipelineAlertSchema)
def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.ALERT_ACKNOWLEDGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Marks an alert as acknowledged by an operator."""
    alert = (
        db.query(PipelineAlertModel)
        .join(PipelineModel, PipelineAlertModel.pipeline_id == PipelineModel.id)
        .filter(
            PipelineAlertModel.id == alert_id,
            PipelineModel.organization_id == org.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    alert.acknowledged = True
    alert.acknowledged_at = now
    db.commit()
    db.refresh(alert)

    # Invalidate alerts cache for this pipeline and tenant
    cache_service.invalidate_alerts(org.id, alert.pipeline_id)

    # Broadcast alert update over WebSocket
    websocket_manager.broadcast_sync(
        alert.pipeline_id,
        {
            "type": "alert_updated",
            "pipeline_id": alert.pipeline_id,
            "timestamp": now.isoformat(),
            "alert": {
                "id": alert.id,
                "pipeline_id": alert.pipeline_id,
                "severity": alert.severity,
                "alert_type": alert.alert_type,
                "title": alert.title,
                "description": alert.description,
                "dedup_key": alert.dedup_key,
                "occurrence_count": alert.occurrence_count,
                "first_occurred_at": alert.first_occurred_at.isoformat(),
                "last_occurred_at": alert.last_occurred_at.isoformat(),
                "resolved": alert.resolved,
                "acknowledged": alert.acknowledged,
                "evidence": alert.evidence,
            },
        },
    )
    return alert

@router.post("/alerts/{alert_id}/resolve", response_model=PipelineAlertSchema)
def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.ALERT_RESOLVE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Marks an alert as resolved and recalculates pipeline health."""
    alert = (
        db.query(PipelineAlertModel)
        .join(PipelineModel, PipelineAlertModel.pipeline_id == PipelineModel.id)
        .filter(
            PipelineAlertModel.id == alert_id,
            PipelineModel.organization_id == org.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    alert.resolved = True
    alert.resolved_at = now

    pipeline = db.query(PipelineModel).filter(PipelineModel.id == alert.pipeline_id).first()
    if pipeline:
        pipeline.health_score = stream_processor.calculate_pipeline_health(pipeline, db)

    db.commit()
    db.refresh(alert)

    # Invalidate alerts cache for this pipeline and tenant
    cache_service.invalidate_alerts(org.id, alert.pipeline_id)

    # Broadcast alert update over WebSocket
    websocket_manager.broadcast_sync(
        alert.pipeline_id,
        {
            "type": "alert_updated",
            "pipeline_id": alert.pipeline_id,
            "timestamp": now.isoformat(),
            "alert": {
                "id": alert.id,
                "pipeline_id": alert.pipeline_id,
                "severity": alert.severity,
                "alert_type": alert.alert_type,
                "title": alert.title,
                "description": alert.description,
                "dedup_key": alert.dedup_key,
                "occurrence_count": alert.occurrence_count,
                "first_occurred_at": alert.first_occurred_at.isoformat(),
                "last_occurred_at": alert.last_occurred_at.isoformat(),
                "resolved": alert.resolved,
                "acknowledged": alert.acknowledged,
                "evidence": alert.evidence,
            },
        },
    )
    return alert

@router.post("/{pipeline_id}/health-check")
def check_pipeline_health_audit(
    pipeline_id: str,
    max_inactive_seconds: int = Query(600),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission(Permission.PIPELINE_MANAGE)),
    org: OrganizationModel = Depends(get_current_organization),
):
    """Performs an on-demand audit of pipeline health and checks for unexpected inactivity."""
    pipeline = db.query(PipelineModel).filter(
        PipelineModel.id == pipeline_id,
        PipelineModel.organization_id == org.id,
    ).first()
    if not pipeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline with ID '{pipeline_id}' not found.",
        )

    now = datetime.now(timezone.utc)
    stream_processor.check_inactivity_alert(db, pipeline, now, max_inactive_seconds=max_inactive_seconds)
    pipeline.health_score = stream_processor.calculate_pipeline_health(pipeline, db)
    db.commit()

    # Invalidate cached pipeline details
    cache_service.invalidate_pipelines(org.id, pipeline_id)

    return {
        "pipeline_id": pipeline.id,
        "name": pipeline.name,
        "status": pipeline.status,
        "health_score": pipeline.health_score,
        "success_rate": pipeline.success_rate,
        "avg_latency_ms": pipeline.avg_latency_ms,
        "last_ingestion_at": pipeline.last_ingestion_at,
    }

# ── WebSocket Observability Endpoint ──────────────────────────────────────────

@router.websocket("/{pipeline_id}/ws")
async def pipeline_websocket_endpoint(
    websocket: WebSocket,
    pipeline_id: str,
    token: Optional[str] = Query(None),
):
    """
    Real-time WebSocket endpoint for pipeline observability:
    - Verifies token signature, expiry, and tenant membership
    - Verifies pipeline exists and belongs to user's active organization
    - Rejects unauthorized or cross-tenant access with 4001 or 4003
    - Pushes initial state packet upon connection
    - Streams live telemetry updates (throughput, latency, success/failure rate)
    - Pushes real-time anomalies and schema violations
    - Supports heartbeat ping/pong messages
    """
    # 1. Resolve token from query param or authorization header
    auth_token = token
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            auth_token = auth_header[7:].strip()

    if not auth_token:
        await websocket.close(code=4001, reason="Authentication token missing.")
        return

    # 2. Decode and validate JWT
    try:
        payload = decode_access_token(auth_token)
        user_id = payload.get("sub")
        token_org_id = payload.get("org_id")
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token subject.")
            return
    except Exception as exc:
        logger.warning(f"WebSocket auth failed: {exc}")
        await websocket.close(code=4001, reason="Invalid or expired token.")
        return

    # 3. Check DB for user active status and pipeline ownership
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user or not user.is_active:
            await websocket.close(code=4003, reason="User account is inactive or disabled.")
            return

        pipeline = db.query(PipelineModel).filter(PipelineModel.id == pipeline_id).first()
        if not pipeline:
            await websocket.close(code=4004, reason=f"Pipeline '{pipeline_id}' not found.")
            return

        # Tenant verification
        if token_org_id and pipeline.organization_id != token_org_id and user.role != UserRole.ADMIN.value:
            await websocket.close(code=4003, reason="Access denied: Pipeline belongs to another organization.")
            return

        if user.role != UserRole.ADMIN.value:
            membership = (
                db.query(UserOrganizationModel)
                .filter(
                    UserOrganizationModel.user_id == user.id,
                    UserOrganizationModel.organization_id == pipeline.organization_id,
                )
                .first()
            )
            if not membership:
                await websocket.close(code=4003, reason="Access denied: Not a member of pipeline organization.")
                return

        accepted = await websocket_manager.connect(pipeline_id, websocket)
        if not accepted:
            return

        snapshots = (
            db.query(PipelineMetricSnapshotModel)
            .filter(PipelineMetricSnapshotModel.pipeline_id == pipeline_id)
            .order_by(PipelineMetricSnapshotModel.timestamp.desc())
            .limit(10)
            .all()
        )
        anomalies = (
            db.query(PipelineAnomalyModel)
            .filter(PipelineAnomalyModel.pipeline_id == pipeline_id)
            .order_by(PipelineAnomalyModel.detected_at.desc())
            .limit(5)
            .all()
        )
        alerts = (
            db.query(PipelineAlertModel)
            .filter(PipelineAlertModel.pipeline_id == pipeline_id)
            .order_by(PipelineAlertModel.last_occurred_at.desc())
            .limit(10)
            .all()
        )

        initial_state = {
            "type": "initial_state",
            "pipeline_id": pipeline.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            "recent_snapshots": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "throughput_rps": s.throughput_rps,
                    "avg_latency_ms": s.avg_latency_ms,
                    "error_rate": s.error_rate,
                    "records_processed": s.records_processed,
                    "records_failed": s.records_failed,
                    "status": s.status,
                }
                for s in reversed(snapshots)
            ],
            "recent_anomalies": [
                {
                    "id": a.id,
                    "column_name": a.column_name,
                    "anomaly_type": a.anomaly_type,
                    "severity": a.severity,
                    "description": a.description,
                    "detected_at": a.detected_at.isoformat(),
                }
                for a in anomalies
            ],
            "recent_alerts": [
                {
                    "id": al.id,
                    "pipeline_id": al.pipeline_id,
                    "severity": al.severity,
                    "alert_type": al.alert_type,
                    "title": al.title,
                    "description": al.description,
                    "dedup_key": al.dedup_key,
                    "occurrence_count": al.occurrence_count,
                    "first_occurred_at": al.first_occurred_at.isoformat(),
                    "last_occurred_at": al.last_occurred_at.isoformat(),
                    "resolved": al.resolved,
                    "resolved_at": al.resolved_at.isoformat() if al.resolved_at else None,
                    "acknowledged": al.acknowledged,
                    "acknowledged_at": al.acknowledged_at.isoformat() if al.acknowledged_at else None,
                    "evidence": al.evidence,
                }
                for al in alerts
            ],
            "is_simulator_running": stream_simulator.is_running(pipeline_id),
        }
        await websocket.send_text(json.dumps(initial_state, default=str))
    finally:
        db.close()

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        websocket_manager.disconnect(pipeline_id, websocket)
    except Exception as exc:
        logger.debug(f"WebSocket client error on {pipeline_id}: {exc}")
        websocket_manager.disconnect(pipeline_id, websocket)
