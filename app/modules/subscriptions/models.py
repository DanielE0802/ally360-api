"""
Models for subscription management.
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database.database import Base
from app.common.mixins import TenantMixin
import uuid
from datetime import datetime
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


class Plan(Base):
    """
    Modelo para planes de suscripción.
    Planes predefinidos del sistema.
    """
    __tablename__ = "plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)  # basic, professional, etc.
    type = Column(String(20), nullable=False, default=PlanType.FREE)
    description = Column(Text, nullable=True)
    
    # Precios
    monthly_price = Column(DECIMAL(10, 2), nullable=False, default=0)
    yearly_price = Column(DECIMAL(10, 2), nullable=False, default=0)
    
    # Límites del plan
    max_users = Column(Integer, nullable=True)  # null = ilimitado
    max_pdvs = Column(Integer, nullable=True)
    max_products = Column(Integer, nullable=True)
    max_storage_gb = Column(Integer, nullable=True)
    max_invoices_month = Column(Integer, nullable=True)
    
    # Features
    has_advanced_reports = Column(Boolean, default=False)
    has_api_access = Column(Boolean, default=False)
    has_multi_currency = Column(Boolean, default=False)
    has_inventory_alerts = Column(Boolean, default=False)
    has_email_support = Column(Boolean, default=True)
    has_phone_support = Column(Boolean, default=False)
    has_priority_support = Column(Boolean, default=False)
    
    # Configuración
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relaciones
    subscriptions = relationship("Subscription", back_populates="plan")
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Subscription(Base, TenantMixin):
    """
    Modelo para suscripciones de empresas.
    Una empresa puede tener múltiples suscripciones (historial).
    """
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False, index=True)
    
    # Estado y fechas
    status = Column(String(20), nullable=False, default=SubscriptionStatus.TRIAL)
    billing_cycle = Column(String(20), nullable=False, default=BillingCycle.MONTHLY)
    
    # Fechas importantes
    start_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)  # null = indefinido
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    
    # Facturación
    amount = Column(DECIMAL(10, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="COP")
    next_billing_date = Column(DateTime(timezone=True), nullable=True)
    
    # Configuración
    auto_renew = Column(Boolean, default=True)
    is_current = Column(Boolean, default=True)  # Solo una suscripción activa por tenant
    
    # Notas administrativas
    notes = Column(Text, nullable=True)
    canceled_reason = Column(String(500), nullable=True)
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relaciones
    plan = relationship("Plan", back_populates="subscriptions")
    
    def __str__(self):
        return f"Subscription {self.plan.name} - {self.status}"
    
    @property
    def is_active(self) -> bool:
        """Verifica si la suscripción está activa."""
        if self.status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
            return False
        
        now = datetime.utcnow()
        if self.end_date and now > self.end_date:
            return False
            
        return True
    
    @property
    def is_trial(self) -> bool:
        """Verifica si está en período de prueba."""
        return self.status == SubscriptionStatus.TRIAL
    
    @property
    def days_remaining(self) -> int:
        """Días restantes de la suscripción."""
        if not self.end_date:
            return -1  # Indefinido
        
        now = datetime.utcnow()
        if now > self.end_date:
            return 0
        
        return (self.end_date - now).days