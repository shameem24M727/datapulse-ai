from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.session import get_db
from app.models.dataset import DatasetModel, AnomalyModel
from app.models.auth import UserModel, OrganizationModel
from app.api.deps import get_current_active_user, get_current_organization
from app.services.cache_service import cache_service
from app.core.config import settings

router = APIRouter()

@router.get("/summary")
def get_overview_summary(
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Returns aggregated platform metrics scoped to the caller's organization.
    Cached per-organization in Redis to reduce expensive table aggregations.
    """
    cache_key = cache_service.build_key(org.id, "overview", "summary")
    cached_summary = cache_service.get(cache_key)
    if cached_summary is not None:
        return cached_summary

    dataset_query = db.query(DatasetModel).filter(DatasetModel.organization_id == org.id)
    dataset_ids = [d.id for d in dataset_query.all()]

    total_datasets = len(dataset_ids)
    avg_quality = (
        db.query(func.avg(DatasetModel.quality_score))
        .filter(DatasetModel.organization_id == org.id)
        .scalar()
    )
    avg_quality_score = round(float(avg_quality), 1) if avg_quality is not None else 88.0

    total_records = (
        db.query(func.sum(DatasetModel.row_count))
        .filter(DatasetModel.organization_id == org.id)
        .scalar()
        or 0
    )

    # Anomalies count scoped to organization's datasets
    total_anomalies = (
        db.query(func.count(AnomalyModel.id))
        .filter(AnomalyModel.dataset_id.in_(dataset_ids))
        .scalar()
        if dataset_ids else 0
    )
    critical_anomalies = (
        db.query(func.count(AnomalyModel.id))
        .filter(AnomalyModel.dataset_id.in_(dataset_ids), AnomalyModel.severity == "critical")
        .scalar()
        if dataset_ids else 0
    )

    # Status counts
    healthy_count = (
        db.query(func.count(DatasetModel.id))
        .filter(DatasetModel.organization_id == org.id, DatasetModel.status == "healthy")
        .scalar()
        or 0
    )
    warning_count = (
        db.query(func.count(DatasetModel.id))
        .filter(DatasetModel.organization_id == org.id, DatasetModel.status == "warning")
        .scalar()
        or 0
    )
    critical_count = (
        db.query(func.count(DatasetModel.id))
        .filter(DatasetModel.organization_id == org.id, DatasetModel.status == "critical")
        .scalar()
        or 0
    )

    # Recent ingested datasets as activities
    recent_datasets = (
        db.query(DatasetModel)
        .filter(DatasetModel.organization_id == org.id)
        .order_by(desc(DatasetModel.created_at))
        .limit(5)
        .all()
    )

    recent_activities = []
    for ds in recent_datasets:
        recent_activities.append({
            "id": f"act-{ds.id}",
            "type": "upload",
            "title": f"Dataset ingested: {ds.name}",
            "description": f"{ds.row_count:,} rows profiled · Score: {ds.quality_score:.1f}%",
            "timestamp": ds.created_at.strftime("%b %d, %H:%M UTC") if ds.created_at else "Recently",
            "user": "alex.chen@acme.com",
        })

    result = {
        "total_datasets": total_datasets,
        "average_quality_score": avg_quality_score,
        "total_records_monitored": total_records,
        "total_anomalies": total_anomalies,
        "critical_anomalies": critical_anomalies,
        "status_breakdown": {
            "healthy": healthy_count,
            "warning": warning_count,
            "critical": critical_count,
        },
        "recent_activities": recent_activities,
    }
    cache_service.set(cache_key, result, ttl=settings.CACHE_TTL_OVERVIEW_SUMMARY)
    return result
