"""
Reports Module - Ally360 ERP SaaS

Sistema completo de reportes para análisis de ventas, compras, inventario,
caja POS y estados financieros básicos.

Este módulo NO crea nuevas tablas, sino que genera consultas optimizadas
sobre las tablas existentes de otros módulos para generar reportes
ejecutivos y operacionales.

Funcionalidades principales:
- Reportes de ventas (totales, por producto, por vendedor, por cliente)
- Reportes de compras (por proveedor, por categoría)
- Reportes de inventario (stock actual, kardex, productos más vendidos)
- Reportes de caja POS (arqueo, movimientos, diferencias)
- Reportes financieros (ingresos vs egresos, cuentas por cobrar/pagar)
- Exportación CSV de todos los reportes
- Filtros avanzados con rangos de fechas y contexto multi-tenant

Architecture Pattern: Service Layer
- routers/ -> Define FastAPI endpoints con validaciones
- services/ -> Lógica de negocio y generación de consultas SQL
- schemas/ -> Modelos Pydantic para requests y responses
- utils/ -> Utilidades para exportación CSV y formateo
"""

try:
    from .routers import (
        sales_router,
        purchases_router,
        inventory_router,
        cash_registers_router,
        financial_router
    )
    
    __all__ = [
        "sales_router",
        "purchases_router", 
        "inventory_router",
        "cash_registers_router",
        "financial_router"
    ]
except ImportError:
    # Module dependencies not available yet
    __all__ = []

__version__ = "1.0.0"
__author__ = "Ally360 Development Team"
__description__ = "Reports module for comprehensive business analytics"