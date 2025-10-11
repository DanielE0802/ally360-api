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
    QR_CODE = "qr_code"  # ← NUEVO
    OTHER = "other"


class QRPaymentProvider(str, Enum):  # ← NUEVO
    """Proveedores de pago QR soportados"""
    NEQUI = "nequi"
    DAVIPLATA = "daviplata"
    BANCOLOMBIA_QR = "bancolombia_qr"
    PSE = "pse"
    GENERIC_QR = "generic_qr"


class PaymentStatus(str, Enum):  # ← NUEVO
    """Estados de procesamiento de pagos"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


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
    seller_id: Optional[UUID] = Field(None, description="ID del vendedor responsable de la caja")


class CashRegisterClose(BaseModel):
    """Esquema para cerrar caja registradora"""
    closing_balance: Decimal = Field(..., ge=0, description="Saldo final declarado")
    closing_notes: Optional[str] = Field(None, max_length=500, description="Notas de cierre")


class CashRegisterOut(BaseModel):
    """Esquema de salida para caja registradora"""
    id: UUID = Field(description="ID único de la caja")
    pdv_id: UUID = Field(description="ID del PDV")
    seller_id: Optional[UUID] = Field(None, description="ID del vendedor responsable")
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
    seller_name: Optional[str] = Field(None, description="Nombre del vendedor responsable")
    seller_email: Optional[str] = Field(None, description="Email del vendedor")
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


# ===== ADVANCED PAYMENT SCHEMAS =====

class MixedPaymentItem(BaseModel):
    """Schema para un pago individual en pago mixto"""
    method: PaymentMethod = Field(..., description="Método de pago")
    amount: Decimal = Field(..., gt=0, description="Monto del pago")
    reference: Optional[str] = Field(None, max_length=100, description="Referencia del pago")
    notes: Optional[str] = Field(None, max_length=200, description="Notas del pago")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('El monto debe ser mayor a cero')
        return v


class MixedPaymentRequest(BaseModel):
    """Schema para solicitud de pago mixto"""
    invoice_id: UUID = Field(..., description="ID de la factura a pagar")
    payments: List[MixedPaymentItem] = Field(..., min_length=1, description="Lista de pagos")
    cash_register_id: Optional[UUID] = Field(None, description="ID de caja (requerido si hay efectivo)")

    @field_validator('payments')
    @classmethod
    def validate_payments(cls, v: List[MixedPaymentItem]) -> List[MixedPaymentItem]:
        if not v:
            raise ValueError('Debe incluir al menos un pago')
        
        # Validar que si hay efectivo, se proporcione cash_register_id
        has_cash = any(p.method == PaymentMethod.CASH for p in v)
        return v

    @model_validator(mode='after')
    def validate_cash_register(self):
        has_cash = any(p.method == PaymentMethod.CASH for p in self.payments)
        if has_cash and not self.cash_register_id:
            raise ValueError('cash_register_id es requerido cuando hay pagos en efectivo')
        return self


class MixedPaymentResponse(BaseModel):
    """Schema de respuesta para pago mixto"""
    invoice_id: str = Field(description="ID de la factura pagada")
    total_amount: float = Field(description="Total de la factura")
    total_paid: float = Field(description="Total pagado")
    change_amount: float = Field(description="Vuelto dado")
    payments: List[Dict[str, Any]] = Field(description="Pagos procesados")
    cash_movements: List[Dict[str, Any]] = Field(description="Movimientos de caja generados")
    payment_summary: Dict[str, Any] = Field(description="Resumen por método de pago")


class QRPaymentRequest(BaseModel):
    """Schema para solicitud de pago QR"""
    invoice_id: UUID = Field(..., description="ID de la factura")
    amount: Decimal = Field(..., gt=0, description="Monto a pagar")
    provider: QRPaymentProvider = Field(..., description="Proveedor de pago QR")
    expires_in_minutes: int = Field(30, ge=5, le=120, description="Minutos de expiración")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('El monto debe ser mayor a cero')
        return v


class QRPaymentResponse(BaseModel):
    """Schema de respuesta para pago QR"""
    qr_code: str = Field(description="Código único del QR")
    qr_data: str = Field(description="Datos del QR para generar imagen")
    amount: float = Field(description="Monto a pagar")
    provider: str = Field(description="Proveedor de pago")
    invoice_id: str = Field(description="ID de la factura")
    expires_at: str = Field(description="Fecha de expiración ISO")
    status: str = Field(description="Estado del pago")
    created_at: str = Field(description="Fecha de creación ISO")
    instructions: Dict[str, Any] = Field(description="Instrucciones específicas del proveedor")


class QRPaymentStatusRequest(BaseModel):
    """Schema para consultar estado de pago QR"""
    qr_code: str = Field(..., min_length=8, max_length=20, description="Código del QR")


class QRPaymentStatusResponse(BaseModel):
    """Schema de respuesta de estado de pago QR"""
    qr_code: str = Field(description="Código del QR")
    status: str = Field(description="Estado actual del pago")
    last_check: str = Field(description="Última verificación ISO")
    message: str = Field(description="Mensaje del estado")


# Schemas para validación de métodos de pago
class PaymentValidationResponse(BaseModel):
    """Respuesta de validación de límites de pago"""
    valid: bool
    method: PaymentMethod
    amount: Decimal
    limit_exceeded: bool = False
    daily_limit: Optional[Decimal] = None
    current_daily_usage: Optional[Decimal] = None
    remaining_daily_limit: Optional[Decimal] = None
    warnings: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


# ===============================
# MULTI-CASH SCHEMAS (v1.3.0)
# ===============================

class MultiCashSessionCreate(BaseModel):
    """Schema para crear sesión multi-caja"""
    location_id: UUID = Field(description="ID del PDV/Ubicación")
    primary_balance: Decimal = Field(ge=0, description="Saldo inicial caja principal")
    secondary_balances: List[Decimal] = Field(
        description="Saldos iniciales para cajas secundarias",
        min_length=1,
        max_length=5
    )
    session_notes: Optional[str] = Field(None, max_length=500, description="Notas de la sesión")
    enable_load_balancing: bool = Field(True, description="Habilitar balanceamento automático")
    allow_existing: bool = Field(False, description="Permitir cajas abiertas existentes")
    
    @field_validator('secondary_balances')
    @classmethod
    def validate_secondary_balances(cls, v):
        if any(balance < 0 for balance in v):
            raise ValueError("Todos los saldos deben ser no negativos")
        return v

class MultiCashSessionResponse(BaseModel):
    """Respuesta de sesión multi-caja creada"""
    session_id: UUID
    location_id: UUID
    primary_register: CashRegisterOut
    secondary_registers: List[CashRegisterOut]
    supervisor_id: UUID
    created_at: datetime
    status: str = Field(description="active, paused, closed")
    load_balancing_enabled: bool
    total_registers: int
    
    class Config:
        from_attributes = True

class LoadBalancingConfig(BaseModel):
    """Configuración de balanceamento de carga"""
    enabled: bool = True
    algorithm: str = Field("round_robin", description="round_robin, least_loaded, sales_based")
    max_sales_per_register: Optional[int] = Field(None, description="Máximo ventas por caja")
    balance_threshold: Optional[Decimal] = Field(None, description="Umbral de balance para rebalanceo")
    
class ShiftTransferRequest(BaseModel):
    """Request para transferencia de turno"""
    location_id: UUID
    register_ids: List[UUID] = Field(min_length=1, description="IDs de cajas a transferir")
    new_operator_id: UUID = Field(description="ID del nuevo operador")
    notes: Optional[str] = Field(None, max_length=500, description="Notas de transferencia")
    
class ShiftTransferResponse(BaseModel):
    """Respuesta de transferencia de turno"""
    transfer_id: UUID
    location_id: UUID
    from_user_id: UUID
    to_user_id: UUID
    transferred_registers: List[Dict[str, Any]]
    transfer_time: datetime
    notes: Optional[str]
    status: str = Field(description="completed, pending, failed")
    
    class Config:
        from_attributes = True

class RegisterCloseData(BaseModel):
    """Datos de cierre de caja individual"""
    register_id: UUID
    declared_balance: Decimal = Field(ge=0, description="Balance declarado en arqueo")
    notes: Optional[str] = Field(None, max_length=500, description="Notas del cierre")

class MultiCashSessionClose(BaseModel):
    """Request para cerrar sesión multi-caja"""
    session_id: UUID
    register_closures: List[RegisterCloseData] = Field(min_length=1)
    final_notes: Optional[str] = Field(None, max_length=1000, description="Notas finales de sesión")
    
class ConsolidatedAuditResponse(BaseModel):
    """Respuesta de auditoría consolidada"""
    audit_id: UUID
    location_id: UUID
    audit_date: date
    registers_audited: int
    total_opening_balance: Decimal
    total_current_balance: Decimal
    total_movements: int
    total_sales_count: int
    total_sales_amount: Decimal
    average_ticket: Decimal
    registers_detail: List[Dict[str, Any]]
    recommendations: List[str]
    audit_performed_by: Optional[UUID]
    audit_performed_at: datetime
    
    class Config:
        from_attributes = True


# ===============================
# REAL-TIME ANALYTICS SCHEMAS (v1.3.0)
# ===============================

class LiveDashboardResponse(BaseModel):
    """Respuesta del dashboard en tiempo real"""
    timestamp: datetime
    location_id: Optional[UUID]
    today_sales: Dict[str, Any]
    current_hour_sales: Dict[str, Any]
    active_registers: int
    registers_detail: List[Dict[str, Any]]
    hourly_breakdown: List[Dict[str, Any]]
    top_products_today: List[Dict[str, Any]]
    comparisons: Dict[str, Dict[str, Any]]
    alerts: List['AlertResponse']
    performance_indicators: Dict[str, Any]
    
    class Config:
        from_attributes = True

class AlertResponse(BaseModel):
    """Respuesta de alerta del sistema"""
    alert_id: UUID
    type: str = Field(description="stock, sales, cash, system")
    priority: str = Field(description="low, medium, high, critical")
    title: str
    message: str
    location_id: Optional[UUID]
    entity_id: Optional[UUID] = Field(None, description="ID de la entidad relacionada")
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class SalesTargetCheck(BaseModel):
    """Verificación de metas de ventas"""
    check_date: date
    location_id: Optional[UUID]
    daily_progress: Optional[Dict[str, Any]]
    monthly_progress: Optional[Dict[str, Any]]
    recommendations: List[str]
    
    class Config:
        from_attributes = True

class PredictiveAnalyticsResponse(BaseModel):
    """Respuesta de analytics predictivo"""
    prediction_date: datetime
    prediction_period_days: int
    location_id: Optional[UUID]
    sales_forecast: List[Dict[str, Any]]
    trend_analysis: Dict[str, Any]
    seasonal_patterns: Dict[str, Any]
    stock_alerts: List[Dict[str, Any]]
    demand_forecast: List[Dict[str, Any]]
    confidence_level: float = Field(ge=0, le=1, description="Nivel de confianza de las predicciones")
    recommendations: List[str]
    
    class Config:
        from_attributes = True

class LiveMetricsResponse(BaseModel):
    """Respuesta de métricas en vivo"""
    timestamp: datetime
    location_id: Optional[UUID]
    current_sales_count: int
    current_revenue: Decimal
    active_registers: int
    sales_velocity: float = Field(description="Ventas por hora")
    conversion_rate: Optional[float] = Field(None, description="Tasa de conversión estimada")
    average_ticket: Decimal
    peak_hour: Optional[int] = Field(None, description="Hora pico del día")
    
    class Config:
        from_attributes = True

class ComparativeAnalyticsResponse(BaseModel):
    """Respuesta de analytics comparativo"""
    comparison_period: str = Field(description="day, week, month, year")
    period_name: str
    current_period: Dict[str, Any]
    previous_period: Dict[str, Any]
    changes: Dict[str, Any]
    analysis: List[str]
    
    class Config:
        from_attributes = True