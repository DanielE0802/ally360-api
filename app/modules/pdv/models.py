from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from uuid import uuid4
from sqlalchemy.orm import relationship
from app.common.mixins import TenantMixin, TimestampMixin

class PDV(Base, TenantMixin, TimestampMixin):
    __tablename__ = "pdvs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    is_main = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Location relationships
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True, index=True)
    
    # Relationships - using strings to avoid circular imports
    stocks = relationship("Stock", back_populates="pdv")
    department = relationship("Department", foreign_keys=[department_id])
    city = relationship("City", foreign_keys=[city_id])

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_pdv_tenant_name"),
    )

