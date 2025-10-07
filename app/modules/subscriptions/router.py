"""
API Router for subscription management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database.database import get_async_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext

from . import crud, schemas
from .models import SubscriptionStatus, PlanType, BillingCycle

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
    responses={404: {"description": "Not found"}}
)


# ===== PLAN ENDPOINTS =====

@router.get("/plans", response_model=List[schemas.PlanOut])
async def get_plans(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de registros"),
    plan_type: Optional[PlanType] = Query(None, description="Filtrar por tipo de plan"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener lista de planes disponibles.
    
    Este endpoint es público y no requiere autenticación.
    """
    plans = await crud.get_plans(
        db=db,
        skip=skip,
        limit=limit,
        plan_type=plan_type,
        active_only=True
    )
    return plans


@router.get("/plans/{plan_id}", response_model=schemas.PlanOut)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener detalles de un plan específico.
    
    Este endpoint es público y no requiere autenticación.
    """
    plan = await crud.get_plan(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan no encontrado"
        )
    return plan


# ===== SUBSCRIPTION ENDPOINTS =====

@router.get("/current", response_model=schemas.SubscriptionCurrent)
async def get_current_subscription(
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener suscripción actual de la empresa.
    
    **Para validar si ya seleccionó un plan.**
    
    Retorna información detallada de la suscripción activa incluyendo:
    - Estado de la suscripción
    - Plan actual y sus características
    - Días restantes
    - Límites del plan
    - Features disponibles
    """
    subscription = await crud.get_current_subscription(
        db=db, 
        tenant_id=auth_context.tenant_id
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay suscripción activa"
        )
    
    # Calcular propiedades dinámicas
    from datetime import datetime
    now = datetime.utcnow()
    
    is_trial = (
        subscription.trial_end_date and 
        subscription.trial_end_date > now and
        subscription.status == SubscriptionStatus.TRIAL
    )
    
    # Calcular días restantes
    if subscription.end_date:
        if is_trial and subscription.trial_end_date:
            delta = subscription.trial_end_date - now
        else:
            delta = subscription.end_date - now
        days_remaining = max(0, delta.days)
    else:
        days_remaining = -1  # Ilimitado
    
    return schemas.SubscriptionCurrent(
        id=subscription.id,
        plan_name=subscription.plan.name,
        plan_code=subscription.plan.code,
        plan_type=subscription.plan.type,
        status=subscription.status,
        billing_cycle=subscription.billing_cycle,
        is_trial=is_trial,
        days_remaining=days_remaining,
        next_billing_date=subscription.next_billing_date,
        
        # Límites del plan
        max_users=subscription.plan.max_users,
        max_pdvs=subscription.plan.max_pdvs,
        max_products=subscription.plan.max_products,
        max_storage_gb=subscription.plan.max_storage_gb,
        max_invoices_month=subscription.plan.max_invoices_month,
        
        # Features
        has_advanced_reports=subscription.plan.has_advanced_reports,
        has_api_access=subscription.plan.has_api_access,
        has_multi_currency=subscription.plan.has_multi_currency,
        has_inventory_alerts=subscription.plan.has_inventory_alerts
    )


