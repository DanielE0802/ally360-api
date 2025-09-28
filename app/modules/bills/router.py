"""
Routers FastAPI para el módulo de Gastos (Bills)

Endpoints para gestión completa de la cadena de compras:
- Proveedores: CRUD completo con búsqueda
- Órdenes de compra: Creación, listado, conversión a facturas
- Facturas: Gestión completa con integración de inventario
- Pagos: Registro y control de estados automático
- Notas débito: Ajustes con impacto en inventario

Todos los endpoints respetan la arquitectura multi-tenant y roles de usuario.
"""

from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.bills.service import (
    PurchaseOrderService, BillService, BillPaymentService, DebitNoteService
)
from app.modules.bills.schemas import (
    # Supplier schemas (deprecated, use Contacts module instead)
    # Purchase Order schemas
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderOut, 
    PurchaseOrderDetail, PurchaseOrderList, PurchaseOrderStatus,
    ConvertPOToBillRequest,
    # Bill schemas
    BillCreate, BillUpdate, BillOut, BillDetail, BillList, BillStatus,
    BillStatusUpdate,
    # Payment schemas
    BillPaymentCreate, BillPaymentOut, BillPaymentList,
    # Debit Note schemas
    DebitNoteCreate, DebitNoteOut, DebitNoteList, DebitNoteDetail
)

# Router principal
bills_router = APIRouter(prefix="/bills", tags=["Bills Module"])

# Sub-routers
# Suppliers are managed by Contacts module (type=provider). Endpoints deprecated.
# suppliers_router = APIRouter(prefix="/suppliers", tags=["Suppliers"]) 
purchase_orders_router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])
bill_payments_router = APIRouter(prefix="/bill-payments", tags=["Bill Payments"])
debit_notes_router = APIRouter(prefix="/debit-notes", tags=["Debit Notes"])


## Suppliers endpoints are deprecated. Use /contacts and filter by provider type.


# ===== PURCHASE ORDERS ENDPOINTS =====

