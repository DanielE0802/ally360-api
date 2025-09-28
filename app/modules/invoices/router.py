from fastapi import APIRouter
from .invoices_router import invoices_router

# Router principal del módulo de facturas
router = APIRouter(prefix="/api/v1", tags=["Invoices Module"])

# Incluir sub-routers
router.include_router(invoices_router)


