from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

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
    
    user_companies = relationship("UserCompany", back_populates="company")