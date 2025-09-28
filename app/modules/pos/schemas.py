"""
Esquemas Pydantic para el módulo POS (Point of Sale)

Define la validación de datos de entrada y salida para:
- CashRegister: Cajas registradoras con apertura/cierre
- CashMovement: Movimientos de caja
- Seller: Vendedores para ventas POS
- POSInvoice: Facturas de punto de venta

Todas las validaciones respetan la arquitectura multi-tenant.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime
from enum import Enum


# ===== ENUMS =====

class CashRegisterStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class MovementType(str, Enum):
    SALE = "sale"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    EXPENSE = "expense"
    ADJUSTMENT = "adjustment"


class PaymentMethod(str, Enum):
    CASH = "cash"
    TRANSFER = "transfer"
    CARD = "card"
    OTHER = "other"


# ===== CASH REGISTER SCHEMAS =====

class CashRegisterCreate(BaseModel):
    """Esquema para crear caja registradora"""
    name: str = Field(..., min_length=1, max_length=100, description="Nombre de la caja")
    opening_balance: Decimal = Field(default=Decimal("0"), ge=0, description="Saldo inicial")
    opening_notes: Optional[str] = Field(None, max_length=500, description="Notas de apertura")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('El nombre no puede estar vacío')
        return cleaned


class CashRegisterOpen(BaseModel):
    """Esquema para abrir caja registradora"""
    opening_balance: Decimal = Field(..., ge=0, description="Saldo inicial de apertura")
    opening_notes: Optional[str] = Field(None, max_length=500, description="Notas de apertura")


class CashRegisterClose(BaseModel):
    """Esquema para cerrar caja registradora"""
    closing_balance: Decimal = Field(..., ge=0, description="Saldo final declarado")
    closing_notes: Optional[str] = Field(None, max_length=500, description="Notas de cierre")


class CashRegisterOut(BaseModel):
    """Esquema de salida para caja registradora"""
    id: UUID = Field(description="ID único de la caja")
    pdv_id: UUID = Field(description="ID del PDV")
    name: str = Field(description="Nombre de la caja")
    status: CashRegisterStatus = Field(description="Estado de la caja")
    opening_balance: Decimal = Field(description="Saldo de apertura")
    closing_balance: Optional[Decimal] = Field(None, description="Saldo de cierre")
    opened_by: UUID = Field(description="Usuario que abrió la caja")
    closed_by: Optional[UUID] = Field(None, description="Usuario que cerró la caja")
    opened_at: datetime = Field(description="Fecha y hora de apertura")
    closed_at: Optional[datetime] = Field(None, description="Fecha y hora de cierre")
    opening_notes: Optional[str] = Field(None, description="Notas de apertura")
    closing_notes: Optional[str] = Field(None, description="Notas de cierre")
    created_at: datetime = Field(description="Fecha de creación")
    updated_at: datetime = Field(description="Fecha de actualización")

    model_config = {"from_attributes": True}


class CashRegisterDetail(CashRegisterOut):
    """Esquema detallado de caja registradora con movimientos"""
    # Información adicional
    pdv_name: Optional[str] = Field(None, description="Nombre del PDV")
    opened_by_name: Optional[str] = Field(None, description="Nombre del usuario que abrió")
    closed_by_name: Optional[str] = Field(None, description="Nombre del usuario que cerró")
    
    # Cálculos
    calculated_balance: Decimal = Field(description="Balance calculado basado en movimientos")
    difference: Optional[Decimal] = Field(None, description="Diferencia entre declarado y calculado")
    total_sales: Decimal = Field(description="Total de ventas")
    total_deposits: Decimal = Field(description="Total de depósitos")
    total_withdrawals: Decimal = Field(description="Total de retiros")
    total_expenses: Decimal = Field(description="Total de gastos")
    total_adjustments: Decimal = Field(description="Total de ajustes")
    
    # Movimientos (opcional, se puede cargar bajo demanda)
    movements: List['CashMovementOut'] = Field(default=[], description="Movimientos de la caja")


class CashRegisterList(BaseModel):
    """Esquema para lista de cajas registradoras"""
    cash_registers: List[CashRegisterOut] = Field(description="Lista de cajas")
    total: int = Field(description="Total de cajas")
    limit: int = Field(description="Límite aplicado")
    offset: int = Field(description="Offset aplicado")


# ===== CASH MOVEMENT SCHEMAS =====

class CashMovementCreate(BaseModel):
    """Esquema para crear movimiento de caja"""
    cash_register_id: UUID = Field(..., description="ID de la caja registradora")
    type: MovementType = Field(..., description="Tipo de movimiento")
    amount: Decimal = Field(..., gt=0, description="Monto del movimiento (siempre positivo)")
    reference: Optional[str] = Field(None, max_length=100, description="Referencia opcional")
    notes: Optional[str] = Field(None, max_length=500, description="Notas del movimiento")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('El monto debe ser mayor a cero')
        return v
    
    # Validación especial para ajustes que pueden ser negativos
    @model_validator(mode='after')
    def validate_adjustment(self):
        if self.type == MovementType.ADJUSTMENT:
            # Para ajustes, permitir montos negativos usando el signo en notas
            # o manejarlo de forma especial en el service
            pass
        return self


class CashMovementOut(BaseModel):
    """Esquema de salida para movimiento de caja"""
    id: UUID = Field(description="ID único del movimiento")
    cash_register_id: UUID = Field(description="ID de la caja registradora")
    type: MovementType = Field(description="Tipo de movimiento")
    amount: Decimal = Field(description="Monto del movimiento")
    signed_amount: Decimal = Field(description="Monto con signo según tipo")
    reference: Optional[str] = Field(None, description="Referencia")
    notes: Optional[str] = Field(None, description="Notas")
    invoice_id: Optional[UUID] = Field(None, description="ID de factura relacionada")
    created_by: UUID = Field(description="Usuario que creó el movimiento")
    created_at: datetime = Field(description="Fecha de creación")
    
    # Información adicional
    created_by_name: Optional[str] = Field(None, description="Nombre del usuario")
    invoice_number: Optional[str] = Field(None, description="Número de factura")

    model_config = {"from_attributes": True}


class CashMovementList(BaseModel):
    """Esquema para lista de movimientos de caja"""
    movements: List[CashMovementOut] = Field(description="Lista de movimientos")
    summary: Dict[str, Any] = Field(description="Resumen de movimientos")
    total: int = Field(description="Total de movimientos")
    limit: int = Field(description="Límite aplicado")
    offset: int = Field(description="Offset aplicado")


# ===== SELLER SCHEMAS =====

class SellerCreate(BaseModel):
    """Esquema para crear vendedor"""
    name: str = Field(..., min_length=1, max_length=200, description="Nombre del vendedor")
    email: Optional[str] = Field(None, max_length=100, description="Email del vendedor")
    phone: Optional[str] = Field(None, max_length=50, description="Teléfono del vendedor")
    document: Optional[str] = Field(None, max_length=50, description="Documento de identidad")
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Tasa de comisión (0-1)")
    base_salary: Optional[Decimal] = Field(None, ge=0, description="Salario base")
    notes: Optional[str] = Field(None, max_length=500, description="Notas adicionales")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('El nombre no puede estar vacío')
        return cleaned
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if v:
            # Validación básica de email
            if '@' not in v or '.' not in v:
                raise ValueError('Email inválido')
        return v


class SellerUpdate(BaseModel):
    """Esquema para actualizar vendedor"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Nombre del vendedor")
    email: Optional[str] = Field(None, max_length=100, description="Email del vendedor")
    phone: Optional[str] = Field(None, max_length=50, description="Teléfono del vendedor")
    document: Optional[str] = Field(None, max_length=50, description="Documento de identidad")
    is_active: Optional[bool] = Field(None, description="Estado activo/inactivo")
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Tasa de comisión")
    base_salary: Optional[Decimal] = Field(None, ge=0, description="Salario base")
    notes: Optional[str] = Field(None, max_length=500, description="Notas adicionales")


