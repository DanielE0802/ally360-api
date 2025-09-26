from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from uuid import uuid4
from sqlalchemy.orm import relationship

class PDV(Base):
    __tablename__ = "pdvs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False, unique=True)
    address = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    
    stocks = relationship("Stock", back_populates="pdv")

