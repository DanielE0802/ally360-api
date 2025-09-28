"""
Módulo de Gastos (Bills) - Ally360 ERP

Este módulo maneja toda la cadena de compras con las siguientes características:

ENTIDADES PRINCIPALES:
- Suppliers: Proveedores con información de contacto y documentos
- PurchaseOrders: Órdenes de compra que no afectan inventario hasta convertirse
- Bills: Facturas de proveedor que actualizan inventario automáticamente
- BillPayments: Pagos con control automático de estados
- DebitNotes: Notas débito con ajustes de precio/cantidad/servicios

INTEGRACIÓN CON INVENTARIO:
- Bills en estado 'open' → incrementan stock + movimientos IN
- DebitNotes quantity_adjustment → incrementan stock + movimientos IN
- Estados 'draft' no afectan inventario

INTEGRACIÓN CON TAXES:
- Cálculo automático de impuestos por línea
- Soporte para impuestos globales DIAN y locales
- Totales calculados: subtotal, taxes_total, total_amount

ARQUITECTURA MULTI-TENANT:
- Todas las tablas incluyen company_id
- Queries automáticamente filtradas por tenant
- Validación de pertenencia en todos los endpoints

ROLES Y PERMISOS:
- owner/admin: Control total sobre todas las operaciones
- seller: Crear y gestionar compras, sin eliminar
- accountant: Ver todo, gestionar pagos
- viewer: Solo lectura

ESTADOS DE FACTURAS:
- draft: Borrador (no afecta inventario)
- open: Abierta (afecta inventario, pendiente de pago)
- partial: Pago parcial
- paid: Pagada completamente
- void: Anulada

ESTADOS DE ÓRDENES:
- draft: Borrador
- sent: Enviada al proveedor
- approved: Aprobada por proveedor
- closed: Cerrada/convertida
- void: Anulada

FLUJO TÍPICO:
1. Crear PurchaseOrder (draft) → no afecta stock
2. PurchaseOrder → sent/approved
3. Convertir PO a Bill (open) → actualiza stock + movimientos
4. Registrar pagos → cambia estado automáticamente
5. Crear DebitNotes si hay ajustes → puede afectar stock
"""

from .models import (
    PurchaseOrder, POItem, Bill, BillLineItem, 
    BillPayment, DebitNote, DebitNoteItem,
    PurchaseOrderStatus, BillStatus, PaymentMethod, 
    DebitNoteStatus, DebitNoteReasonType
)
from .schemas import (
    PurchaseOrderCreate, PurchaseOrderOut, PurchaseOrderDetail,
    BillCreate, BillOut, BillDetail,
    BillPaymentCreate, BillPaymentOut,
    DebitNoteCreate, DebitNoteOut, DebitNoteDetail
)
from .service import (
    PurchaseOrderService, BillService, BillPaymentService
)
from .router import bills_router

__all__ = [
    # Models
    "PurchaseOrder", "POItem", "Bill", "BillLineItem",
    "BillPayment", "DebitNote", "DebitNoteItem",
    "PurchaseOrderStatus", "BillStatus", "PaymentMethod",
    "DebitNoteStatus", "DebitNoteReasonType",
    
    # Schemas
    "PurchaseOrderCreate", "PurchaseOrderOut", "PurchaseOrderDetail",
    "BillCreate", "BillOut", "BillDetail",
    "BillPaymentCreate", "BillPaymentOut",
    "DebitNoteCreate", "DebitNoteOut", "DebitNoteDetail",
    
    # Services
    "PurchaseOrderService", "BillService", "BillPaymentService",
    
    # Router
    "bills_router"
]