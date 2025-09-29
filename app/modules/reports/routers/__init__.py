"""
Routers package for Reports module

Exports all report router instances for easy importing.
"""

from .sales import router as sales_router
from .purchases import router as purchases_router
from .inventory import router as inventory_router
from .cash_registers import router as cash_registers_router
from .financial import router as financial_router

__all__ = [
    "sales_router",
    "purchases_router", 
    "inventory_router",
    "cash_registers_router",
    "financial_router"
]