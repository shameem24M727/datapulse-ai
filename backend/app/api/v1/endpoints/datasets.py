import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.dataset import (
    DatasetModel,
    ColumnProfileModel,
    QualityReportModel,
    AnomalyModel,
)
from app.schemas.dataset import DatasetSummarySchema, DatasetDetailSchema
from app.services.parser import validate_and_read_file
from app.services.profiler import profile_dataframe
from app.services.quality_engine import compute_data_quality
from app.services.anomaly_engine import detect_anomalies
from app.core.config import settings
from app.models.auth import UserModel, OrganizationModel
from app.core.roles import Permission
from app.api.deps import (
    get_current_active_user,
    get_current_organization,
    require_permission,
)
from app.services.cache_service import cache_service

router = APIRouter()

@router.post("/upload", response_model=DatasetDetailSchema, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(require_permission(Permission.DATASET_CREATE)),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Ingest a real CSV or Excel file, perform profiling, evaluate data quality,
    detect statistical anomalies, and persist findings scoped to the caller's organization.
    """
    # 1. Parse and validate file safely
    df, clean_filename, file_size, ext = await validate_and_read_file(file)

    # 2. Derive friendly dataset display name
    base_name = clean_filename.rsplit(".", 1)[0].replace("_", " ").title()

    # 3. Save uploaded file copy to storage path safely
    dataset_record = DatasetModel(
        name=base_name,
        original_filename=clean_filename,
        file_type=ext,
        file_size_bytes=file_size,
        row_count=len(df),
        column_count=len(df.columns),
        status="processing",
        organization_id=org.id,
        created_by_user_id=current_user.id,
    )
    db.add(dataset_record)
    db.flush()  # assign UUID to dataset_record.id

    storage_filename = f"{dataset_record.id}.{ext}"
    storage_path = os.path.join(settings.UPLOAD_DIR, storage_filename)
    try:
        # Save parsed DataFrame to clean CSV or original binary format
        df.to_csv(storage_path, index=False)
        dataset_record.storage_path = storage_path
    except Exception:
        pass

    # 4. Profile DataFrame
    profile = profile_dataframe(df)

    # 5. Evaluate Data Quality
    quality = compute_data_quality(df, profile)
    dataset_record.quality_score = quality["overall_score"]
    dataset_record.status = quality["status"]

    # 6. Detect Anomalies
    detected_anomalies = detect_anomalies(df, profile)

    # 7. Persist Column Profiles
    for col in profile["columns"]:
        cp = ColumnProfileModel(
            dataset_id=dataset_record.id,
            column_name=col["column_name"],
            data_type=col["data_type"],
            total_count=col["total_count"],
            null_count=col["null_count"],
            null_percentage=col["null_percentage"],
            unique_count=col["unique_count"],
            is_numeric=col["is_numeric"],
            min_value=col["min_value"],
            max_value=col["max_value"],
            mean_value=col["mean_value"],
            median_value=col["median_value"],
            std_value=col["std_value"],
            top_values=col["top_values"],
        )
        db.add(cp)

    # 8. Persist Quality Report
    qr = QualityReportModel(
        dataset_id=dataset_record.id,
        overall_score=quality["overall_score"],
        completeness_score=quality["completeness_score"],
        uniqueness_score=quality["uniqueness_score"],
        validity_score=quality["validity_score"],
        consistency_score=quality["consistency_score"],
        duplicate_rows_count=quality["duplicate_rows_count"],
        duplicate_rows_percentage=quality["duplicate_rows_percentage"],
        total_cells=quality["total_cells"],
        null_cells=quality["null_cells"],
        deductions_evidence=quality["evidence"],
    )
    db.add(qr)

    # 9. Persist Anomalies
    for anom in detected_anomalies:
        am = AnomalyModel(
            dataset_id=dataset_record.id,
            column_name=anom["column_name"],
            anomaly_type=anom["anomaly_type"],
            severity=anom["severity"],
            affected_rows=anom["affected_rows"],
            description=anom["description"],
            details=anom["details"],
        )
        db.add(am)

    db.commit()
    db.refresh(dataset_record)

    # Invalidate dataset catalog lists and overview cache for this tenant
    cache_service.invalidate_datasets(org.id)

    return dataset_record

@router.get("/", response_model=List[DatasetSummarySchema])
def list_datasets(
    skip: int = 0,
    limit: int = 50,
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """List all ingested datasets belonging to the caller's organization."""
    cache_key = cache_service.build_key(org.id, "datasets", f"list:skip={skip}:limit={limit}")
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    datasets = (
        db.query(DatasetModel)
        .filter(DatasetModel.organization_id == org.id)
        .order_by(desc(DatasetModel.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = [DatasetSummarySchema.model_validate(d).model_dump() for d in datasets]
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_DATASET_LIST)
    return result

@router.get("/{dataset_id}", response_model=DatasetDetailSchema)
def get_dataset(
    dataset_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Retrieve complete profiling, data quality, and anomaly details for a dataset.
    Enforces organization isolation against IDOR with Redis caching.
    """
    cache_key = cache_service.build_key(org.id, "datasets", dataset_id, "detail")
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    dataset = (
        db.query(DatasetModel)
        .filter(DatasetModel.id == dataset_id, DatasetModel.organization_id == org.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset with ID '{dataset_id}' not found in current organization.",
        )
    result = DatasetDetailSchema.model_validate(dataset).model_dump()
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_DATASET_DETAIL)
    return result

@router.delete("/{dataset_id}", status_code=200)
def delete_dataset(
    dataset_id: str,
    current_user: UserModel = Depends(require_permission(Permission.DATASET_DELETE)),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Delete a dataset and all associated profiles, quality reports, and anomaly findings.
    Requires DATASET_DELETE permission and organization tenant match.
    """
    dataset = (
        db.query(DatasetModel)
        .filter(DatasetModel.id == dataset_id, DatasetModel.organization_id == org.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset with ID '{dataset_id}' not found in current organization.",
        )

    # Remove storage file if it exists
    if dataset.storage_path and os.path.exists(dataset.storage_path):
        try:
            os.remove(dataset.storage_path)
        except Exception:
            pass

    db.delete(dataset)
    db.commit()

    # Invalidate dataset detail and list cache
    cache_service.invalidate_datasets(org.id, dataset_id)

    return {"message": f"Dataset '{dataset.name}' successfully deleted.", "id": dataset_id}
