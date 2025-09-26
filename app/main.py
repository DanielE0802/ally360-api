from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import logging

# Import database components
from app.database.database import sync_engine, Base

# Import middleware
from app.common.middleware import TenantMiddleware, SecurityHeadersMiddleware

# Import routers
from app.modules.auth.router import auth_router
from app.modules.company.router import company_router
from app.modules.pdv.router import pdv_router
from app.modules.products.router import product_router
from app.modules.brands.router import brand_router
from app.modules.categories.router import categories_router
from app.modules.files.router_simple import router as files_router

# Import models for table creation
import app.modules.auth.models
import app.modules.company.models
import app.modules.pdv.models
import app.modules.products.models
import app.modules.brands.models
import app.modules.categories.models
import app.modules.files.models

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
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(company_router, prefix="/company", tags=["Companies"])
app.include_router(categories_router, prefix="/categories", tags=["Categories"])
app.include_router(pdv_router, prefix="/pdv", tags=["PDVs"])
app.include_router(product_router, prefix="/products", tags=["Products"])
app.include_router(brand_router, prefix="/brands", tags=["Brands"])
app.include_router(files_router)

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

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Ally360 API shutting down...")