class SellerOut(BaseModel):
    """Esquema de salida para vendedor"""
    id: UUID = Field(description="ID único del vendedor")
    name: str = Field(description="Nombre del vendedor")
    email: Optional[str] = Field(None, description="Email del vendedor")
    phone: Optional[str] = Field(None, description="Teléfono del vendedor")
    document: Optional[str] = Field(None, description="Documento de identidad")
    is_active: bool = Field(description="Estado activo/inactivo")
    commission_rate: Optional[Decimal] = Field(None, description="Tasa de comisión")
    base_salary: Optional[Decimal] = Field(None, description="Salario base")
    notes: Optional[str] = Field(None, description="Notas adicionales")
    created_at: datetime = Field(description="Fecha de creación")
    updated_at: datetime = Field(description="Fecha de actualización")

    model_config = {"from_attributes": True}


class SellerList(BaseModel):
    """Esquema para lista de vendedores"""
    sellers: List[SellerOut] = Field(description="Lista de vendedores")
    total: int = Field(description="Total de vendedores")
    limit: int = Field(description="Límite aplicado")
    offset: int = Field(description="Offset aplicado")


# ===== POS INVOICE SCHEMAS =====

class POSPaymentCreate(BaseModel):
    """Esquema para pagos en ventas POS"""
    method: PaymentMethod = Field(..., description="Método de pago")
    amount: Decimal = Field(..., gt=0, description="Monto del pago")
    reference: Optional[str] = Field(None, max_length=100, description="Referencia del pago")
    notes: Optional[str] = Field(None, max_length=200, description="Notas del pago")


