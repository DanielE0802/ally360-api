"""
Seed subscription plans for Ally360.

This script creates the default subscription plans.
"""
import asyncio
import logging
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.modules.subscriptions.models import Plan, PlanType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(settings.async_database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed_plans():
    """Seed default subscription plans."""
    
    plans_data = [
        {
            "name": "Plan Gratuito",
            "code": "FREE",
            "type": PlanType.FREE,
            "description": "Plan básico gratuito para empezar",
            "monthly_price": Decimal("0"),
            "yearly_price": Decimal("0"),
            "max_users": 1,
            "max_pdvs": 1,
            "max_products": 50,
            "max_storage_gb": 1,
            "max_invoices_month": 20,
            "has_advanced_reports": False,
            "has_api_access": False,
            "has_multi_currency": False,
            "has_inventory_alerts": False,
            "has_email_support": True,
            "has_phone_support": False,
            "has_priority_support": False,
            "is_popular": False,
            "sort_order": 1
        },
        {
            "name": "Plan Básico",
            "code": "BASIC",
            "type": PlanType.BASIC,
            "description": "Ideal para pequeñas empresas",
            "monthly_price": Decimal("29900"),  # $29,900 COP
            "yearly_price": Decimal("299000"),  # $299,000 COP (10 meses)
            "max_users": 3,
            "max_pdvs": 2,
            "max_products": 500,
            "max_storage_gb": 5,
            "max_invoices_month": 100,
            "has_advanced_reports": True,
            "has_api_access": False,
            "has_multi_currency": False,
            "has_inventory_alerts": True,
            "has_email_support": True,
            "has_phone_support": False,
            "has_priority_support": False,
            "is_popular": True,
            "sort_order": 2
        },
        {
            "name": "Plan Profesional",
            "code": "PROFESSIONAL",
            "type": PlanType.PROFESSIONAL,
            "description": "Para empresas en crecimiento",
            "monthly_price": Decimal("59900"),  # $59,900 COP
            "yearly_price": Decimal("599000"),  # $599,000 COP (10 meses)
            "max_users": 10,
            "max_pdvs": 5,
            "max_products": 2000,
            "max_storage_gb": 20,
            "max_invoices_month": 500,
            "has_advanced_reports": True,
            "has_api_access": True,
            "has_multi_currency": True,
            "has_inventory_alerts": True,
            "has_email_support": True,
            "has_phone_support": True,
            "has_priority_support": False,
            "is_popular": False,
            "sort_order": 3
        },
        {
            "name": "Plan Empresarial",
            "code": "ENTERPRISE",
            "type": PlanType.ENTERPRISE,
            "description": "Para grandes empresas con necesidades avanzadas",
            "monthly_price": Decimal("99900"),  # $99,900 COP
            "yearly_price": Decimal("999000"),  # $999,000 COP (10 meses)
            "max_users": None,  # Ilimitado
            "max_pdvs": None,   # Ilimitado
            "max_products": None,  # Ilimitado
            "max_storage_gb": 100,
            "max_invoices_month": None,  # Ilimitado
            "has_advanced_reports": True,
            "has_api_access": True,
            "has_multi_currency": True,
            "has_inventory_alerts": True,
            "has_email_support": True,
            "has_phone_support": True,
            "has_priority_support": True,
            "is_popular": False,
            "sort_order": 4
        }
    ]
    
    async with AsyncSessionLocal() as db:
        try:
            for plan_data in plans_data:
                # Check if plan already exists
                from sqlalchemy import select
                result = await db.execute(
                    select(Plan).where(Plan.code == plan_data["code"])
                )
                existing_plan = result.scalar_one_or_none()
                
                if existing_plan:
                    logger.info(f"Plan {plan_data['code']} already exists, updating...")
                    # Update existing plan
                    for key, value in plan_data.items():
                        if key != "code":  # Don't update the code
                            setattr(existing_plan, key, value)
                else:
                    logger.info(f"Creating plan {plan_data['code']}...")
                    # Create new plan
                    plan = Plan(**plan_data)
                    db.add(plan)
            
            await db.commit()
            logger.info("All plans seeded successfully!")
            
        except Exception as e:
            logger.error(f"Error seeding plans: {e}")
            await db.rollback()
            raise


async def main():
    """Main function."""
    logger.info("Starting subscription plans seeding...")
    await seed_plans()
    logger.info("Subscription plans seeding completed!")


if __name__ == "__main__":
    asyncio.run(main())