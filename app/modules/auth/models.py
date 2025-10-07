from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid import uuid4
from datetime import datetime, timezone
from app.database.database import Base
from app.common.mixins import TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    first_login = Column(Boolean, default=True)

    # Relationships
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    profile = relationship("Profile", back_populates="user")
    user_companies = relationship("UserCompany", back_populates="user", cascade="all, delete-orphan")
    verification_tokens = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    invitations_sent = relationship("CompanyInvitation", foreign_keys="CompanyInvitation.invited_by_id", back_populates="invited_by")

class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=True)
    dni = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="profile")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class UserCompany(Base, TimestampMixin):
    __tablename__ = "user_companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    role = Column(String, nullable=False, default="user")  # owner, admin, seller, accountant, viewer
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="user_companies")
    company = relationship("Company", back_populates="user_companies")

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company"),
    )

class EmailVerificationToken(Base, TimestampMixin):
    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    is_used = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="verification_tokens")

class PasswordResetToken(Base, TimestampMixin):
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    is_used = Column(Boolean, default=False)

    # Relationships  
    user = relationship("User", back_populates="reset_tokens")

class CompanyInvitation(Base, TimestampMixin):
    __tablename__ = "company_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    invitee_email = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    is_accepted = Column(Boolean, default=False)

    # Relationships
    company = relationship("Company")
    invited_by = relationship("User", foreign_keys=[invited_by_id], back_populates="invitations_sent")

    __table_args__ = (
        UniqueConstraint("company_id", "invitee_email", name="uq_company_invitee"),
    )
    
