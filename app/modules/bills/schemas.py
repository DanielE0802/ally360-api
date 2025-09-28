"""
Esquemas Pydantic para el módulo de Gastos (Bills)

Define la validación de datos de entrada y salida para todas las entidades:
- Suppliers: Proveedores con validaciones de documentos y emails
- PurchaseOrders: Órdenes de compra con ítems y cálculos
- Bills: Facturas de proveedor con integración de inventario  
- BillPayments: Pagos con validaciones de montos
- DebitNotes: Notas débito con diferentes tipos de ajuste

Todas las validaciones respetan la arquitectura multi-tenant.
"""

from pydantic import BaseModel, Field, validator, root_validator
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime
from enum import Enum


# ===== ENUMS =====

class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    CLOSED = "closed"
    VOID = "void"


class BillStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    PARTIAL = "partial"
    VOID = "void"


class PaymentMethod(str, Enum):
    CASH = "cash"
    TRANSFER = "transfer"
    CARD = "card"
    OTHER = "other"


class DebitNoteStatus(str, Enum):
    OPEN = "open"
    VOID = "void"


class DebitNoteReasonType(str, Enum):
    PRICE_ADJUSTMENT = "price_adjustment"
    QUANTITY_ADJUSTMENT = "quantity_adjustment"
    SERVICE = "service"


# ===== SUPPLIER SCHEMAS =====

class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nombre del proveedor")
    document: Optional[str] = Field(None, max_length=50, description="NIT o CC del proveedor")
    email: Optional[str] = Field(None, max_length=100, description="Email del proveedor")
    phone: Optional[str] = Field(None, max_length=50, description="Teléfono del proveedor")
    address: Optional[str] = Field(None, description="Dirección del proveedor")

    @validator('email')
    def validate_email(cls, v):
        if v and v.strip():
            # Validación básica de email
            if '@' not in v or '.' not in v:
                raise ValueError('Email debe tener formato válido')
        return v


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    document: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None

    @validator('email')
    def validate_email(cls, v):
        if v and v.strip():
            if '@' not in v or '.' not in v:
                raise ValueError('Email debe tener formato válido')
        return v


