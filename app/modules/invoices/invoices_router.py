from fastapi import APIRouter, Depends, status, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date
import tempfile
import os

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.invoices.service import InvoiceService, CustomerService
from app.modules.invoices.schemas import (
    InvoiceCreate, InvoiceOut, InvoiceDetail, InvoiceList, 
    PaymentCreate, PaymentOut, InvoiceEmailRequest,
    InvoiceUpdate, InvoiceCancelRequest
)

invoices_router = APIRouter(prefix="/invoices", tags=["Invoices"])


@invoices_router.post("/", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Crear una nueva factura de venta
    
    Solo propietarios, administradores y vendedores pueden crear facturas.
    Se actualiza automáticamente el stock de los productos.
    """
    service = InvoiceService(db)
    return service.create_invoice(invoice_data, auth_context.tenant_id, auth_context.user.id)


@invoices_router.get("/", response_model=InvoiceList)
def list_invoices(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[date] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    customer_id: Optional[UUID] = Query(None, description="Filtrar por cliente"),
    pdv_id: Optional[UUID] = Query(None, description="Filtrar por PDV"),
    status: Optional[str] = Query(None, description="pending, paid, cancelled"),
    invoice_number: Optional[str] = Query(None, description="Buscar por número de factura"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar facturas con filtros avanzados
    
    Permite filtrar por fechas, cliente, PDV, estado y número de factura.
    Todos los roles pueden ver las facturas.
    """
    service = InvoiceService(db)
    return service.get_invoices(
        tenant_id=auth_context.tenant_id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        pdv_id=pdv_id,
        status=status,
        invoice_number=invoice_number
    )


@invoices_router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener detalles completos de una factura
    """
    service = InvoiceService(db)
    return service.get_invoice_by_id(invoice_id, auth_context.tenant_id)


@invoices_router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: UUID,
    invoice_update: InvoiceUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Actualizar una factura (solo si está en estado draft)
    
    Solo se pueden actualizar facturas en estado borrador.
    """
    service = InvoiceService(db)
    return service.update_invoice(invoice_id, invoice_update, auth_context.tenant_id)


@invoices_router.post("/{invoice_id}/confirm")
def confirm_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Confirmar una factura (cambiar de draft a pending)
    
    Una vez confirmada, se actualiza el stock y ya no se puede modificar.
    """
    service = InvoiceService(db)
    return service.confirm_invoice(invoice_id, auth_context.tenant_id)


@invoices_router.post("/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: UUID,
    cancel_data: InvoiceCancelRequest,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Cancelar una factura
    
    Solo propietarios y administradores pueden cancelar facturas.
    Se revierte el movimiento de stock si aplica.
    """
    service = InvoiceService(db)
    return service.cancel_invoice(invoice_id, cancel_data.reason, auth_context.tenant_id)


# --- PAGOS ---

@invoices_router.post("/{invoice_id}/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def add_payment(
    invoice_id: UUID,
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Registrar un pago para una factura
    
    Permite pagos parciales. Cuando el total de pagos >= total de factura,
    el estado cambia automáticamente a 'paid'.
    """
    service = InvoiceService(db)
    return service.add_payment(invoice_id, payment_data, auth_context.tenant_id, auth_context.user.id)


@invoices_router.get("/{invoice_id}/payments", response_model=List[PaymentOut])
def get_invoice_payments(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener todos los pagos de una factura
    """
    service = InvoiceService(db)
    return service.get_invoice_payments(invoice_id, auth_context.tenant_id)


# --- PDF Y EMAIL ---

@invoices_router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Descargar factura en formato PDF
    
    Genera el PDF dinámicamente y lo retorna como descarga.
    """
    service = InvoiceService(db)
    
    # Verificar que la factura existe y pertenece al tenant
    invoice = service.get_invoice_by_id(invoice_id, auth_context.tenant_id)
    
    # TODO: Implementar generación de PDF
    # Por ahora retornamos un placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF generation not implemented yet"
    )


@invoices_router.post("/{invoice_id}/email")
def send_invoice_email(
    invoice_id: UUID,
    email_data: InvoiceEmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Enviar factura por email
    
    Envía la factura en PDF al email especificado usando tareas en background.
    """
    service = InvoiceService(db)
    
    # Verificar que la factura existe y pertenece al tenant
    invoice = service.get_invoice_by_id(invoice_id, auth_context.tenant_id)
    
    # TODO: Implementar envío de email con Celery
    # Por ahora retornamos un placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email sending not implemented yet"
    )


# --- REPORTES Y ESTADÍSTICAS ---

@invoices_router.get("/reports/summary")
def get_invoices_summary(
    start_date: date = Query(..., description="Fecha inicial (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Fecha final (YYYY-MM-DD)"),
    pdv_id: Optional[UUID] = Query(None, description="Filtrar por PDV"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "viewer"]))
):
    """
    Resumen de ventas por período
    
    Incluye totales de facturas, impuestos, estado de pagos, etc.
    """
    service = InvoiceService(db)
    return service.get_sales_summary(
        tenant_id=auth_context.tenant_id,
        start_date=start_date,
        end_date=end_date,
        pdv_id=pdv_id
    )


@invoices_router.get("/next-number/{pdv_id}")
def get_next_invoice_number(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Obtener el siguiente número de factura para un PDV
    
    Útil para mostrar el número antes de crear la factura.
    """
    service = InvoiceService(db)
    return service.get_next_invoice_number(pdv_id, auth_context.tenant_id)