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

class DatasetModel(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # csv, xlsx, xls
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=True)

    row_count = Column(Integer, default=0)
    column_count = Column(Integer, default=0)
    status = Column(String(50), default="healthy")  # healthy, warning, critical, processing
    quality_score = Column(Float, default=100.0)

    # Multi-tenancy and Ownership
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, default="org_default_001", index=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = relationship("OrganizationModel", back_populates="datasets")
    created_by = relationship("UserModel", back_populates="datasets")
    column_profiles = relationship("ColumnProfileModel", back_populates="dataset", cascade="all, delete-orphan")
    quality_report = relationship("QualityReportModel", back_populates="dataset", uselist=False, cascade="all, delete-orphan")
    anomalies = relationship("AnomalyModel", back_populates="dataset", cascade="all, delete-orphan")
    copilot_messages = relationship("CopilotMessageModel", back_populates="dataset", cascade="all, delete-orphan", order_by="CopilotMessageModel.created_at")

class ColumnProfileModel(Base):
    __tablename__ = "column_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)

    column_name = Column(String(255), nullable=False)
    data_type = Column(String(50), nullable=False)
    total_count = Column(Integer, nullable=False, default=0)
    null_count = Column(Integer, nullable=False, default=0)
    null_percentage = Column(Float, nullable=False, default=0.0)
    unique_count = Column(Integer, nullable=False, default=0)
    is_numeric = Column(Boolean, default=False)

    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    mean_value = Column(Float, nullable=True)
    median_value = Column(Float, nullable=True)
    std_value = Column(Float, nullable=True)

    top_values = Column(JSON, nullable=True)  # List of {value, count, percentage}

    dataset = relationship("DatasetModel", back_populates="column_profiles")

class QualityReportModel(Base):
    __tablename__ = "quality_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    overall_score = Column(Float, nullable=False)
    completeness_score = Column(Float, nullable=False)
    uniqueness_score = Column(Float, nullable=False)
    validity_score = Column(Float, nullable=False)
    consistency_score = Column(Float, nullable=False)

    duplicate_rows_count = Column(Integer, default=0)
    duplicate_rows_percentage = Column(Float, default=0.0)
    total_cells = Column(Integer, default=0)
    null_cells = Column(Integer, default=0)

    deductions_evidence = Column(JSON, nullable=True)  # Structured evidence of score penalties
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    dataset = relationship("DatasetModel", back_populates="quality_report")

class AnomalyModel(Base):
    __tablename__ = "anomalies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)

    column_name = Column(String(255), nullable=False)
    anomaly_type = Column(String(50), nullable=False)  # zscore_outlier, iqr_outlier, null_spike
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    affected_rows = Column(Integer, default=0)
    description = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)  # Statistics and example values

    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    dataset = relationship("DatasetModel", back_populates="anomalies")

class CopilotMessageModel(Base):
    __tablename__ = "copilot_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)

    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    recommendations = Column(JSON, nullable=True)  # list of action item strings
    metrics = Column(JSON, nullable=True)  # list of {label, value, status}
    model_used = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    dataset = relationship("DatasetModel", back_populates="copilot_messages")