@router.get("/", response_model=schemas.SubscriptionList)
async def get_subscriptions(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(20, ge=1, le=100, description="Número máximo de registros"),
    status: Optional[SubscriptionStatus] = Query(None, description="Filtrar por estado"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener historial de suscripciones de la empresa.
    """
    subscriptions = await crud.get_subscriptions(
        db=db,
        tenant_id=auth_context.tenant_id,
        skip=skip,
        limit=limit,
        status=status
    )
    
    # Calcular propiedades dinámicas para cada suscripción
    from datetime import datetime
    now = datetime.utcnow()
    
    subscription_list = []
    for sub in subscriptions:
        is_trial = (
            sub.trial_end_date and 
            sub.trial_end_date > now and
            sub.status == SubscriptionStatus.TRIAL
        )
        
        is_active = sub.status in [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
        if is_active and sub.end_date and sub.end_date <= now:
            is_active = False
        
        # Calcular días restantes
        if sub.end_date:
            if is_trial and sub.trial_end_date:
                delta = sub.trial_end_date - now
            else:
                delta = sub.end_date - now
            days_remaining = max(0, delta.days)
        else:
            days_remaining = -1
        
        subscription_out = schemas.SubscriptionOut(
            **sub.__dict__,
            is_active=is_active,
            is_trial=is_trial,
            days_remaining=days_remaining
        )
        subscription_list.append(subscription_out)
    
    total = len(subscription_list)  # Para una implementación completa, usar count query
    
    return schemas.SubscriptionList(
        subscriptions=subscription_list,
        total=total,
        limit=limit,
        offset=skip
    )


@router.get("/{subscription_id}", response_model=schemas.SubscriptionDetail)
async def get_subscription(
    subscription_id: UUID,
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener detalles de una suscripción específica.
    """
    subscription = await crud.get_subscription(
        db=db,
        subscription_id=subscription_id,
        tenant_id=auth_context.tenant_id
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suscripción no encontrada"
        )
    
    # Calcular propiedades dinámicas
    from datetime import datetime
    now = datetime.utcnow()
    
    is_trial = (
        subscription.trial_end_date and 
        subscription.trial_end_date > now and
        subscription.status == SubscriptionStatus.TRIAL
    )
    
    is_active = subscription.status in [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
    if is_active and subscription.end_date and subscription.end_date <= now:
        is_active = False
    
    # Calcular días restantes
    if subscription.end_date:
        if is_trial and subscription.trial_end_date:
            delta = subscription.trial_end_date - now
        else:
            delta = subscription.end_date - now
        days_remaining = max(0, delta.days)
    else:
        days_remaining = -1
    
    subscription_detail = schemas.SubscriptionDetail(
        **subscription.__dict__,
        plan=subscription.plan,
        is_active=is_active,
        is_trial=is_trial,
        days_remaining=days_remaining
    )
    
    return subscription_detail


@router.post("/", response_model=schemas.SubscriptionCreateResponse)
async def create_subscription(
    subscription_data: schemas.SubscriptionCreate,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crear nueva suscripción para la empresa.
    
    **Nota:** Solo pueden tener una suscripción activa por empresa.
    Si ya existe una suscripción activa, se desactivará automáticamente.
    """
    try:
        # Verificar si ya tiene suscripción activa
        current_subscription = await crud.get_current_subscription(
            db=db, 
            tenant_id=auth_context.tenant_id
        )
        is_upgrade = current_subscription is not None
        
        subscription = await crud.create_subscription(
            db=db,
            tenant_id=auth_context.tenant_id,
            subscription_data=subscription_data
        )
        
        # Calcular propiedades dinámicas
        from datetime import datetime
        now = datetime.utcnow()
        
        is_trial = (
            subscription.trial_end_date and 
            subscription.trial_end_date > now and
            subscription.status == SubscriptionStatus.TRIAL
        )
        
        is_active = subscription.status in [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
        
        # Calcular días restantes
        if subscription.end_date:
            if is_trial and subscription.trial_end_date:
                delta = subscription.trial_end_date - now
            else:
                delta = subscription.end_date - now
            days_remaining = max(0, delta.days)
        else:
            days_remaining = -1
        
        subscription_detail = schemas.SubscriptionDetail(
            **subscription.__dict__,
            plan=subscription.plan,
            is_active=is_active,
            is_trial=is_trial,
            days_remaining=days_remaining
        )
        
        message = "Suscripción actualizada exitosamente" if is_upgrade else "Suscripción creada exitosamente"
        
        return schemas.SubscriptionCreateResponse(
            subscription=subscription_detail,
            message=message,
            is_upgrade=is_upgrade
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{subscription_id}", response_model=schemas.SubscriptionDetail)
async def update_subscription(
    subscription_id: UUID,
    subscription_data: schemas.SubscriptionUpdate,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualizar suscripción existente.
    """
    try:
        subscription = await crud.update_subscription(
            db=db,
            subscription_id=subscription_id,
            tenant_id=auth_context.tenant_id,
            subscription_data=subscription_data
        )
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Suscripción no encontrada"
            )
        
        # Calcular propiedades dinámicas
        from datetime import datetime
        now = datetime.utcnow()
        
        is_trial = (
            subscription.trial_end_date and 
            subscription.trial_end_date > now and
            subscription.status == SubscriptionStatus.TRIAL
        )
        
        is_active = subscription.status in [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
        
        # Calcular días restantes
        if subscription.end_date:
            if is_trial and subscription.trial_end_date:
                delta = subscription.trial_end_date - now
            else:
                delta = subscription.end_date - now
            days_remaining = max(0, delta.days)
        else:
            days_remaining = -1
        
        return schemas.SubscriptionDetail(
            **subscription.__dict__,
            plan=subscription.plan,
            is_active=is_active,
            is_trial=is_trial,
            days_remaining=days_remaining
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{subscription_id}/cancel", response_model=schemas.SubscriptionDetail)
async def cancel_subscription(
    subscription_id: UUID,
    cancel_data: schemas.SubscriptionCancel,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Cancelar suscripción.
    """
    subscription = await crud.cancel_subscription(
        db=db,
        subscription_id=subscription_id,
        tenant_id=auth_context.tenant_id,
        reason=cancel_data.reason,
        cancel_immediately=cancel_data.cancel_immediately
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suscripción no encontrada"
        )
    
    # Calcular propiedades dinámicas
    from datetime import datetime
    now = datetime.utcnow()
    
    is_trial = (
        subscription.trial_end_date and 
        subscription.trial_end_date > now and
        subscription.status == SubscriptionStatus.TRIAL
    )
    
    is_active = subscription.status in [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
    
    # Calcular días restantes
    if subscription.end_date:
        if is_trial and subscription.trial_end_date:
            delta = subscription.trial_end_date - now
        else:
            delta = subscription.end_date - now
        days_remaining = max(0, delta.days)
    else:
        days_remaining = -1
    
    return schemas.SubscriptionDetail(
        **subscription.__dict__,
        plan=subscription.plan,
        is_active=is_active,
        is_trial=is_trial,
        days_remaining=days_remaining
    )


@router.post("/{subscription_id}/reactivate", response_model=schemas.SubscriptionDetail)
async def reactivate_subscription(
    subscription_id: UUID,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Reactivar suscripción cancelada.
    """
    subscription = await crud.reactivate_subscription(
        db=db,
        subscription_id=subscription_id,
        tenant_id=auth_context.tenant_id
    )
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suscripción no encontrada o no se puede reactivar"
        )
    
    # Calcular propiedades dinámicas
    from datetime import datetime
    now = datetime.utcnow()
    
    is_trial = (
        subscription.trial_end_date and 
        subscription.trial_end_date > now and
        subscription.status == SubscriptionStatus.TRIAL
    )
    
    is_active = subscription.status in [SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE]
    
    # Calcular días restantes
    if subscription.end_date:
        if is_trial and subscription.trial_end_date:
            delta = subscription.trial_end_date - now
        else:
            delta = subscription.end_date - now
        days_remaining = max(0, delta.days)
    else:
        days_remaining = -1
    
    return schemas.SubscriptionDetail(
        **subscription.__dict__,
        plan=subscription.plan,
        is_active=is_active,
        is_trial=is_trial,
        days_remaining=days_remaining
    )


# ===== UTILITY ENDPOINTS =====

@router.get("/stats/current", response_model=dict)
async def get_subscription_stats(
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener estadísticas resumidas de la suscripción actual.
    """
    stats = await crud.get_subscription_stats(
        db=db, 
        tenant_id=auth_context.tenant_id
    )
    return stats