class SupplierOut(SupplierBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierList(BaseModel):
    items: List[SupplierOut]
    total: int
    limit: int
    offset: int


# ===== PURCHASE ORDER SCHEMAS =====

class POItemBase(BaseModel):
    product_id: UUID = Field(..., description="ID del producto")
    quantity: Decimal = Field(..., gt=0, description="Cantidad a ordenar")
    unit_price: Decimal = Field(..., ge=0, description="Precio unitario")

    @validator('quantity', 'unit_price')
    def validate_decimals(cls, v):
        return v.quantize(Decimal('0.01'))


class POItemCreate(POItemBase):
    pass


class POItemOut(POItemBase):
    id: UUID
    name: str
    line_subtotal: Decimal
    line_taxes: Optional[Dict[str, Any]]
    line_total: Decimal

    class Config:
        from_attributes = True


class PurchaseOrderBase(BaseModel):
    supplier_id: UUID = Field(..., description="ID del proveedor")
    pdv_id: UUID = Field(..., description="ID del PDV")
    issue_date: date = Field(default_factory=date.today, description="Fecha de emisión")
    currency: str = Field("COP", min_length=3, max_length=3, description="Moneda")
    notes: Optional[str] = Field(None, description="Notas adicionales")


class PurchaseOrderCreate(PurchaseOrderBase):
    items: List[POItemCreate] = Field(..., min_items=1, description="Ítems de la orden")

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('La orden debe tener al menos un ítem')
        return v


class PurchaseOrderUpdate(BaseModel):
    supplier_id: Optional[UUID] = None
    pdv_id: Optional[UUID] = None
    issue_date: Optional[date] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    notes: Optional[str] = None
    items: Optional[List[POItemCreate]] = None


class PurchaseOrderOut(PurchaseOrderBase):
    id: UUID
    status: PurchaseOrderStatus
    subtotal: Decimal
    taxes_total: Decimal
    total_amount: Decimal
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PurchaseOrderDetail(PurchaseOrderOut):
    items: List[POItemOut]
    supplier: SupplierOut


class PurchaseOrderList(BaseModel):
    items: List[PurchaseOrderOut]
    total: int
    limit: int
    offset: int


# ===== BILL SCHEMAS =====

class BillLineItemBase(BaseModel):
    product_id: UUID = Field(..., description="ID del producto")
    quantity: Decimal = Field(..., gt=0, description="Cantidad")
    unit_price: Decimal = Field(..., ge=0, description="Precio unitario")

    @validator('quantity', 'unit_price')
    def validate_decimals(cls, v):
        return v.quantize(Decimal('0.01'))


class BillLineItemCreate(BillLineItemBase):
    pass


class BillLineItemOut(BillLineItemBase):
    id: UUID
    name: str
    line_subtotal: Decimal
    line_taxes: Optional[Dict[str, Any]]
    line_total: Decimal

    class Config:
        from_attributes = True


class BillBase(BaseModel):
    supplier_id: UUID = Field(..., description="ID del proveedor")
    pdv_id: UUID = Field(..., description="ID del PDV")
    number: str = Field(..., min_length=1, max_length=100, description="Número de factura del proveedor")
    issue_date: date = Field(default_factory=date.today, description="Fecha de emisión")
    due_date: Optional[date] = Field(None, description="Fecha de vencimiento")
    currency: str = Field("COP", min_length=3, max_length=3, description="Moneda")
    notes: Optional[str] = Field(None, description="Notas adicionales")


class BillCreate(BillBase):
    line_items: List[BillLineItemCreate] = Field(..., min_items=1, description="Ítems de la factura")
    status: BillStatus = Field(BillStatus.DRAFT, description="Estado inicial de la factura")

    @validator('line_items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('La factura debe tener al menos un ítem')
        return v

    @validator('due_date')
    def validate_due_date(cls, v, values):
        if v and 'issue_date' in values and v < values['issue_date']:
            raise ValueError('La fecha de vencimiento no puede ser anterior a la fecha de emisión')
        return v


class BillUpdate(BaseModel):
    supplier_id: Optional[UUID] = None
    pdv_id: Optional[UUID] = None
    number: Optional[str] = Field(None, min_length=1, max_length=100)
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    notes: Optional[str] = None
    line_items: Optional[List[BillLineItemCreate]] = None


class BillOut(BillBase):
    id: UUID
    status: BillStatus
    subtotal: Decimal
    taxes_total: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BillDetail(BillOut):
    line_items: List[BillLineItemOut]
    supplier: SupplierOut
    payments: List['BillPaymentOut'] = []


class BillList(BaseModel):
    items: List[BillOut]
    total: int
    limit: int
    offset: int


# ===== BILL PAYMENT SCHEMAS =====

class BillPaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Monto del pago")
    method: PaymentMethod = Field(..., description="Método de pago")
    reference: Optional[str] = Field(None, max_length=100, description="Referencia del pago")
    payment_date: date = Field(default_factory=date.today, description="Fecha del pago")
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @validator('amount')
    def validate_amount(cls, v):
        return v.quantize(Decimal('0.01'))


class BillPaymentCreate(BillPaymentBase):
    pass


class BillPaymentOut(BillPaymentBase):
    id: UUID
    bill_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BillPaymentList(BaseModel):
    items: List[BillPaymentOut]
    total: int
    limit: int
    offset: int


# ===== DEBIT NOTE SCHEMAS =====

class DebitNoteItemBase(BaseModel):
    product_id: Optional[UUID] = Field(None, description="ID del producto (opcional para servicios)")
    name: str = Field(..., min_length=1, max_length=200, description="Descripción del ítem")
    quantity: Optional[Decimal] = Field(None, gt=0, description="Cantidad (para ajustes de cantidad)")
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Precio unitario (para ajustes de precio)")
    reason_type: DebitNoteReasonType = Field(..., description="Tipo de ajuste")

    @validator('quantity', 'unit_price')
    def validate_decimals(cls, v):
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v

    @root_validator
    def validate_reason_requirements(cls, values):
        reason_type = values.get('reason_type')
        quantity = values.get('quantity')
        unit_price = values.get('unit_price')
        product_id = values.get('product_id')

        if reason_type == DebitNoteReasonType.QUANTITY_ADJUSTMENT:
            if not quantity:
                raise ValueError('quantity es requerido para ajustes de cantidad')
            if not product_id:
                raise ValueError('product_id es requerido para ajustes de cantidad')
        
        if reason_type == DebitNoteReasonType.PRICE_ADJUSTMENT:
            if not unit_price:
                raise ValueError('unit_price es requerido para ajustes de precio')

        return values


class DebitNoteItemCreate(DebitNoteItemBase):
    pass


class DebitNoteItemOut(DebitNoteItemBase):
    id: UUID
    line_subtotal: Decimal
    line_taxes: Optional[Dict[str, Any]]
    line_total: Decimal

    class Config:
        from_attributes = True


class DebitNoteBase(BaseModel):
    bill_id: Optional[UUID] = Field(None, description="ID de la factura relacionada (opcional)")
    supplier_id: UUID = Field(..., description="ID del proveedor")
    issue_date: date = Field(default_factory=date.today, description="Fecha de emisión")
    notes: Optional[str] = Field(None, description="Notas adicionales")


class DebitNoteCreate(DebitNoteBase):
    items: List[DebitNoteItemCreate] = Field(..., min_items=1, description="Ítems de la nota débito")

    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('La nota débito debe tener al menos un ítem')
        return v


class DebitNoteUpdate(BaseModel):
    bill_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    issue_date: Optional[date] = None
    notes: Optional[str] = None
    items: Optional[List[DebitNoteItemCreate]] = None


class DebitNoteOut(DebitNoteBase):
    id: UUID
    status: DebitNoteStatus
    subtotal: Decimal
    taxes_total: Decimal
    total_amount: Decimal
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DebitNoteDetail(DebitNoteOut):
    items: List[DebitNoteItemOut]
    supplier: SupplierOut


class DebitNoteList(BaseModel):
    items: List[DebitNoteOut]
    total: int
    limit: int
    offset: int


# ===== UTILITY SCHEMAS =====

class ConvertPOToBillRequest(BaseModel):
    """Esquema para convertir orden de compra a factura"""
    bill_number: str = Field(..., min_length=1, max_length=100, description="Número de la factura del proveedor")
    issue_date: date = Field(default_factory=date.today, description="Fecha de la factura")
    due_date: Optional[date] = Field(None, description="Fecha de vencimiento")
    status: BillStatus = Field(BillStatus.DRAFT, description="Estado inicial de la factura")
    notes: Optional[str] = Field(None, description="Notas adicionales para la factura")


class BillStatusUpdate(BaseModel):
    """Esquema para cambios de estado de facturas"""
    reason: Optional[str] = Field(None, max_length=500, description="Razón del cambio de estado")


# Forward references
BillDetail.model_rebuild()