"""
Modelos SQLAlchemy para el módulo de Gastos (Bills)

Este módulo maneja toda la cadena de compras:
- Proveedores (Suppliers)
- Órdenes de compra (PurchaseOrders) 
- Facturas de proveedor (Bills)
- Pagos de facturas (BillPayments)
- Notas débito (DebitNotes)

Integración con inventario:
- Bills open/paid → incrementan stock + movimientos IN
- DebitNotes quantity_adjustment → incrementan stock + movimientos IN

Arquitectura multi-tenant: Todas las tablas incluyen company_id
"""

from app.database.database import Base
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Enum, Date, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin
import enum


# ===== ENUMS =====

class PurchaseOrderStatus(enum.Enum):
    """Estados de órdenes de compra"""
    DRAFT = "draft"         # Borrador
    SENT = "sent"           # Enviada al proveedor
    APPROVED = "approved"   # Aprobada por proveedor
    CLOSED = "closed"       # Cerrada/completada
    VOID = "void"           # Anulada


class BillStatus(enum.Enum):
    """Estados de facturas de proveedor"""
    DRAFT = "draft"         # Borrador (no afecta inventario)
    OPEN = "open"           # Abierta/pendiente (afecta inventario)
    PAID = "paid"           # Pagada completamente
    PARTIAL = "partial"     # Pago parcial
    VOID = "void"           # Anulada


class PaymentMethod(enum.Enum):
    """Métodos de pago"""
    CASH = "cash"           # Efectivo
    TRANSFER = "transfer"   # Transferencia bancaria
    CARD = "card"           # Tarjeta
    OTHER = "other"         # Otro método


class DebitNoteStatus(enum.Enum):
    """Estados de notas débito"""
    OPEN = "open"           # Abierta
    VOID = "void"           # Anulada


class DebitNoteReasonType(enum.Enum):
    """Tipos de razón para notas débito"""
    PRICE_ADJUSTMENT = "price_adjustment"       # Ajuste de precio (no afecta inventario)
    QUANTITY_ADJUSTMENT = "quantity_adjustment" # Ajuste de cantidad (afecta inventario)
    SERVICE = "service"                         # Servicio adicional


# ===== MODELOS =====

class Supplier(Base, TenantMixin, TimestampMixin):
    """
    Proveedores de la empresa
    
    Maneja la información básica de proveedores para facturación,
    órdenes de compra y notas débito.
    """
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(200), nullable=False, index=True)
    document = Column(String(50), nullable=True)  # NIT o CC
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier", cascade="all, delete-orphan")
    bills = relationship("Bill", back_populates="supplier", cascade="all, delete-orphan")
    debit_notes = relationship("DebitNote", back_populates="supplier", cascade="all, delete-orphan")

    __table_args__ = (
        # Documento único por empresa (si se proporciona)
        # UniqueConstraint("company_id", "document", name="uq_supplier_company_document"),
        TenantMixin.__table_args__
    )


