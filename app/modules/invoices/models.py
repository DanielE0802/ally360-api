from app.database.database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, UniqueConstraint, Numeric, Enum, Date, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin
import enum


class InvoiceType(enum.Enum):
    SALE = "sale"    # Facturas regulares de venta
    POS = "pos"      # Ventas POS (punto de venta)
    # PURCHASE = "purchase"  # Para futuro
    # EXPENSE = "expense"    # Para futuro


class InvoiceStatus(enum.Enum):
    DRAFT = "draft"      # Borrador, no afecta inventario
    OPEN = "open"        # Abierta, afecta inventario, pendiente de pago
    PAID = "paid"        # Pagada completamente
    VOID = "void"        # Anulada


class PaymentMethod(enum.Enum):
    CASH = "cash"           # Efectivo
    TRANSFER = "transfer"   # Transferencia
    CARD = "card"          # Tarjeta
    OTHER = "other"        # Otro


# Deprecated: Customer entity replaced by Contacts module


class Invoice(Base, TenantMixin, TimestampMixin):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # References
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False)
    # Keep column name customer_id for backward compatibility, but point to contacts table
    customer_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # POS-specific reference
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=True, index=True)
    
    # Invoice data
    number = Column(String(50), nullable=True)  # Secuencia simple por empresa/pdv
    type = Column(Enum(InvoiceType), nullable=False, default=InvoiceType.SALE)
    status = Column(Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.DRAFT)
    
    # Dates
    issue_date = Column(Date, nullable=False, default=date.today)
    due_date = Column(Date, nullable=True)
    
    # Content
    notes = Column(Text, nullable=True)
    currency = Column(String(3), nullable=False, default="COP")
    
    # Totals (calculated)
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    taxes_total = Column(Numeric(15, 2), nullable=False, default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Relationships
    pdv = relationship("PDV")
    # Relationship to unified Contact entity (customers/providers)
    customer = relationship("Contact")
    created_by_user = relationship("User")
    # POS-specific relationship
    seller = relationship("Seller")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "pdv_id", "number", name="uq_invoice_tenant_pdv_number"),
    )

    @property
    def paid_amount(self):
        """Calcular monto pagado"""
        return sum(payment.amount for payment in self.payments)
    
    @property
    def balance_due(self):
        """Calcular saldo pendiente"""
        return self.total_amount - self.paid_amount


class InvoiceLineItem(Base, TimestampMixin):
    __tablename__ = "invoice_line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    
    # Snapshot data (para preservar información si el producto cambia)
    name = Column(String(200), nullable=False)
    sku = Column(String(50), nullable=False)
    
    # Line calculations
    quantity = Column(Numeric(10, 3), nullable=False)  # Permitir decimales para servicios
    unit_price = Column(Numeric(15, 2), nullable=False)  # Precio sin impuestos
    line_subtotal = Column(Numeric(15, 2), nullable=False)  # quantity * unit_price
    line_taxes = Column(JSON, nullable=True)  # Lista de impuestos aplicados
    line_total = Column(Numeric(15, 2), nullable=False)  # line_subtotal + impuestos
    
    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")
    product = relationship("Product")


class Payment(Base, TenantMixin, TimestampMixin):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    
    amount = Column(Numeric(15, 2), nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    reference = Column(String(100), nullable=True)  # Número de referencia, cheque, etc.
    payment_date = Column(Date, nullable=False, default=date.today)
    notes = Column(Text, nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payments")

    __table_args__ = (
        # Los pagos no pueden ser negativos
        # Se validará en el service layer
    )


class InvoiceSequence(Base, TenantMixin):
    """Tabla para manejar secuencias de numeración de facturas por PDV"""
    __tablename__ = "invoice_sequences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False)
    current_number = Column(Integer, nullable=False, default=0)
    prefix = Column(String(10), nullable=True)  # Ej: "F-", "FAC-"
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "pdv_id", name="uq_sequence_tenant_pdv"),
    )