from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import logging

# Import database components
from app.database.database import sync_engine, Base
from sqlalchemy import inspect, text

# Import middleware
from app.common.middleware import TenantMiddleware, SecurityHeadersMiddleware

# Import routers
from app.modules.auth.router import auth_router
from app.modules.company.router import company_router
from app.modules.pdv.router import pdv_router
from app.modules.products.router import product_router
from app.modules.brands.router import brand_router
from app.modules.categories.router import categories_router
from app.modules.inventory.router import stock_router, movements_router
from app.modules.taxes.router import taxes_router
from app.modules.invoices.router import router as invoices_router
from app.modules.bills.router import bills_router
from app.modules.contacts.router import router as contacts_router
from app.modules.files.router_simple import router as files_router
from app.modules.email.router import router as email_router
from app.modules.locations.router import router as locations_router
from app.modules.subscriptions.router import router as subscriptions_router
from app.modules.pos.routers import (
    cash_registers_router, 
    cash_movements_router, 
    sellers_router, 
    pos_invoices_router
)
from app.modules.reports.routers import (
    sales_router as sales_reports_router,
    purchases_router as purchases_reports_router, 
    inventory_router as inventory_reports_router,
    cash_registers_router as cash_registers_reports_router,
    financial_router as financial_reports_router
)

# Import models for table creation
import app.modules.auth.models
import app.modules.company.models
import app.modules.pdv.models
import app.modules.products.models
import app.modules.brands.models
import app.modules.categories.models
import app.modules.invoices.models
import app.modules.bills.models
import app.modules.contacts.models
import app.modules.files.models
import app.modules.pos.models
import app.modules.locations.models
import app.modules.subscriptions.models
import app.modules.reports  # Import module to register models

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Ally360 API",
    description="Multi-tenant ERP SaaS API built with FastAPI, PostgreSQL, and MinIO",
    version="1.0.0",
    contact={
        "name": "Ally360 Support",
        "url": "https://ally360.com/support",
        "email": "support@ally360.com"
    },
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None
)

# Add middleware (order matters!)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TenantMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(locations_router)  # Public endpoint - no prefix needed
app.include_router(subscriptions_router)  # Subscription management
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(company_router, prefix="/company", tags=["Companies"])
app.include_router(categories_router, prefix="/categories", tags=["Categories"])
app.include_router(pdv_router, tags=["PDVs"])
app.include_router(product_router, tags=["Products"])
app.include_router(brand_router, prefix="/brands", tags=["Brands"])
app.include_router(taxes_router, tags=["Taxes"])
app.include_router(invoices_router)
app.include_router(bills_router)
app.include_router(cash_registers_router, prefix="/api/v1")
app.include_router(cash_movements_router, prefix="/api/v1")
app.include_router(sellers_router, prefix="/api/v1")
app.include_router(pos_invoices_router, prefix="/api/v1")
app.include_router(sales_reports_router, prefix="/api/v1")
app.include_router(purchases_reports_router, prefix="/api/v1")  
app.include_router(inventory_reports_router, prefix="/api/v1")
app.include_router(cash_registers_reports_router, prefix="/api/v1")
app.include_router(financial_reports_router, prefix="/api/v1")
app.include_router(contacts_router, tags=["Contacts"])
app.include_router(stock_router, tags=["Inventory"])
app.include_router(movements_router, tags=["Inventory"])
app.include_router(files_router)
app.include_router(email_router)

# Create database tables (only for development - use migrations in production)
if settings.ENVIRONMENT == "development":
    Base.metadata.create_all(bind=sync_engine)

@app.get("/")
async def read_root():
    return {
        "message": "Ally360 API is running",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}

@app.on_event("startup")
async def startup_event():
    logger.info("Ally360 API starting up...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Lightweight schema sync for development environments (no Alembic)
    if settings.ENVIRONMENT == "development":
        try:
            inspector = inspect(sync_engine)
            tables = inspector.get_table_names()
            if "users" in tables:
                cols = {c["name"] for c in inspector.get_columns("users")}
                with sync_engine.begin() as conn:
                    if "is_superuser" not in cols:
                        logger.info("Adding missing column users.is_superuser (BOOLEAN DEFAULT FALSE)")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE"))
                    if "email_verified" not in cols:
                        logger.info("Adding missing column users.email_verified (BOOLEAN DEFAULT FALSE)")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE"))
                    if "email_verified_at" not in cols:
                        logger.info("Adding missing column users.email_verified_at (TIMESTAMPTZ NULL)")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ NULL"))
                    if "last_login" not in cols:
                        logger.info("Adding missing column users.last_login (TIMESTAMPTZ NULL)")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ NULL"))
                    if "profile_id" not in cols:
                        logger.info("Adding missing column users.profile_id (UUID NULL)")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_id UUID NULL"))
                    if "created_at" not in cols:
                        logger.info("Adding missing column users.created_at (TIMESTAMPTZ DEFAULT now())")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()"))
                    if "updated_at" not in cols:
                        logger.info("Adding missing column users.updated_at (TIMESTAMPTZ DEFAULT now())")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()"))
                    if "deleted_at" not in cols:
                        logger.info("Adding missing column users.deleted_at (TIMESTAMPTZ NULL)")
                        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL"))
        except Exception as e:
            logger.warning(f"Schema sync skipped or failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Ally360 API shutting down...")


