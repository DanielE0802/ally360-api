from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, UniqueConstraint, Numeric, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin
import enum

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
    product_taxes = relationship("ProductTax", cascade="all, delete-orphan")

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

# Tax Type Enum
class TaxType(enum.Enum):
    VAT = "VAT"  # IVA
    INC = "INC"  # INC (Impuesto Nacional al Consumo)
    WITHHOLDING = "WITHHOLDING"  # Retención
    MUNICIPAL = "MUNICIPAL"  # Impuestos municipales (ReteICA, etc.)
    OTHER = "OTHER"  # Otros

class Tax(Base, TimestampMixin):
    __tablename__ = "taxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)  # ej. "IVA 19%", "IVA 5%", "INC 8%"
    code = Column(String(10), nullable=False)  # Código DIAN ej. "01" = IVA
    rate = Column(Numeric(5, 4), nullable=False)  # ej. 0.1900, 0.0500
    type = Column(Enum(TaxType), nullable=False)
    is_editable = Column(Boolean, default=True)  # False para impuestos globales DIAN
    
    # Si company_id es NULL, es un impuesto global (DIAN)
    # Si company_id tiene valor, es un impuesto local de la empresa
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    # Relationships
    company = relationship("Company")
    product_taxes = relationship("ProductTax", back_populates="tax", cascade="all, delete-orphan")

    __table_args__ = (
        # Los impuestos globales deben tener nombres únicos
        # Los impuestos locales deben tener nombres únicos por empresa
        UniqueConstraint("company_id", "name", name="uq_tax_company_name"),
    )

class ProductTax(Base, TenantMixin, TimestampMixin):
    __tablename__ = "product_taxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    tax_id = Column(UUID(as_uuid=True), ForeignKey("taxes.id"), nullable=False)

    # Relationships
    product = relationship("Product")
    tax = relationship("Tax", back_populates="product_taxes")

    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "tax_id", name="uq_product_tax_tenant_product_tax"),
    )

# Para futura integración con facturación
class InvoiceTax(Base, TenantMixin, TimestampMixin):
    __tablename__ = "invoice_taxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(UUID(as_uuid=True), nullable=False)  # FK a invoices (futuro)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    tax_id = Column(UUID(as_uuid=True), ForeignKey("taxes.id"), nullable=False)
    base_amount = Column(Numeric(15, 2), nullable=False)  # Base gravable
    tax_amount = Column(Numeric(15, 2), nullable=False)   # Valor del impuesto

    # Relationships
    product = relationship("Product")
    tax = relationship("Tax")
