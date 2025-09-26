from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Synchronous engine for migrations and initial setup
sync_engine = create_engine(
    settings.database_url, 
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG
)

# Async engine for application use
async_engine = create_async_engine(
    settings.async_database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None
)

# Sync session for migrations
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Async session for application
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

# Sync dependency for migrations and setup
def get_db():
    """Genera una sesión de base de datos síncrona (para migraciones)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Async dependency for application endpoints
async def get_async_db() -> AsyncSession:
    """Genera una sesión de base de datos asíncrona para endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

# Helper function to get tenant-scoped query
def get_tenant_query(session, model, tenant_id):
    """Helper function to create tenant-scoped queries"""
    from app.common.mixins import TenantMixin
    
    if hasattr(model, 'tenant_id'):
        return session.query(model).filter(model.tenant_id == tenant_id)
    else:
        # Fallback for models not yet updated to use TenantMixin
        return session.query(model)

