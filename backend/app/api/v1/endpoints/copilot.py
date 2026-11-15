import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import DatasetModel, CopilotMessageModel
from app.schemas.copilot import (
    CopilotQueryRequest,
    CopilotQueryResponse,
    CopilotMessageSchema,
    CopilotSuggestionsResponse,
)
from app.services.copilot_context import (
    build_dataset_context,
    generate_dataset_suggestions,
)
from app.services.gemini_service import gemini_copilot_service
from app.models.auth import UserModel, OrganizationModel
from app.core.roles import Permission
from app.api.deps import (
    get_current_active_user,
    get_current_organization,
    require_permission,
)

logger = logging.getLogger("datapulse.copilot.endpoint")
router = APIRouter()

@router.post("/query", response_model=CopilotQueryResponse)
async def query_copilot(
    request: CopilotQueryRequest,
    current_user: UserModel = Depends(require_permission(Permission.COPILOT_QUERY)),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Submits a natural language query about a specific dataset.
    Extracts actual profiling, quality metrics, and anomalies,
    and returns a factual response via Gemini (or grounded fallback).
    Enforces tenant isolation and COPILOT_QUERY permission.
    """
    cleaned_question = request.question.strip()
    if not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty.",
        )

    dataset = (
        db.query(DatasetModel)
        .filter(DatasetModel.id == request.dataset_id, DatasetModel.organization_id == org.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{request.dataset_id}' not found in current organization.",
        )

    # 1. Build privacy-safe, non-PII context from actual database results
    context = build_dataset_context(dataset)

    # 2. Generate response via GeminiCopilotService
    result = await gemini_copilot_service.generate_copilot_response(
        dataset_context=context,
        user_question=cleaned_question,
    )

    # 3. Persist conversation history to database
    try:
        user_msg = CopilotMessageModel(
            dataset_id=dataset.id,
            role="user",
            content=cleaned_question,
        )
        assistant_msg = CopilotMessageModel(
            dataset_id=dataset.id,
            role="assistant",
            content=result["answer"],
            recommendations=result.get("recommendations"),
            metrics=result.get("metrics"),
            model_used=result.get("model"),
        )
        db.add(user_msg)
        db.add(assistant_msg)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist copilot message: {e}")
        db.rollback()

    return CopilotQueryResponse(
        answer=result["answer"],
        metrics=result.get("metrics"),
        recommendations=result.get("recommendations"),
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        model=result.get("model", "grounded-engine"),
        is_fallback=result.get("is_fallback", False),
        evidence_used=result.get("evidence_used", []),
    )

@router.get("/suggestions/{dataset_id}", response_model=CopilotSuggestionsResponse)
def get_suggestions(
    dataset_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Generates dynamic prompt suggestions tailored specifically to the dataset's
    actual missing values, anomalies, and quality deductions within caller's organization.
    """
    dataset = (
        db.query(DatasetModel)
        .filter(DatasetModel.id == dataset_id, DatasetModel.organization_id == org.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found in current organization.",
        )

    context = build_dataset_context(dataset)
    suggestions = generate_dataset_suggestions(context)

    return CopilotSuggestionsResponse(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        suggestions=suggestions,
    )

@router.get("/history/{dataset_id}", response_model=List[CopilotMessageSchema])
def get_chat_history(
    dataset_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Retrieves stored conversation history for the specified dataset within caller's organization.
    """
    dataset = (
        db.query(DatasetModel)
        .filter(DatasetModel.id == dataset_id, DatasetModel.organization_id == org.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found in current organization.",
        )

    messages = (
        db.query(CopilotMessageModel)
        .filter(CopilotMessageModel.dataset_id == dataset_id)
        .order_by(CopilotMessageModel.created_at.asc())
        .all()
    )

    return messages

@router.delete("/history/{dataset_id}")
def clear_chat_history(
    dataset_id: str,
    current_user: UserModel = Depends(require_permission(Permission.COPILOT_QUERY)),
    org: OrganizationModel = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Clears all saved conversation history for the specified dataset within caller's organization.
    """
    dataset = (
        db.query(DatasetModel)
        .filter(DatasetModel.id == dataset_id, DatasetModel.organization_id == org.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found in current organization.",
        )

    deleted_count = (
        db.query(CopilotMessageModel)
        .filter(CopilotMessageModel.dataset_id == dataset_id)
        .delete()
    )
    db.commit()

    return {
        "message": f"Conversation history for dataset '{dataset.name}' cleared successfully.",
        "deleted_count": deleted_count,
    }
