import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.auth import UserModel, OrganizationModel, UserOrganizationModel, RefreshTokenModel
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    hash_token,
)
from app.core.config import settings
from app.core.roles import UserRole

logger = logging.getLogger("datapulse.auth")

class AuthService:
    """Core authentication, token issuance, refresh rotation, and revocation engine."""

    @staticmethod
    def register_user(
        db: Session,
        email: str,
        password: str,
        full_name: str,
        role: str = UserRole.DATA_ENGINEER.value,
        organization_name: Optional[str] = None,
    ) -> Tuple[UserModel, OrganizationModel, str, str]:
        """Registers a new user, assigns/creates their organization, and issues tokens."""
        email_clean = email.strip().lower()

        # 1. Validate password requirements
        valid, msg = validate_password_strength(password)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )

        # 2. Check if user already exists
        existing = db.query(UserModel).filter(UserModel.email == email_clean).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        # 3. Hash password and persist user
        hashed = hash_password(password)
        user = UserModel(
            email=email_clean,
            hashed_password=hashed,
            full_name=full_name.strip(),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # 4. Create or assign default organization
        org_name = organization_name.strip() if organization_name else f"{full_name.strip()}'s Workspace"
        base_slug = org_name.lower().replace(" ", "-").replace("'", "")
        slug = f"{base_slug}-{user.id[:8]}"

        org = OrganizationModel(
            name=org_name,
            slug=slug,
            description=f"Primary organization for {user.full_name}",
            is_active=True,
        )
        db.add(org)
        db.flush()

        # 5. Create Organization Membership (User is Admin of their own organization)
        membership = UserOrganizationModel(
            user_id=user.id,
            organization_id=org.id,
            role=UserRole.ADMIN.value if role == UserRole.ADMIN.value else role,
            is_default=True,
        )
        db.add(membership)

        # 6. Issue initial JWT access token & Refresh token
        access_token, raw_refresh_token = AuthService.generate_tokens(db, user, org.id)
        db.commit()
        db.refresh(user)
        db.refresh(org)

        return user, org, access_token, raw_refresh_token

    @staticmethod
    def authenticate_user(
        db: Session,
        email: str,
        password: str,
    ) -> Tuple[UserModel, OrganizationModel, str, str]:
        """Authenticates user credentials, verifies status, and issues fresh tokens."""
        email_clean = email.strip().lower()
        user = db.query(UserModel).filter(UserModel.email == email_clean).first()

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled. Please contact an administrator.",
            )

        # Retrieve default or first organization membership
        membership = (
            db.query(UserOrganizationModel)
            .filter(UserOrganizationModel.user_id == user.id)
            .order_by(UserOrganizationModel.is_default.desc(), UserOrganizationModel.created_at.asc())
            .first()
        )

        if not membership:
            # Fallback to system default organization if none associated
            default_org = db.query(OrganizationModel).filter(OrganizationModel.id == "org_default_001").first()
            if not default_org:
                default_org = OrganizationModel(
                    id="org_default_001",
                    name="Default Workspace",
                    slug="default-workspace",
                    is_active=True,
                )
                db.add(default_org)
                db.flush()

            membership = UserOrganizationModel(
                user_id=user.id,
                organization_id=default_org.id,
                role=user.role,
                is_default=True,
            )
            db.add(membership)
            db.flush()

        org = db.query(OrganizationModel).filter(OrganizationModel.id == membership.organization_id).first()
        access_token, raw_refresh_token = AuthService.generate_tokens(db, user, org.id)
        db.commit()

        return user, org, access_token, raw_refresh_token

    @staticmethod
    def generate_tokens(
        db: Session,
        user: UserModel,
        organization_id: str,
    ) -> Tuple[str, str]:
        """Issues a new JWT access token and records a cryptographically hashed refresh token."""
        # Payload embedded in JWT access token
        payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "org_id": organization_id,
        }
        access_token = create_access_token(payload)

        # Issue secure refresh token
        raw_refresh_token = create_refresh_token()
        hashed = hash_token(raw_refresh_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        token_record = RefreshTokenModel(
            user_id=user.id,
            token_hash=hashed,
            expires_at=expires_at,
            is_revoked=False,
        )
        db.add(token_record)
        return access_token, raw_refresh_token

    @staticmethod
    def rotate_refresh_token(
        db: Session,
        raw_refresh_token: str,
    ) -> Tuple[UserModel, OrganizationModel, str, str]:
        """
        Rotates a refresh token:
        - Validates token hash exists, is unexpired, and unrevoked.
        - Revokes previous token immediately (mitigating token reuse).
        - Issues new access token + new refresh token.
        """
        token_hash = hash_token(raw_refresh_token)
        record = db.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if record.is_revoked:
            logger.warning(f"Security Alert: Attempted reuse of revoked refresh token for user {record.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)
        record_exp = record.expires_at.replace(tzinfo=timezone.utc) if record.expires_at.tzinfo is None else record.expires_at
        if record_exp < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired. Please login again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = db.query(UserModel).filter(UserModel.id == record.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        # Revoke the used token immediately
        record.is_revoked = True

        # Retrieve user's default organization
        membership = (
            db.query(UserOrganizationModel)
            .filter(UserOrganizationModel.user_id == user.id)
            .order_by(UserOrganizationModel.is_default.desc())
            .first()
        )
        org_id = membership.organization_id if membership else "org_default_001"
        org = db.query(OrganizationModel).filter(OrganizationModel.id == org_id).first()

        # Generate new pair
        new_access_token, new_refresh_token = AuthService.generate_tokens(db, user, org_id)
        db.commit()

        return user, org, new_access_token, new_refresh_token

    @staticmethod
    def revoke_refresh_token(db: Session, raw_refresh_token: str) -> bool:
        """Revokes a refresh token on logout."""
        token_hash = hash_token(raw_refresh_token)
        record = db.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).first()
        if record:
            record.is_revoked = True
            db.commit()
            return True
        return False

auth_service = AuthService()
