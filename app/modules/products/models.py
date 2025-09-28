from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin

class Product(Base, TenantMixin, TimestampMixin):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    sku = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    is_configurable = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))

    # Relationships
    brand = relationship("Brand", lazy="joined")
    category = relationship("Category", lazy="joined")
    stocks = relationship("Stock", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    movements = relationship("InventoryMovement", back_populates="product")

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
    )

class ProductVariant(Base, TenantMixin, TimestampMixin):
    __tablename__ = "product_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    color = Column(String(50), nullable=True)
    size = Column(String(50), nullable=True)
    sku = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    product = relationship("Product", back_populates="variants")
    stocks = relationship("Stock", back_populates="variant")

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_variant_tenant_sku"),
    )

Product.variants = relationship("ProductVariant", back_populates="product")

class InventoryMovement(Base, TenantMixin, TimestampMixin):
    __tablename__ = "inventory_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    
    quantity = Column(Integer, nullable=False)  # Can be positive or negative
    movement_type = Column(String(20), nullable=False)  # IN, OUT, ADJ, TRANSFER
    reference = Column(String(100), nullable=True)  # Order, invoice, etc.
    notes = Column(String(255), nullable=True)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="movements")
    pdv = relationship("PDV")
    variant = relationship("ProductVariant")
    created_by_user = relationship("User")

class Stock(Base, TenantMixin, TimestampMixin):
    __tablename__ = "stocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    quantity = Column(Integer, nullable=False, default=0)

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False)

    # Relationships
    product = relationship("Product", back_populates="stocks")
    variant = relationship("ProductVariant", back_populates="stocks")
    pdv = relationship("PDV", back_populates="stocks")

    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "pdv_id", "variant_id", name="uq_stock_tenant_product_pdv_variant"),
    )
