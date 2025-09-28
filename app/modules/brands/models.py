from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID

from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin

class Brand(Base, TenantMixin, TimestampMixin):
    __tablename__ = "brands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    products = relationship("Product", back_populates="brand")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_brand_tenant_name"),
    )

