from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    phone_number = Column(String, unique=True, index=True)
    dni = Column(String(50), unique=True, nullable=False)
    role = Column(String)
    user = relationship("User", back_populates="profile", uselist=False)

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    profile = relationship("Profile", back_populates="user")
    companies = relationship("UserCompany", back_populates="user")

class UserCompany(Base):
    __tablename__ = "user_company"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), primary_key=True)
    role = Column(String, nullable=False, default="empleado")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="companies")
    company = relationship("Company", back_populates="users")
    

class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone_number = Column(String, unique=True, index=True)
    nit = Column(String(50), unique=True, nullable=False)
    social_reason = Column(String, nullable=True)
    logo = Column(String, nullable=True)
    quantity_employees = Column(Integer, default=0)
    economic_activity = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    users = relationship("UserCompany", back_populates="company")