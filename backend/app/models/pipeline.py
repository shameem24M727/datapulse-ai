import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship
from app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class PipelineModel(Base):
    __tablename__ = "pipelines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    source = Column(String(255), nullable=False, default="HTTP Stream Ingestion")
    destination = Column(String(255), nullable=False, default="DataPulse Staging Warehouse")
    status = Column(String(50), default="active", nullable=False, index=True)  # active, stopped, degraded, error
    schedule = Column(String(100), default="Real-time Continuous", nullable=False)

    # Schema definition: dict containing fields with name, type, required flags
    schema_definition = Column(JSON, nullable=False)

    # Ingestion & Observability counters
    total_records_ingested = Column(Integer, default=0, nullable=False)
    total_records_processed = Column(Integer, default=0, nullable=False)
    total_records_failed = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=100.0, nullable=False)
    avg_latency_ms = Column(Float, default=0.0, nullable=False)
    current_throughput_rps = Column(Float, default=0.0, nullable=False)
    health_score = Column(Float, default=100.0, nullable=False)

    # Multi-tenancy and Ownership
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, default="org_default_001", index=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    last_ingestion_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    organization = relationship("OrganizationModel", back_populates="pipelines")
    created_by = relationship("UserModel", back_populates="pipelines")
    metric_snapshots = relationship(
        "PipelineMetricSnapshotModel",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="desc(PipelineMetricSnapshotModel.timestamp)",
    )
    alerts = relationship(
        "PipelineAlertModel",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="desc(PipelineAlertModel.created_at)",
    )
    anomalies = relationship(
        "PipelineAnomalyModel",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="desc(PipelineAnomalyModel.detected_at)",
    )

class PipelineMetricSnapshotModel(Base):
    __tablename__ = "pipeline_metric_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pipeline_id = Column(
        String(36),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    records_in_interval = Column(Integer, default=0, nullable=False)
    records_processed = Column(Integer, default=0, nullable=False)
    records_failed = Column(Integer, default=0, nullable=False)
    throughput_rps = Column(Float, default=0.0, nullable=False)
    avg_latency_ms = Column(Float, default=0.0, nullable=False)
    error_rate = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="active", nullable=False)

    pipeline = relationship("PipelineModel", back_populates="metric_snapshots")

class PipelineAlertModel(Base):
    __tablename__ = "pipeline_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pipeline_id = Column(
        String(36),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    severity = Column(String(20), nullable=False, index=True)  # info, warning, error, critical
    alert_type = Column(
        String(50),
        nullable=False,
        index=True,
    )  # pipeline_failure, repeated_schema_violations, high_failure_rate, anomaly_spike, inactivity
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Deduplication fingerprint to coalesce repeated alerts and prevent alert storms
    dedup_key = Column(String(255), nullable=False, index=True)
    occurrence_count = Column(Integer, default=1, nullable=False)
    first_occurred_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_occurred_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    evidence = Column(JSON, nullable=True)  # Metric and event evidence dict

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pipeline = relationship("PipelineModel", back_populates="alerts")

class PipelineAnomalyModel(Base):
    __tablename__ = "pipeline_anomalies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pipeline_id = Column(
        String(36),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    column_name = Column(String(255), nullable=False)
    anomaly_type = Column(
        String(50),
        nullable=False,
    )  # zscore_outlier, null_spike, schema_violation, type_mismatch
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)

    metric_value = Column(Float, nullable=True)
    expected_range = Column(JSON, nullable=True)
    record_sample = Column(JSON, nullable=True)

    detected_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    pipeline = relationship("PipelineModel", back_populates="anomalies")
