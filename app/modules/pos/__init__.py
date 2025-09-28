"""
Módulo POS (Point of Sale) - Ally360 ERP

Este módulo maneja las operaciones de punto de venta con:

ENTIDADES PRINCIPALES:
- CashRegister: Cajas registradoras con apertura/cierre y arqueo
- CashMovement: Movimientos de caja (ventas, depósitos, retiros, gastos, ajustes)
- Seller: Vendedores asociados a ventas POS
- Invoices POS: Extensión de facturas con type=pos y seller_id

FUNCIONALIDADES:
- Apertura/cierre de cajas con arqueo automático
- Registro de movimientos de efectivo
- Ventas POS integradas con inventario y pagos
- Control de turnos por vendedor
- Validaciones de caja abierta obligatoria
- Reportes de caja y ventas por vendedor

INTEGRACIÓN CON OTROS MÓDULOS:
- Invoices: Facturas type=pos con seller_id
- Inventory: Descuento automático de stock por PDV
- Payments: Pagos obligatorios en ventas POS
- PDV: Validación de punto de venta activo

ARQUITECTURA MULTI-TENANT:
- Todas las tablas incluyen company_id (tenant_id)
- Queries automáticamente filtradas por tenant
- Validación de pertenencia de entidades al tenant
- Roles y permisos específicos por operación

REGLAS DE NEGOCIO:
- Solo una caja abierta por PDV simultáneamente
- Ventas POS requieren caja abierta
- Pagos obligatorios al momento de venta
- Arqueo automático en cierre de caja
- Sellers activos para asociar ventas

SEGURIDAD:
- owner/admin: Todas las operaciones
- seller/cashier: Operaciones de su caja/PDV
- accountant: Consultas y reportes
- viewer: Solo lectura
"""

from .models import (
    CashRegister, CashMovement, Seller,
    CashRegisterStatus, MovementType
)

from .schemas import (
    # CashRegister schemas
    CashRegisterCreate, CashRegisterOut, CashRegisterDetail,
    CashRegisterOpen, CashRegisterClose, CashRegisterList,
    
    # CashMovement schemas  
    CashMovementCreate, CashMovementOut, CashMovementList,
    
    # Seller schemas
    SellerCreate, SellerUpdate, SellerOut, SellerList,
    
    # POS Invoice schemas
    POSInvoiceCreate, POSInvoiceOut, POSInvoiceDetail
)

from .services import (
    CashRegisterService, CashMovementService, 
    SellerService, POSInvoiceService
)

from .routers import (
    cash_registers_router, cash_movements_router,
    sellers_router, pos_invoices_router
)

__all__ = [
    # Models
    "CashRegister", "CashMovement", "Seller",
    "CashRegisterStatus", "MovementType",
    
    # Schemas
    "CashRegisterCreate", "CashRegisterOut", "CashRegisterDetail",
    "CashRegisterOpen", "CashRegisterClose", "CashRegisterList",
    "CashMovementCreate", "CashMovementOut", "CashMovementList", 
    "SellerCreate", "SellerUpdate", "SellerOut", "SellerList",
    "POSInvoiceCreate", "POSInvoiceOut", "POSInvoiceDetail",
    
    # Services
    "CashRegisterService", "CashMovementService",
    "SellerService", "POSInvoiceService",
    
    # Routers
    "cash_registers_router", "cash_movements_router", 
    "sellers_router", "pos_invoices_router"
]