@purchase_orders_router.post("/", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    po_data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Crear una nueva orden de compra
    
    Solo propietarios, administradores y vendedores pueden crear órdenes.
    Las órdenes draft no afectan el inventario.
    """
    service = PurchaseOrderService(db)
    return service.create_purchase_order(po_data, auth_context.tenant_id, auth_context.user.id)


@purchase_orders_router.get("/", response_model=PurchaseOrderList)
def list_purchase_orders(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[PurchaseOrderStatus] = Query(None, description="Filtrar por estado"),
    supplier_id: Optional[UUID] = Query(None, description="Filtrar por proveedor"),
    pdv_id: Optional[UUID] = Query(None, description="Filtrar por PDV"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar órdenes de compra con filtros
    
    Permite filtrar por estado, proveedor y PDV.
    Todos los roles pueden ver las órdenes.
    """
    service = PurchaseOrderService(db)
    return service.get_purchase_orders(
        tenant_id=auth_context.tenant_id,
        limit=limit,
        offset=offset,
        status=status,
        supplier_id=supplier_id,
        pdv_id=pdv_id
    )


@purchase_orders_router.get("/{po_id}", response_model=PurchaseOrderDetail)
def get_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener detalles completos de una orden de compra
    """
    service = PurchaseOrderService(db)
    return service.get_purchase_order_by_id(po_id, auth_context.tenant_id)


@purchase_orders_router.post("/{po_id}/convert-to-bill", response_model=BillOut)
def convert_purchase_order_to_bill(
    po_id: UUID,
    conversion_data: ConvertPOToBillRequest,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Convertir orden de compra a factura
    
    Solo se pueden convertir órdenes en estado 'sent' o 'approved'.
    Si la factura se crea en estado 'open', se actualiza el inventario automáticamente.
    """
    service = PurchaseOrderService(db)
    return service.convert_po_to_bill(po_id, conversion_data, auth_context.tenant_id, auth_context.user.id)


@purchase_orders_router.post("/{po_id}/void")
def void_purchase_order(
    po_id: UUID,
    void_data: BillStatusUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Anular una orden de compra
    
    Solo propietarios y administradores pueden anular órdenes.
    """
    service = PurchaseOrderService(db)
    return service.void_purchase_order(po_id, void_data.reason, auth_context.tenant_id)


# ===== BILLS ENDPOINTS =====

@bills_router.post("/", response_model=BillOut, status_code=status.HTTP_201_CREATED)
def create_bill(
    bill_data: BillCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Crear una nueva factura de proveedor
    
    Solo propietarios, administradores y vendedores pueden crear facturas.
    Si el estado es 'open', se actualiza automáticamente el inventario.
    """
    service = BillService(db)
    return service.create_bill(bill_data, auth_context.tenant_id, auth_context.user.id)


@bills_router.get("/", response_model=BillList)
def list_bills(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[BillStatus] = Query(None, description="Filtrar por estado"),
    supplier_id: Optional[UUID] = Query(None, description="Filtrar por proveedor"),
    pdv_id: Optional[UUID] = Query(None, description="Filtrar por PDV"),
    start_date: Optional[date] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar facturas con filtros avanzados
    
    Permite filtrar por estado, proveedor, PDV y rango de fechas.
    Todos los roles pueden ver las facturas.
    """
    service = BillService(db)
    return service.get_bills(
        tenant_id=auth_context.tenant_id,
        limit=limit,
        offset=offset,
        status=status,
        supplier_id=supplier_id,
        pdv_id=pdv_id,
        start_date=start_date,
        end_date=end_date
    )


@bills_router.get("/{bill_id}", response_model=BillDetail)
def get_bill(
    bill_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener detalles completos de una factura
    """
    service = BillService(db)
    return service.get_bill_by_id(bill_id, auth_context.tenant_id)


@bills_router.patch("/{bill_id}", response_model=BillOut)
def update_bill(
    bill_id: UUID,
    bill_update: BillUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Actualizar una factura (solo si está en estado draft)
    
    Solo se pueden actualizar facturas en estado borrador.
    """
    service = BillService(db)
    return service.update_bill(bill_id, bill_update, auth_context.tenant_id)


@bills_router.post("/{bill_id}/void")
def void_bill(
    bill_id: UUID,
    void_data: BillStatusUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Anular una factura
    
    Solo propietarios y administradores pueden anular facturas.
    En el MVP, no se revierte el inventario automáticamente.
    """
    service = BillService(db)
    return service.void_bill(bill_id, void_data.reason, auth_context.tenant_id)


# ===== BILL PAYMENTS ENDPOINTS =====

@bills_router.post("/{bill_id}/payments", response_model=BillPaymentOut, status_code=status.HTTP_201_CREATED)
def add_bill_payment(
    bill_id: UUID,
    payment_data: BillPaymentCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Registrar un pago para una factura
    
    Permite pagos parciales. Cuando el total de pagos >= total de factura,
    el estado cambia automáticamente a 'paid'.
    """
    service = BillPaymentService(db)
    return service.create_payment(bill_id, payment_data, auth_context.tenant_id, auth_context.user.id)


@bills_router.get("/{bill_id}/payments", response_model=List[BillPaymentOut])
def get_bill_payments(
    bill_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener todos los pagos de una factura
    """
    # Verificar que la factura existe y pertenece al tenant
    bill_service = BillService(db)
    bill = bill_service.get_bill_by_id(bill_id, auth_context.tenant_id)
    
    return bill.payments


@bill_payments_router.get("/", response_model=BillPaymentList)
def list_bill_payments(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    bill_id: Optional[UUID] = Query(None, description="Filtrar por factura"),
    start_date: Optional[date] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar pagos de facturas con filtros
    
    Permite filtrar por factura y rango de fechas.
    """
    service = BillPaymentService(db)
    return service.list_payments(
        tenant_id=auth_context.tenant_id,
        limit=limit,
        offset=offset,
        bill_id=bill_id,
        start_date=start_date,
        end_date=end_date
    )


# ===== DEBIT NOTES ENDPOINTS (Placeholder) =====

@debit_notes_router.post("/", response_model=DebitNoteOut, status_code=status.HTTP_201_CREATED)
def create_debit_note(
    debit_note_data: DebitNoteCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Crear una nueva nota débito
    
    Las notas débito con ajustes de cantidad actualizan automáticamente el inventario.
    """
    service = DebitNoteService(db)
    return service.create_debit_note(debit_note_data, auth_context.tenant_id, auth_context.user.id)


@debit_notes_router.get("/", response_model=DebitNoteList)
def list_debit_notes(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    supplier_id: Optional[UUID] = Query(None, description="Filtrar por proveedor"),
    bill_id: Optional[UUID] = Query(None, description="Filtrar por factura"),
    start_date: Optional[date] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar notas débito con filtros
    """
    service = DebitNoteService(db)
    return service.get_debit_notes(
        tenant_id=auth_context.tenant_id,
        limit=limit,
        offset=offset,
        supplier_id=supplier_id,
        bill_id=bill_id,
        start_date=start_date,
        end_date=end_date
    )


@debit_notes_router.get("/{debit_note_id}", response_model=DebitNoteDetail)
def get_debit_note(
    debit_note_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener detalles completos de una nota débito
    """
    service = DebitNoteService(db)
    return service.get_debit_note_by_id(debit_note_id, auth_context.tenant_id)


@debit_notes_router.post("/{debit_note_id}/void")
def void_debit_note(
    debit_note_id: UUID,
    void_data: BillStatusUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Anular una nota débito
    
    Solo propietarios y administradores pueden anular notas débito.
    En el MVP, no se revierte el inventario automáticamente.
    """
    service = DebitNoteService(db)
    return service.void_debit_note(debit_note_id, void_data.reason, auth_context.tenant_id)


# Incluir todos los sub-routers en el router principal
# bills_router.include_router(suppliers_router)
bills_router.include_router(purchase_orders_router)
bills_router.include_router(bill_payments_router)
bills_router.include_router(debit_notes_router)