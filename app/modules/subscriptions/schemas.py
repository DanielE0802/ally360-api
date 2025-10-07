"""
Pydantic schemas for subscription management.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Estados de suscripción."""
    TRIAL = "trial"
    ACTIVE = "active"
    CANCELED = "canceled"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class PlanType(str, Enum):
    """Tipos de planes."""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class BillingCycle(str, Enum):
    """Ciclos de facturación."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


# ===== PLAN SCHEMAS =====

class PlanBase(BaseModel):
    """Schema base para planes."""
    name: str = Field(..., description="Nombre del plan")
    code: str = Field(..., description="Código único del plan")
    type: PlanType = Field(default=PlanType.FREE, description="Tipo de plan")
    description: Optional[str] = Field(None, description="Descripción del plan")
    monthly_price: Decimal = Field(default=0, description="Precio mensual")
    yearly_price: Decimal = Field(default=0, description="Precio anual")


class PlanCreate(PlanBase):
    """Schema para crear plan."""
    max_users: Optional[int] = Field(None, description="Máximo número de usuarios")
    max_pdvs: Optional[int] = Field(None, description="Máximo número de PDVs")
    max_products: Optional[int] = Field(None, description="Máximo número de productos")
    max_storage_gb: Optional[int] = Field(None, description="Máximo almacenamiento en GB")
    max_invoices_month: Optional[int] = Field(None, description="Máximo facturas por mes")
    has_advanced_reports: bool = Field(default=False)
    has_api_access: bool = Field(default=False)
    has_multi_currency: bool = Field(default=False)
    has_inventory_alerts: bool = Field(default=False)
    has_email_support: bool = Field(default=True)
    has_phone_support: bool = Field(default=False)
    has_priority_support: bool = Field(default=False)
    is_popular: bool = Field(default=False)
    sort_order: int = Field(default=0)


class PlanUpdate(BaseModel):
    """Schema para actualizar plan."""
    name: Optional[str] = None
    description: Optional[str] = None
    monthly_price: Optional[Decimal] = None
    yearly_price: Optional[Decimal] = None
    max_users: Optional[int] = None
    max_pdvs: Optional[int] = None
    max_products: Optional[int] = None
    max_storage_gb: Optional[int] = None
    max_invoices_month: Optional[int] = None
    has_advanced_reports: Optional[bool] = None
    has_api_access: Optional[bool] = None
    has_multi_currency: Optional[bool] = None
    has_inventory_alerts: Optional[bool] = None
    has_email_support: Optional[bool] = None
    has_phone_support: Optional[bool] = None
    has_priority_support: Optional[bool] = None
    is_active: Optional[bool] = None
    is_popular: Optional[bool] = None
    sort_order: Optional[int] = None


class PlanOut(PlanBase):
    """Schema de salida para planes."""
    id: UUID
    max_users: Optional[int]
    max_pdvs: Optional[int]
    max_products: Optional[int]
    max_storage_gb: Optional[int]
    max_invoices_month: Optional[int]
    has_advanced_reports: bool
    has_api_access: bool
    has_multi_currency: bool
    has_inventory_alerts: bool
    has_email_support: bool
    has_phone_support: bool
    has_priority_support: bool
    is_active: bool
    is_popular: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanSummary(BaseModel):
    """Schema resumido para planes."""
    id: UUID
    name: str
    code: str
    type: PlanType
    monthly_price: Decimal
    yearly_price: Decimal
    is_popular: bool

    class Config:
        from_attributes = True


# ===== SUBSCRIPTION SCHEMAS =====

class SubscriptionBase(BaseModel):
    """Schema base para suscripciones."""
    plan_id: UUID = Field(..., description="ID del plan")
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)
    auto_renew: bool = Field(default=True)


class SubscriptionCreate(SubscriptionBase):
    """Schema para crear suscripción."""
    start_date: Optional[datetime] = Field(None, description="Fecha de inicio")
    end_date: Optional[datetime] = Field(None, description="Fecha de fin")
    trial_end_date: Optional[datetime] = Field(None, description="Fin del período de prueba")
    amount: Optional[Decimal] = Field(None, description="Monto a pagar")
    currency: str = Field(default="COP", description="Moneda")
    notes: Optional[str] = Field(None, description="Notas administrativas")


class SubscriptionUpdate(BaseModel):
    """Schema para actualizar suscripción."""
    plan_id: Optional[UUID] = None
    status: Optional[SubscriptionStatus] = None
    billing_cycle: Optional[BillingCycle] = None
    end_date: Optional[datetime] = None
    auto_renew: Optional[bool] = None
    notes: Optional[str] = None


class SubscriptionCancel(BaseModel):
    """Schema para cancelar suscripción."""
    reason: str = Field(..., description="Motivo de cancelación")
    cancel_immediately: bool = Field(default=False, description="Cancelar inmediatamente o al final del período")


class SubscriptionOut(SubscriptionBase):
    """Schema de salida para suscripciones."""
    id: UUID
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime]
    trial_end_date: Optional[datetime]
    canceled_at: Optional[datetime]
    amount: Decimal
    currency: str
    next_billing_date: Optional[datetime]
    is_current: bool
    notes: Optional[str]
    canceled_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # Propiedades calculadas
    is_active: bool = Field(..., description="Si la suscripción está activa")
    is_trial: bool = Field(..., description="Si está en período de prueba")
    days_remaining: int = Field(..., description="Días restantes (-1 si es indefinido)")

    class Config:
        from_attributes = True


class SubscriptionDetail(SubscriptionOut):
    """Schema detallado con información del plan."""
    plan: PlanOut

    class Config:
        from_attributes = True


class SubscriptionCurrent(BaseModel):
    """Schema para suscripción actual simplificada."""
    id: UUID
    plan_name: str
    plan_code: str
    plan_type: PlanType
    status: SubscriptionStatus
    billing_cycle: BillingCycle
    is_trial: bool
    days_remaining: int
    next_billing_date: Optional[datetime]
    
    # Límites actuales
    max_users: Optional[int]
    max_pdvs: Optional[int]
    max_products: Optional[int]
    max_storage_gb: Optional[int]
    max_invoices_month: Optional[int]
    
    # Features
    has_advanced_reports: bool
    has_api_access: bool
    has_multi_currency: bool
    has_inventory_alerts: bool

    class Config:
        from_attributes = True


# ===== LIST SCHEMAS =====

class PlanList(BaseModel):
    """Schema para lista de planes."""
    plans: List[PlanOut]
    total: int

    class Config:
        from_attributes = True


class SubscriptionList(BaseModel):
    """Schema para lista de suscripciones."""
    subscriptions: List[SubscriptionOut]
    total: int
    limit: int
    offset: int

    class Config:
        from_attributes = True


# ===== RESPONSE SCHEMAS =====

class SubscriptionCreateResponse(BaseModel):
    """Respuesta de creación de suscripción."""
    subscription: SubscriptionDetail
    message: str
    is_upgrade: bool = Field(description="Si es una actualización de plan")

    class Config:
        from_attributes = True