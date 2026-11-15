from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters with at least one number and letter")
    full_name: str = Field(..., min_length=2, max_length=100)
    role: Optional[Literal["admin", "data_engineer", "analyst", "viewer"]] = "data_engineer"
    organization_name: Optional[str] = Field(None, max_length=100, description="Optional organization name to create")

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None

class OrganizationMemberResponse(BaseModel):
    id: str
    user_id: str
    organization_id: str
    role: str
    is_default: bool
    created_at: datetime
    organization: Optional[OrganizationResponse] = None

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserProfileResponse(UserResponse):
    organizations: List[OrganizationMemberResponse] = []
    active_organization_id: Optional[str] = None
