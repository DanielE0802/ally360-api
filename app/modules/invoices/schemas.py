from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime
from enum import Enum
from app.modules.contacts.schemas import ContactForInvoice


class InvoiceType(str, Enum):
    SALE = "SALE"


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAID = "PAID"
    VOID = "VOID"


class PaymentMethod(str, Enum):
    CASH = "cash"
    TRANSFER = "transfer"
    CARD = "card"
    OTHER = "other"


# Customer Schemas (deprecated: use Contacts module instead)
class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = Field(None, max_length=100)
    document: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = Field(None, max_length=100)
    document: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None


class CustomerOut(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerList(BaseModel):
    customers: List[CustomerOut]
    total: int
    limit: int
    offset: int


# Invoice Line Item Schemas
class InvoiceLineItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0, description="Cantidad debe ser mayor a 0")
    unit_price: Decimal = Field(..., ge=0, description="Precio unitario sin impuestos")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('La cantidad debe ser mayor a 0')
        return v

    @field_validator('unit_price')
    @classmethod
    def validate_unit_price(cls, v):
        if v < 0:
            raise ValueError('El precio unitario no puede ser negativo')
        return v


class InvoiceLineItemOut(BaseModel):
    id: UUID
    product_id: UUID
    name: str
    sku: str
    quantity: Decimal
    unit_price: Decimal
    line_subtotal: Decimal
    line_taxes: Optional[List[Dict[str, Any]]] = None
    line_total: Decimal

    class Config:
        from_attributes = True


# Invoice Schemas
class InvoiceCreate(BaseModel):
    pdv_id: UUID
    customer_id: UUID  # Contact ID (type must include 'client')
    issue_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    notes: Optional[str] = None
    status: InvoiceStatus = InvoiceStatus.DRAFT
    items: List[InvoiceLineItemCreate] = Field(..., min_items=1, description="Debe incluir al menos un item")

    @model_validator(mode='after')
    def validate_due_date(self):
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValueError('La fecha de vencimiento no puede ser anterior a la fecha de emisión')
        return self

    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if not v:
            raise ValueError('Debe incluir al menos un item en la factura')
        return v


class InvoiceUpdate(BaseModel):
    customer_id: Optional[UUID] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    items: Optional[List[InvoiceLineItemCreate]] = None

    @model_validator(mode='after')
    def validate_due_date(self):
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValueError('La fecha de vencimiento no puede ser anterior a la fecha de emisión')
        return self


class InvoiceOut(BaseModel):
    id: UUID
    pdv_id: UUID
    customer_id: UUID
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    number: Optional[str]
    type: InvoiceType
    status: InvoiceStatus
    issue_date: date
    due_date: Optional[date]
    notes: Optional[str]
    currency: str
    subtotal: Decimal
    taxes_total: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceDetail(InvoiceOut):
    """Esquema detallado que incluye customer (Contact), line items y payments"""
    # Use Contact module projection for customer details
    customer: ContactForInvoice
    line_items: List[InvoiceLineItemOut]
    payments: List['PaymentOut'] = []

    class Config:
        from_attributes = True


class InvoiceList(BaseModel):
    invoices: List[InvoiceOut]
    total: int
    limit: int
    offset: int
    # Nuevos campos para reflejar filtros aplicados y métricas por estado
    applied_filters: Optional['InvoiceFilters'] = None
    counts_by_status: List['InvoiceStatusCount'] = Field(default_factory=list)


class InvoiceStatusCount(BaseModel):
    status: InvoiceStatus
    count: int


# Payment Schemas
class PaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Monto debe ser mayor a 0")
    method: PaymentMethod
    reference: Optional[str] = Field(None, max_length=100)
    payment_date: date = Field(default_factory=date.today)
    notes: Optional[str] = None

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('El monto del pago debe ser mayor a 0')
        return v


class PaymentOut(BaseModel):
    id: UUID
    invoice_id: UUID
    created_by: UUID
    amount: Decimal
    method: PaymentMethod
    reference: Optional[str]
    payment_date: date
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentList(BaseModel):
    payments: List[PaymentOut]
    total: int


