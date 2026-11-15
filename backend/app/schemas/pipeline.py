from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

class SchemaFieldDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Column or attribute name")
    type: Literal["string", "integer", "float", "boolean", "datetime", "json"] = Field(
        ..., description="Expected primitive data type"
    )
    required: bool = Field(False, description="Whether null/missing values are prohibited")
    description: Optional[str] = Field(None, max_length=255, description="Field description")

class PipelineSchemaDefinition(BaseModel):
    fields: List[SchemaFieldDefinition] = Field(..., min_items=1, description="List of expected schema fields")
    strict: bool = Field(False, description="If True, records with undeclared fields are rejected")

class PipelineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Pipeline human-readable name")
    description: Optional[str] = Field(None, max_length=1000, description="Pipeline purpose and details")
    source: str = Field("HTTP Stream Ingestion", max_length=255, description="Stream source identifier")
    destination: str = Field("DataPulse Staging Warehouse", max_length=255, description="Target destination")
    schedule: Optional[str] = Field("Real-time Continuous", max_length=100, description="Ingestion cadence")
    schema_definition: PipelineSchemaDefinition

class PipelineUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    source: Optional[str] = Field(None, max_length=255)
    destination: Optional[str] = Field(None, max_length=255)
    status: Optional[Literal["active", "stopped", "degraded", "error"]] = None
    schema_definition: Optional[PipelineSchemaDefinition] = None

class PipelineMetricSnapshotSchema(BaseModel):
    id: str
    pipeline_id: str
    timestamp: datetime
    records_in_interval: int
    records_processed: int
    records_failed: int
    throughput_rps: float
    avg_latency_ms: float
    error_rate: float
    status: str

    class Config:
        from_attributes = True

class PipelineAlertSchema(BaseModel):
    id: str
    pipeline_id: str
    severity: Literal["info", "warning", "error", "critical", "low", "medium", "high"]
    alert_type: str
    title: str
    description: str
    dedup_key: str
    occurrence_count: int
    first_occurred_at: datetime
    last_occurred_at: datetime
    resolved: bool
    resolved_at: Optional[datetime] = None
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    evidence: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PipelineAnomalySchema(BaseModel):
    id: str
    pipeline_id: str
    column_name: str
    anomaly_type: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    metric_value: Optional[float] = None
    expected_range: Optional[Dict[str, Any]] = None
    record_sample: Optional[Dict[str, Any]] = None
    detected_at: datetime

    class Config:
        from_attributes = True

class PipelineSummarySchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    source: str
    destination: str
    status: str
    schedule: str
    total_records_ingested: int
    total_records_processed: int
    total_records_failed: int
    success_rate: float
    avg_latency_ms: float
    current_throughput_rps: float
    health_score: float = 100.0
    organization_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    last_ingestion_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PipelineDetailSchema(PipelineSummarySchema):
    schema_definition: Dict[str, Any]
    metric_snapshots: List[PipelineMetricSnapshotSchema] = []
    alerts: List[PipelineAlertSchema] = []
    anomalies: List[PipelineAnomalySchema] = []

    class Config:
        from_attributes = True

class StreamRecordIngestRequest(BaseModel):
    # Allows ingesting single record or batch of records
    record: Optional[Dict[str, Any]] = None
    records: Optional[List[Dict[str, Any]]] = None

class StreamIngestResponse(BaseModel):
    pipeline_id: str
    status: str
    records_received: int
    records_accepted: int
    records_rejected: int
    validation_errors: Optional[List[Dict[str, Any]]] = None
    anomalies_detected: Optional[List[Dict[str, Any]]] = None
    avg_latency_ms: float

class SimulatorConfigRequest(BaseModel):
    rate_records_per_sec: float = Field(5.0, ge=0.5, le=50.0, description="Records generated per second")
    batch_size: int = Field(1, ge=1, le=20, description="Records emitted per tick")
    anomaly_rate: float = Field(0.05, ge=0.0, le=0.5, description="Probability of injecting statistical outliers")
    schema_violation_rate: float = Field(0.02, ge=0.0, le=0.5, description="Probability of injecting malformed fields")
    duplicate_rate: float = Field(0.02, ge=0.0, le=0.5, description="Probability of repeating past record")

class SimulatorStatusResponse(BaseModel):
    pipeline_id: str
    is_running: bool
    rate_records_per_sec: float
    batch_size: int
    records_generated: int
    started_at: Optional[datetime] = None
    is_simulated: bool = True