class PurchaseOrder(Base, TenantMixin, TimestampMixin):
    """
    Órdenes de compra a proveedores
    
    Representa intenciones de compra que pueden convertirse en facturas.
    No afectan el inventario hasta que se convierten en Bills.
    """
    __tablename__ = "purchase_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False, index=True)
    
    issue_date = Column(Date, nullable=False, default=date.today)
    status = Column(Enum(PurchaseOrderStatus), nullable=False, default=PurchaseOrderStatus.DRAFT, index=True)
    currency = Column(String(3), nullable=False, default="COP")
    notes = Column(Text, nullable=True)
    
    # Totales calculados
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    taxes_total = Column(Numeric(15, 2), nullable=False, default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    supplier = relationship("Supplier", back_populates="purchase_orders")
    pdv = relationship("PDV")
    created_by_user = relationship("User")
    items = relationship("POItem", back_populates="purchase_order", cascade="all, delete-orphan")


class POItem(Base, TimestampMixin):
    """
    Ítems de órdenes de compra
    
    Líneas individuales de una orden de compra con productos y cantidades.
    """
    __tablename__ = "po_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    
    # Snapshot de datos del producto al momento de la orden
    name = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    
    # Calculados
    line_subtotal = Column(Numeric(15, 2), nullable=False)
    line_taxes = Column(JSON, nullable=True)  # Detalle de impuestos aplicados
    line_total = Column(Numeric(15, 2), nullable=False)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")


class Bill(Base, TenantMixin, TimestampMixin):
    """
    Facturas de proveedor (Gastos/Compras)
    
    Representan compras reales que afectan el inventario cuando están en estado 'open' o 'paid'.
    Pueden crearse independientemente o desde una PurchaseOrder.
    """
    __tablename__ = "bills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False, index=True)
    
    # Información de la factura
    number = Column(String(100), nullable=False, index=True)  # Número de factura del proveedor
    issue_date = Column(Date, nullable=False, default=date.today)
    due_date = Column(Date, nullable=True)
    status = Column(Enum(BillStatus), nullable=False, default=BillStatus.DRAFT, index=True)
    currency = Column(String(3), nullable=False, default="COP")
    notes = Column(Text, nullable=True)
    
    # Totales calculados
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    taxes_total = Column(Numeric(15, 2), nullable=False, default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(15, 2), nullable=False, default=0)  # Total pagado
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    supplier = relationship("Supplier", back_populates="bills")
    pdv = relationship("PDV")
    created_by_user = relationship("User")
    line_items = relationship("BillLineItem", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship("BillPayment", back_populates="bill", cascade="all, delete-orphan")
    debit_notes = relationship("DebitNote", back_populates="bill", cascade="all, delete-orphan")

    __table_args__ = (
        # Número de factura único por empresa y proveedor
        # UniqueConstraint("company_id", "supplier_id", "number", name="uq_bill_company_supplier_number"),
        TenantMixin.__table_args__
    )


class BillLineItem(Base, TimestampMixin):
    """
    Ítems de facturas de proveedor
    
    Líneas individuales de una factura con productos, cantidades y cálculos de impuestos.
    """
    __tablename__ = "bill_line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    
    # Snapshot de datos del producto
    name = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=False)
    
    # Calculados
    line_subtotal = Column(Numeric(15, 2), nullable=False)
    line_taxes = Column(JSON, nullable=True)  # Detalle de impuestos aplicados
    line_total = Column(Numeric(15, 2), nullable=False)

    # Relationships
    bill = relationship("Bill", back_populates="line_items")
    product = relationship("Product")


class BillPayment(Base, TenantMixin, TimestampMixin):
    """
    Pagos realizados a facturas de proveedor
    
    Permite pagos parciales y control del estado de las facturas.
    """
    __tablename__ = "bill_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False, index=True)
    
    amount = Column(Numeric(15, 2), nullable=False)  # Debe ser > 0
    method = Column(Enum(PaymentMethod), nullable=False)
    reference = Column(String(100), nullable=True)  # Referencia del pago
    payment_date = Column(Date, nullable=False, default=date.today)
    notes = Column(Text, nullable=True)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    bill = relationship("Bill", back_populates="payments")
    created_by_user = relationship("User")


class DebitNote(Base, TenantMixin, TimestampMixin):
    """
    Notas débito a proveedores
    
    Documentos que ajustan facturas por diferencias en precios, cantidades o servicios adicionales.
    Los ajustes de cantidad afectan el inventario.
    """
    __tablename__ = "debit_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    bill_id = Column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=True, index=True)  # Opcional
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    
    issue_date = Column(Date, nullable=False, default=date.today)
    status = Column(Enum(DebitNoteStatus), nullable=False, default=DebitNoteStatus.OPEN, index=True)
    notes = Column(Text, nullable=True)
    
    # Totales calculados
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)
    taxes_total = Column(Numeric(15, 2), nullable=False, default=0)
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    bill = relationship("Bill", back_populates="debit_notes")
    supplier = relationship("Supplier", back_populates="debit_notes")
    created_by_user = relationship("User")
    items = relationship("DebitNoteItem", back_populates="debit_note", cascade="all, delete-orphan")


class DebitNoteItem(Base, TimestampMixin):
    """
    Ítems de notas débito
    
    Líneas individuales de ajustes con diferentes tipos de razón.
    """
    __tablename__ = "debit_note_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    debit_note_id = Column(UUID(as_uuid=True), ForeignKey("debit_notes.id"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True)  # Opcional para servicios
    
    name = Column(String(200), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=True)  # Opcional para ajustes de precio
    unit_price = Column(Numeric(15, 2), nullable=True)  # Opcional para ajustes de cantidad
    reason_type = Column(Enum(DebitNoteReasonType), nullable=False)
    
    # Calculados
    line_subtotal = Column(Numeric(15, 2), nullable=False)
    line_taxes = Column(JSON, nullable=True)  # Detalle de impuestos aplicados
    line_total = Column(Numeric(15, 2), nullable=False)

    # Relationships
    debit_note = relationship("DebitNote", back_populates="items")
    product = relationship("Product")