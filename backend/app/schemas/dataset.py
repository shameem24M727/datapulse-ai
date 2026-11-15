from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class ColumnProfileSchema(BaseModel):
    id: str
    column_name: str
    data_type: str
    total_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    is_numeric: bool
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    median_value: Optional[float] = None
    std_value: Optional[float] = None
    top_values: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True

class QualityReportSchema(BaseModel):
    id: str
    overall_score: float
    completeness_score: float
    uniqueness_score: float
    validity_score: float
    consistency_score: float
    duplicate_rows_count: int
    duplicate_rows_percentage: float
    total_cells: int
    null_cells: int
    deductions_evidence: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AnomalySchema(BaseModel):
    id: str
    column_name: str
    anomaly_type: str
    severity: str
    affected_rows: int
    description: str
    details: Optional[Dict[str, Any]] = None
    detected_at: datetime

    class Config:
        from_attributes = True

class DatasetSummarySchema(BaseModel):
    id: str
    name: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    row_count: int
    column_count: int
    status: str
    quality_score: float
    organization_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DatasetDetailSchema(DatasetSummarySchema):
    column_profiles: List[ColumnProfileSchema] = []
    quality_report: Optional[QualityReportSchema] = None
    anomalies: List[AnomalySchema] = []

    class Config:
        from_attributes = True
