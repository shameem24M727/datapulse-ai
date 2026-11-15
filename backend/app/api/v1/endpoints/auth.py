import time
import logging
from collections import defaultdict
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Cookie
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserProfileResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
)
from app.services.auth_service import auth_service
from app.core.config import settings
from app.core.roles import UserRole
from app.api.deps import get_current_active_user, get_token_payload

logger = logging.getLogger("datapulse.auth.endpoint")
router = APIRouter()

# ── Brute Force & Rate Limiting Tracker ─────────────────────────────────────────
# Maps identifier (IP/email) -> list of failed timestamp attempts
FAILED_ATTEMPTS: Dict[str, list] = defaultdict(list)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes

def check_login_rate_limit(key: str):
    now = time.time()
    # Filter attempts within lockout window
    FAILED_ATTEMPTS[key] = [t for t in FAILED_ATTEMPTS[key] if now - t < LOCKOUT_WINDOW_SECONDS]
    if len(FAILED_ATTEMPTS[key]) >= MAX_FAILED_ATTEMPTS:
        remaining = int(LOCKOUT_WINDOW_SECONDS - (now - FAILED_ATTEMPTS[key][0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Account temporarily locked for {remaining} seconds.",
        )

def record_failed_attempt(key: str):
    FAILED_ATTEMPTS[key].append(time.time())

def clear_failed_attempts(key: str):
    FAILED_ATTEMPTS.pop(key, None)


# ── Auth Endpoints ─────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: UserRegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Registers a new user, creates their primary organization,
    and returns initial JWT access and refresh tokens.
    """
    user, org, access_token, raw_refresh_token = auth_service.register_user(
        db=db,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        role=request.role or UserRole.DATA_ENGINEER.value,
        organization_name=request.organization_name,
    )

    # Set secure HttpOnly cookie for refresh token
    response.set_cookie(
        key="dp_refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/login", response_model=TokenResponse)
def login(
    request: UserLoginRequest,
    req: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticates user credentials with rate-limiting brute-force protection.
    Returns access token and rotates refresh token.
    """
    client_ip = req.client.host if req.client else "unknown"
    rate_limit_key = f"{client_ip}:{request.email.lower()}"

    check_login_rate_limit(rate_limit_key)

    try:
        user, org, access_token, raw_refresh_token = auth_service.authenticate_user(
            db=db,
            email=request.email,
            password=request.password,
        )
        clear_failed_attempts(rate_limit_key)
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            record_failed_attempt(rate_limit_key)
        raise e

    # Set secure HttpOnly cookie for refresh token
    response.set_cookie(
        key="dp_refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    dp_refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Rotates refresh token and issues fresh JWT access token.
    Accepts token from request body or HttpOnly cookie.
    """
    raw_token = (body.refresh_token if body and body.refresh_token else dp_refresh_token)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token must be provided via request body or cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, org, new_access_token, new_refresh_token = auth_service.rotate_refresh_token(
        db=db,
        raw_refresh_token=raw_token,
    )

    # Update secure cookie
    response.set_cookie(
        key="dp_refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    dp_refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    """Revokes active refresh token and clears auth cookies."""
    raw_token = (body.refresh_token if body and body.refresh_token else dp_refresh_token)
    if raw_token:
        auth_service.revoke_refresh_token(db=db, raw_refresh_token=raw_token)

    response.delete_cookie(key="dp_refresh_token")
    return {"message": "Logged out successfully."}

@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: UserModel = Depends(get_current_active_user),
    payload: Dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):
    """Retrieves full profile, associated organizations, and active tenant ID."""
    memberships = (
        db.query(UserOrganizationModel)
        .filter(UserOrganizationModel.user_id == current_user.id)
        .all()
    )

    org_members = []
    for m in memberships:
        org = db.query(OrganizationModel).filter(OrganizationModel.id == m.organization_id).first()
        org_members.append(
            OrganizationMemberResponse(
                id=m.id,
                user_id=m.user_id,
                organization_id=m.organization_id,
                role=m.role,
                is_default=m.is_default,
                created_at=m.created_at,
                organization=OrganizationResponse.model_validate(org) if org else None,
            )
        )

    active_org_id = payload.get("org_id")
    if not active_org_id and memberships:
        active_org_id = memberships[0].organization_id

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        organizations=org_members,
        active_organization_id=active_org_id,
    )
