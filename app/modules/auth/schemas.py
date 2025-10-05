from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# Base schemas
class ProfileCreate(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    phone_number: Optional[str] = Field(None, max_length=20)
    dni: Optional[str] = Field(None, max_length=20)

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    phone_number: Optional[str] = Field(None, max_length=20)
    # DNI is excluded - cannot be updated

class UserUpdate(BaseModel):
    """Schema for updating user information. Email and password changes require separate endpoints."""
    profile: Optional[ProfileUpdate] = None

class ImageUploadResponse(BaseModel):
    message: str
    avatar_url: str

class ProfileOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    phone_number: Optional[str]
    dni: Optional[str]
    avatar_url: Optional[str]
    full_name: str

    class Config:
        from_attributes = True

# User schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    profile: ProfileCreate

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    is_active: bool
    email_verified: bool
    profile: ProfileOut

    class Config:
        from_attributes = True

class UserCompanyOut(BaseModel):
    id: UUID
    company_id: UUID
    role: str
    is_active: bool
    joined_at: datetime
    company_name: str

    class Config:
        from_attributes = True

# Token schemas
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    companies: List[UserCompanyOut] = []
    refresh_token: Optional[str] = None

class ContextTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    tenant_id: UUID
    company_name: str
    user_role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Company users schemas
class CompanyUserOut(BaseModel):
    id: UUID
    email: str
    is_active: bool
    email_verified: bool
    profile: ProfileOut
    role: str
    is_user_active: bool
    joined_at: datetime

    class Config:
        from_attributes = True

class CompanyUsersResponse(BaseModel):
    users: List[CompanyUserOut]
    total: int
    page: int
    limit: int
    total_pages: int

# Email verification schemas
class EmailVerificationRequest(BaseModel):
    email: EmailStr

class EmailVerificationConfirm(BaseModel):
    token: str

# Password reset schemas  
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        return v

# Company invitation schemas
class CompanyInvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(..., description="Rol a asignar: owner, admin, seller, accountant, viewer")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed = {"owner", "admin", "seller", "accountant", "viewer"}
        if v not in allowed:
            raise ValueError(f"Rol inválido. Debe ser uno de: {', '.join(sorted(allowed))}")
        return v

class CompanyInvitationOut(BaseModel):
    id: UUID
    invitee_email: str
    role: str
    expires_at: datetime
    is_accepted: bool
    invited_by_name: str
    company_name: str

    class Config:
        from_attributes = True

class CompanyInvitationAccept(BaseModel):
    token: str
    password: str = Field(..., min_length=8)
    profile: ProfileCreate

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        return v

class CompanyInvitationAcceptExisting(BaseModel):
    """Schema for existing users accepting company invitations."""
    token: str

class InvitationInfo(BaseModel):
    """Information about an invitation token."""
    company_name: str
    company_id: UUID
    invitee_email: str
    role: str
    user_exists: bool
    expires_at: datetime

# Company selection schemas
class CompanySelectionRequest(BaseModel):
    company_id: UUID

# Auth context schemas
class AuthContext(BaseModel):
    user_id: UUID
    tenant_id: Optional[UUID] = None
    user_role: Optional[str] = None
    companies: List[UserCompanyOut] = []