class POSLineItemCreate(BaseModel):
    """Esquema para ítems de venta POS"""
    product_id: UUID = Field(..., description="ID del producto")
    quantity: Decimal = Field(..., gt=0, description="Cantidad")
    unit_price: Optional[Decimal] = Field(None, gt=0, description="Precio unitario (opcional, se toma del producto)")
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('La cantidad debe ser mayor a cero')
        return v


class POSInvoiceCreate(BaseModel):
    """Esquema para crear venta POS"""
    customer_id: UUID = Field(..., description="ID del cliente")
    seller_id: UUID = Field(..., description="ID del vendedor")
    items: List[POSLineItemCreate] = Field(..., min_length=1, description="Ítems de la venta")
    payments: List[POSPaymentCreate] = Field(..., min_length=1, description="Pagos de la venta")
    notes: Optional[str] = Field(None, max_length=500, description="Notas de la venta")
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[POSLineItemCreate]) -> List[POSLineItemCreate]:
        if not v:
            raise ValueError('Debe incluir al menos un ítem')
        return v
    
    @field_validator('payments')
    @classmethod
    def validate_payments(cls, v: List[POSPaymentCreate]) -> List[POSPaymentCreate]:
        if not v:
            raise ValueError('Debe incluir al menos un pago')
        return v


class POSInvoiceOut(BaseModel):
    """Esquema de salida para venta POS"""
    id: UUID = Field(description="ID de la factura")
    pdv_id: UUID = Field(description="ID del PDV")
    customer_id: UUID = Field(description="ID del cliente")
    seller_id: UUID = Field(description="ID del vendedor")
    number: Optional[str] = Field(None, description="Número de factura")
    status: str = Field(description="Estado de la factura")
    issue_date: date = Field(description="Fecha de emisión")
    notes: Optional[str] = Field(None, description="Notas")
    currency: str = Field(description="Moneda")
    subtotal: Decimal = Field(description="Subtotal")
    taxes_total: Decimal = Field(description="Total de impuestos")
    total_amount: Decimal = Field(description="Monto total")
    paid_amount: Decimal = Field(description="Monto pagado")
    balance_due: Decimal = Field(description="Saldo pendiente")
    created_at: datetime = Field(description="Fecha de creación")
    updated_at: datetime = Field(description="Fecha de actualización")
    
    # Información adicional
    customer_name: Optional[str] = Field(None, description="Nombre del cliente")
    seller_name: Optional[str] = Field(None, description="Nombre del vendedor")
    pdv_name: Optional[str] = Field(None, description="Nombre del PDV")

    model_config = {"from_attributes": True}


class POSInvoiceDetail(POSInvoiceOut):
    """Esquema detallado de venta POS"""
    # Relaciones expandidas
    line_items: List[Dict[str, Any]] = Field(description="Ítems de la factura")
    payments: List[Dict[str, Any]] = Field(description="Pagos de la factura")
    cash_movements: List[CashMovementOut] = Field(default=[], description="Movimientos de caja generados")


# Forward references
CashRegisterDetail.model_rebuild()