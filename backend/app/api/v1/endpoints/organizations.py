from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel
from app.schemas.auth import (
    OrganizationResponse,
    OrganizationCreateRequest,
    OrganizationMemberResponse,
    TokenResponse,
)
from app.services.auth_service import auth_service
from app.core.roles import UserRole
from app.core.config import settings
from app.api.deps import (
    get_current_active_user,
    get_current_organization,
    require_roles,
)

router = APIRouter()

class AddMemberRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"

@router.get("/", response_model=List[OrganizationResponse])
def list_user_organizations(
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieves all organizations that the current user belongs to."""
    if current_user.role == UserRole.ADMIN.value:
        # Global admin sees all active organizations
        return db.query(OrganizationModel).filter(OrganizationModel.is_active == True).all()

    memberships = (
        db.query(UserOrganizationModel)
        .filter(UserOrganizationModel.user_id == current_user.id)
        .all()
    )
    org_ids = [m.organization_id for m in memberships]
    return (
        db.query(OrganizationModel)
        .filter(OrganizationModel.id.in_(org_ids), OrganizationModel.is_active == True)
        .all()
    )

@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    request: OrganizationCreateRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Creates a new organization and grants the creator Admin privileges within it."""
    slug = request.slug.strip().lower() if request.slug else request.name.strip().lower().replace(" ", "-")
    slug = f"{slug}-{current_user.id[:6]}"

    existing = db.query(OrganizationModel).filter(OrganizationModel.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{slug}' already exists.",
        )

    org = OrganizationModel(
        name=request.name.strip(),
        slug=slug,
        description=request.description,
        is_active=True,
    )
    db.add(org)
    db.flush()

    membership = UserOrganizationModel(
        user_id=current_user.id,
        organization_id=org.id,
        role=UserRole.ADMIN.value,
        is_default=False,
    )
    db.add(membership)
    db.commit()
    db.refresh(org)

    return org

@router.post("/switch/{org_id}", response_model=TokenResponse)
def switch_active_organization(
    org_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Switches caller's active organization context and mints a new tenant-scoped access token."""
    # Verify membership
    membership = (
        db.query(UserOrganizationModel)
        .filter(
            UserOrganizationModel.user_id == current_user.id,
            UserOrganizationModel.organization_id == org_id,
        )
        .first()
    )

    if not membership and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a member of this organization.",
        )

    org = db.query(OrganizationModel).filter(OrganizationModel.id == org_id).first()
    if not org or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found or inactive.",
        )

    # Issue fresh tokens scoped to selected organization
    access_token, raw_refresh_token = auth_service.generate_tokens(db, current_user, org.id)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.get("/{org_id}/members", response_model=List[OrganizationMemberResponse])
def get_organization_members(
    org_id: str,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retrieves all members of an organization."""
    # Check caller has permission in this org
    caller_mem = (
        db.query(UserOrganizationModel)
        .filter(
            UserOrganizationModel.user_id == current_user.id,
            UserOrganizationModel.organization_id == org_id,
        )
        .first()
    )
    if not caller_mem and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Access denied to organization members.")

    memberships = (
        db.query(UserOrganizationModel)
        .filter(UserOrganizationModel.organization_id == org_id)
        .all()
    )
    return memberships

@router.post("/{org_id}/members", response_model=OrganizationMemberResponse, status_code=status.HTTP_201_CREATED)
def add_organization_member(
    org_id: str,
    request: AddMemberRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Adds a registered user to an organization. Requires Admin privileges."""
    caller_mem = (
        db.query(UserOrganizationModel)
        .filter(
            UserOrganizationModel.user_id == current_user.id,
            UserOrganizationModel.organization_id == org_id,
        )
        .first()
    )
    if (not caller_mem or caller_mem.role != UserRole.ADMIN.value) and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Organization Admins can add members.",
        )

    target_user = db.query(UserModel).filter(UserModel.email == request.email.lower().strip()).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User with email '{request.email}' not found.")

    existing_mem = (
        db.query(UserOrganizationModel)
        .filter(
            UserOrganizationModel.user_id == target_user.id,
            UserOrganizationModel.organization_id == org_id,
        )
        .first()
    )
    if existing_mem:
        raise HTTPException(status_code=409, detail="User is already a member of this organization.")

    new_mem = UserOrganizationModel(
        user_id=target_user.id,
        organization_id=org_id,
        role=request.role,
        is_default=False,
    )
    db.add(new_mem)
    db.commit()
    db.refresh(new_mem)
    return new_mem
