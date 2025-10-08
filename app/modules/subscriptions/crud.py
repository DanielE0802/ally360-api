"""
CRUD operations for subscription management.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, asc, or_, func
from sqlalchemy.orm import selectinload, joinedload

from .models import Plan, Subscription, SubscriptionStatus, PlanType, BillingCycle
from .schemas import (
    PlanCreate, PlanUpdate, 
    SubscriptionCreate, SubscriptionUpdate
)


# ===== PLAN CRUD =====

async def get_plan(db: AsyncSession, plan_id: UUID) -> Optional[Plan]:
    """Obtener un plan por ID."""
    result = await db.execute(
        select(Plan).where(
            and_(
                Plan.id == plan_id,
                Plan.is_active == True
            )
        )
    )
    return result.scalar_one_or_none()


async def get_plan_by_code(db: AsyncSession, code: str) -> Optional[Plan]:
    """Obtener un plan por código."""
    result = await db.execute(
        select(Plan).where(
            and_(
                Plan.code == code,
                Plan.is_active == True
            )
        )
    )
    return result.scalar_one_or_none()


async def get_plans(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    plan_type: Optional[PlanType] = None,
    active_only: bool = True
) -> List[Plan]:
    """Obtener lista de planes."""
    query = select(Plan)
    
    conditions = []
    if active_only:
        conditions.append(Plan.is_active == True)
    if plan_type:
        conditions.append(Plan.type == plan_type)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(asc(Plan.sort_order), asc(Plan.created_at))
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def create_plan(db: AsyncSession, plan_data: PlanCreate) -> Plan:
    """Crear nuevo plan."""
    plan = Plan(**plan_data.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_plan(db: AsyncSession, plan_id: UUID, plan_data: PlanUpdate) -> Optional[Plan]:
    """Actualizar plan."""
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    
    if not plan:
        return None
    
    update_data = plan_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)
    
    await db.commit()
    await db.refresh(plan)
    return plan


async def delete_plan(db: AsyncSession, plan_id: UUID) -> bool:
    """Desactivar plan (soft delete)."""
    result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    
    if not plan:
        return False
    
    plan.is_active = False
    await db.commit()
    return True


# ===== SUBSCRIPTION CRUD =====

async def get_subscription(
    db: AsyncSession, 
    subscription_id: UUID, 
    tenant_id: UUID
) -> Optional[Subscription]:
    """Obtener suscripción por ID."""
    result = await db.execute(
        select(Subscription)
        .options(joinedload(Subscription.plan))
        .where(
            and_(
                Subscription.id == subscription_id,
                Subscription.tenant_id == tenant_id
            )
        )
    )
    return result.scalar_one_or_none()


async def get_current_subscription(
    db: AsyncSession, 
    tenant_id: UUID
) -> Optional[Subscription]:
    """Obtener suscripción actual de un tenant."""
    result = await db.execute(
        select(Subscription)
        .options(joinedload(Subscription.plan))
        .where(
            and_(
                Subscription.tenant_id == tenant_id,
                Subscription.is_current == True
            )
        )
    )
    return result.scalar_one_or_none()


async def get_active_subscription(
    db: AsyncSession, 
    tenant_id: UUID
) -> Optional[Subscription]:
    """Obtener suscripción activa de un tenant."""
    result = await db.execute(
        select(Subscription)
        .options(joinedload(Subscription.plan))
        .where(
            and_(
                Subscription.tenant_id == tenant_id,
                Subscription.status.in_([
                    SubscriptionStatus.TRIAL,
                    SubscriptionStatus.ACTIVE
                ]),
                or_(
                    Subscription.end_date.is_(None),
                    Subscription.end_date > datetime.now(timezone.utc)
                )
            )
        )
        .order_by(desc(Subscription.created_at))
    )
    return result.scalar_one_or_none()


async def get_subscriptions(
    db: AsyncSession,
    tenant_id: UUID,
    skip: int = 0,
    limit: int = 20,
    status: Optional[SubscriptionStatus] = None
) -> List[Subscription]:
    """Obtener lista de suscripciones de un tenant."""
    query = select(Subscription).options(joinedload(Subscription.plan))
    
    conditions = [Subscription.tenant_id == tenant_id]
    if status:
        conditions.append(Subscription.status == status)
    
    query = query.where(and_(*conditions))
    query = query.order_by(desc(Subscription.created_at))
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def create_subscription(
    db: AsyncSession, 
    tenant_id: UUID, 
    subscription_data: SubscriptionCreate
) -> Subscription:
    """Crear nueva suscripción."""
    # Desactivar suscripción actual si existe
    await _deactivate_current_subscription(db, tenant_id)
    
    # Obtener el plan para calcular fechas y montos
    plan = await get_plan(db, subscription_data.plan_id)
    if not plan:
        raise ValueError("Plan no encontrado")
    
    # Calcular fechas y montos
    now = datetime.now(timezone.utc)
    start_date = subscription_data.start_date or now
    
    # Determinar si es trial
    status = SubscriptionStatus.TRIAL
    trial_end_date = subscription_data.trial_end_date
    
    if not trial_end_date and plan.type != PlanType.FREE:
        # Por defecto, 15 días de trial
        trial_end_date = start_date + timedelta(days=15)
    
    # Calcular fechas de fin
    if subscription_data.end_date:
        end_date = subscription_data.end_date
    elif plan.type == PlanType.FREE:
        end_date = None  # Plan gratuito no tiene fin
    else:
        # Calcular según ciclo de facturación
        if subscription_data.billing_cycle == BillingCycle.YEARLY:
            end_date = start_date + timedelta(days=365)
        else:
            end_date = start_date + timedelta(days=30)
    
    # Calcular monto
    if subscription_data.amount is not None:
        amount = subscription_data.amount
    else:
        if subscription_data.billing_cycle == BillingCycle.YEARLY:
            amount = plan.yearly_price
        else:
            amount = plan.monthly_price
    
    # Calcular próxima fecha de facturación
    next_billing_date = None
    if plan.type != PlanType.FREE and end_date:
        if trial_end_date and trial_end_date > now:
            next_billing_date = trial_end_date
        else:
            next_billing_date = end_date
    
    subscription = Subscription(
        tenant_id=tenant_id,
        plan_id=subscription_data.plan_id,
        status=status,
        billing_cycle=subscription_data.billing_cycle,
        start_date=start_date,
        end_date=end_date,
        trial_end_date=trial_end_date,
        amount=amount,
        currency=subscription_data.currency,
        next_billing_date=next_billing_date,
        auto_renew=subscription_data.auto_renew,
        is_current=True,
        notes=subscription_data.notes
    )
    
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    
    # Cargar el plan
    await db.refresh(subscription, ["plan"])
    
    return subscription


async def update_subscription(
    db: AsyncSession, 
    subscription_id: UUID, 
    tenant_id: UUID, 
    subscription_data: SubscriptionUpdate
) -> Optional[Subscription]:
    """Actualizar suscripción."""
    result = await db.execute(
        select(Subscription)
        .options(joinedload(Subscription.plan))
        .where(
            and_(
                Subscription.id == subscription_id,
                Subscription.tenant_id == tenant_id
            )
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        return None
    
    update_data = subscription_data.model_dump(exclude_unset=True)
    
    # Si cambia el plan, recalcular montos
    if "plan_id" in update_data:
        plan = await get_plan(db, update_data["plan_id"])
        if not plan:
            raise ValueError("Plan no encontrado")
        
        # Recalcular monto según ciclo
        if subscription.billing_cycle == BillingCycle.YEARLY:
            subscription.amount = plan.yearly_price
        else:
            subscription.amount = plan.monthly_price
    
    for field, value in update_data.items():
        setattr(subscription, field, value)
    
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def cancel_subscription(
    db: AsyncSession, 
    subscription_id: UUID, 
    tenant_id: UUID, 
    reason: str,
    cancel_immediately: bool = False
) -> Optional[Subscription]:
    """Cancelar suscripción."""
    subscription = await get_subscription(db, subscription_id, tenant_id)
    
    if not subscription:
        return None
    
    now = datetime.now(timezone.utc)
    subscription.canceled_at = now
    subscription.canceled_reason = reason
    subscription.auto_renew = False
    
    if cancel_immediately:
        subscription.status = SubscriptionStatus.CANCELED
        subscription.end_date = now
    else:
        # Cancelar al final del período actual
        subscription.status = SubscriptionStatus.CANCELED
        # end_date se mantiene igual
    
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def reactivate_subscription(
    db: AsyncSession, 
    subscription_id: UUID, 
    tenant_id: UUID
) -> Optional[Subscription]:
    """Reactivar suscripción cancelada."""
    subscription = await get_subscription(db, subscription_id, tenant_id)
    
    if not subscription or subscription.status != SubscriptionStatus.CANCELED:
        return None
    
    # Desactivar suscripción actual si existe
    await _deactivate_current_subscription(db, tenant_id)
    
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.canceled_at = None
    subscription.canceled_reason = None
    subscription.is_current = True
    subscription.auto_renew = True
    
    await db.commit()
    await db.refresh(subscription)
    return subscription


# ===== UTILITY FUNCTIONS =====

async def _deactivate_current_subscription(db: AsyncSession, tenant_id: UUID):
    """Desactivar suscripción actual."""
    result = await db.execute(
        select(Subscription).where(
            and_(
                Subscription.tenant_id == tenant_id,
                Subscription.is_current == True
            )
        )
    )
    current_subscription = result.scalar_one_or_none()
    
    if current_subscription:
        current_subscription.is_current = False
        await db.commit()


async def get_subscription_stats(db: AsyncSession, tenant_id: UUID) -> dict:
    """Obtener estadísticas de suscripción."""
    current_sub = await get_current_subscription(db, tenant_id)
    
    if not current_sub:
        return {
            "has_subscription": False,
            "plan_name": "Sin Plan",
            "status": "no_subscription",
            "is_trial": False,
            "days_remaining": 0
        }
    
    now = datetime.now(timezone.utc)
    is_trial = current_sub.trial_end_date and current_sub.trial_end_date > now
    
    # Calcular días restantes
    if current_sub.end_date:
        if is_trial and current_sub.trial_end_date:
            delta = current_sub.trial_end_date - now
        else:
            delta = current_sub.end_date - now
        days_remaining = max(0, delta.days)
    else:
        days_remaining = -1  # Ilimitado
    
    return {
        "has_subscription": True,
        "plan_name": current_sub.plan.name,
        "plan_code": current_sub.plan.code,
        "status": current_sub.status.value,
        "is_trial": is_trial,
        "days_remaining": days_remaining,
        "billing_cycle": current_sub.billing_cycle.value
    }