# Tax Calculation Schemas (para mostrar discriminación de impuestos)
class InvoiceTaxSummary(BaseModel):
    """Resumen de impuestos discriminados en la factura"""
    tax_id: UUID
    tax_name: str
    tax_rate: Decimal
    taxable_amount: Decimal  # Base gravable
    tax_amount: Decimal      # Valor del impuesto


class InvoiceTotals(BaseModel):
    """Totales calculados de la factura"""
    subtotal: Decimal
    taxes: List[InvoiceTaxSummary]
    taxes_total: Decimal
    total_amount: Decimal


# Preview y Email Schemas
class InvoicePreview(BaseModel):
    """Esquema para generar preview PDF"""
    template: Optional[str] = "default"
    include_taxes: bool = True
    include_payments: bool = True


class InvoiceEmail(BaseModel):
    """Esquema para envío por email"""
    recipient_email: Optional[str] = None  # Si no se proporciona, usa el del customer
    subject: Optional[str] = None
    message: Optional[str] = None
    include_pdf: bool = True


# Search y Filter Schemas
class InvoiceFilters(BaseModel):
    """Filtros para búsqueda de facturas"""
    status: Optional[InvoiceStatus] = None
    customer_id: Optional[UUID] = None
    pdv_id: Optional[UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    search: Optional[str] = Field(None, description="Buscar en número, nombre del cliente o notas")


# Email Response Schema
class InvoiceEmailResponse(BaseModel):
    """Respuesta del envío de email de factura"""
    status: str = Field(..., description="Estado del envío: 'queued', 'success', 'failed'")
    task_id: Optional[str] = Field(None, description="ID de la tarea de Celery")
    message: str = Field(..., description="Mensaje descriptivo del resultado")


# Validation Response Schemas
class StockValidation(BaseModel):
    """Resultado de validación de stock"""
    product_id: UUID
    product_name: str
    requested_quantity: Decimal
    available_quantity: Decimal
    is_sufficient: bool


class InvoiceValidation(BaseModel):
    """Resultado completo de validación de factura"""
    is_valid: bool
    stock_validations: List[StockValidation]
    errors: List[str] = []
    warnings: List[str] = []


# Esquemas adicionales para los routers

class CustomerList(BaseModel):
    items: List[CustomerOut]
    total: int
    limit: int
    offset: int


class InvoiceCancelRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class InvoiceEmailRequest(BaseModel):
    to_email: str = Field(..., min_length=1, max_length=100, description="Email del destinatario")
    subject: Optional[str] = Field(None, max_length=200, description="Asunto personalizado del email")
    message: Optional[str] = Field(None, max_length=1000, description="Mensaje adicional en el email")
    pdf_filename: str = Field(..., min_length=1, max_length=255, description="Nombre del archivo PDF")

    @field_validator('to_email')
    @classmethod
    def validate_email(cls, v):
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Email inválido')
        return v


class SalesSummary(BaseModel):
    period_start: date
    period_end: date
    total_invoices: int
    total_amount: Decimal
    total_tax: Decimal
    pending_amount: Decimal
    paid_amount: Decimal
    cancelled_amount: Decimal
    top_products: List[Dict[str, Any]]
    daily_sales: List[Dict[str, Any]]


class NextInvoiceNumber(BaseModel):
    next_number: str
    prefix: str
    current_sequence: int


# Forward reference resolution
InvoiceDetail.model_rebuild()


# ===== Monthly Status Summary =====

class MonthlyStatusMetrics(BaseModel):
    """Métricas por estado para un período mensual"""
    count: int
    recaudado: Decimal


class InvoicesMonthlySummary(BaseModel):
    """Resumen mensual de facturas agrupado por estado"""
    year: int
    month: int
    total: MonthlyStatusMetrics
    open: MonthlyStatusMetrics
    paid: MonthlyStatusMetrics
    void: MonthlyStatusMetrics

# Rebuild models with forward references for runtime
InvoiceList.model_rebuild()