from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4

class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    sku = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_configurable = Column(Boolean, default=False)

    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"))
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    brand = relationship("Brand", lazy="joined")
    category = relationship("Category", lazy="joined")
    stocks = relationship("Stock", back_populates="product")
    variants = relationship("ProductVariant", back_populates="product")

class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    color = Column(String(50), nullable=True)
    size = Column(String(50), nullable=True)
    sku = Column(String(50), unique=True, nullable=False)
    price = Column(Float, nullable=False)

    product = relationship("Product", back_populates="variants")
    stocks = relationship("Stock", back_populates="variant")

Product.variants = relationship("ProductVariant", back_populates="product")

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    quantity = Column(Integer, nullable=False)

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False)

    product = relationship("Product", back_populates="stocks")
    variant = relationship("ProductVariant", back_populates="stocks")
    pdv = relationship("PDV", back_populates="stocks")
