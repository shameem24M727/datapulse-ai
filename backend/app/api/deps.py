import logging
from typing import Optional, Dict, Any, List, Callable
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, ExpiredSignatureError

from app.db.session import get_db
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel
from app.core.security import decode_access_token
from app.core.roles import UserRole, Permission, has_permission

logger = logging.getLogger("datapulse.deps")

# OAuth2 bearer token extractor (auto_error=False to allow clean custom error handling)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)

def get_token_payload(token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Validates presence and signature of JWT access token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing subject identifier.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token signature or malformed token: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(
    payload: Dict[str, Any] = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> UserModel:
    """Retrieves user model matching JWT subject identifier."""
    user_id = payload.get("sub")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_active_user(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    """Ensures authenticated user is active and not disabled."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact an administrator.",
        )
    return current_user

# Alias for require_authenticated_user
require_authenticated_user = get_current_active_user

def get_current_organization(
    payload: Dict[str, Any] = Depends(get_token_payload),
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationModel:
    """
    Extracts active organization context from token payload,
    verifying caller holds a valid membership in that organization.
    """
    org_id = payload.get("org_id")

    if org_id:
        # Verify user is a member of the requested organization
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
                detail="Access denied: Caller is not a member of the active organization.",
            )
        org = db.query(OrganizationModel).filter(OrganizationModel.id == org_id).first()
        if org and org.is_active:
            return org

    # Fallback to user's default organization
    default_membership = (
        db.query(UserOrganizationModel)
        .filter(UserOrganizationModel.user_id == current_user.id)
        .order_by(UserOrganizationModel.is_default.desc())
        .first()
    )
    if default_membership:
        org = db.query(OrganizationModel).filter(OrganizationModel.id == default_membership.organization_id).first()
        if org and org.is_active:
            return org

    # System default organization fallback
    default_org = db.query(OrganizationModel).filter(OrganizationModel.id == "org_default_001").first()
    if default_org:
        return default_org

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No active organization found for this user.",
    )

def require_roles(allowed_roles: List[str]) -> Callable:
    """
    Dependency factory that checks if current user holds one of the required roles.
    Checks organization-specific role first, falling back to global role.
    """
    def role_checker(
        current_user: UserModel = Depends(get_current_active_user),
        org: OrganizationModel = Depends(get_current_organization),
        db: Session = Depends(get_db),
    ) -> UserModel:
        # Check org-specific membership role
        membership = (
            db.query(UserOrganizationModel)
            .filter(
                UserOrganizationModel.user_id == current_user.id,
                UserOrganizationModel.organization_id == org.id,
            )
            .first()
        )
        effective_role = membership.role if membership else current_user.role

        # Admin always bypasses role checks
        if effective_role == UserRole.ADMIN.value or current_user.role == UserRole.ADMIN.value:
            return current_user

        if effective_role not in allowed_roles and current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Operation requires one of the following roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return role_checker

def require_permission(permission: Permission) -> Callable:
    """
    Dependency factory that enforces granular RBAC permissions.
    """
    def permission_checker(
        current_user: UserModel = Depends(get_current_active_user),
        org: OrganizationModel = Depends(get_current_organization),
        db: Session = Depends(get_db),
    ) -> UserModel:
        membership = (
            db.query(UserOrganizationModel)
            .filter(
                UserOrganizationModel.user_id == current_user.id,
                UserOrganizationModel.organization_id == org.id,
            )
            .first()
        )
        effective_role = membership.role if membership else current_user.role

        # Check if user holds the permission
        if not has_permission(effective_role, permission) and not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Missing permission: '{permission.value}'.",
            )
        return current_user

    return permission_checker
