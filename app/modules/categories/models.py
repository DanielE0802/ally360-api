from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4

from app.database.database import Base
from app.common.mixins import TenantMixin, TimestampMixin

class Category(Base, TenantMixin, TimestampMixin):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    products = relationship("Product", back_populates="category")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_category_tenant_name"),
    )

