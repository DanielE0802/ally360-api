from fastapi import APIRouter, Depends, status, Query, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date
import tempfile
import os

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.invoices.service import InvoiceService
from app.modules.invoices.schemas import (
    InvoiceCreate, InvoiceOut, InvoiceDetail, InvoiceList, 
    PaymentCreate, PaymentOut, InvoiceEmailRequest, InvoiceEmailResponse,
    InvoiceUpdate, InvoiceCancelRequest, InvoiceFilters, InvoiceStatus,
    InvoicesMonthlySummary, TopProductsResponse, SalesComparison, PDVSalesResponse
)
from app.modules.invoices.service import get_top_products, get_sales_comparison, get_sales_by_pdv
import os

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.invoices.service import InvoiceService
from app.modules.invoices.schemas import (
    InvoiceCreate, InvoiceOut, InvoiceDetail, InvoiceList, 
    PaymentCreate, PaymentOut, InvoiceEmailRequest, InvoiceEmailResponse,
    InvoiceUpdate, InvoiceCancelRequest, InvoiceFilters, InvoiceStatus,
    InvoicesMonthlySummary
)

# Router principal del módulo de facturas
router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
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
    return service.create_invoice(invoice_data, auth_context.tenant_id, auth_context.user_id)


@router.get("/", response_model=InvoiceList)
def list_invoices(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[date] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    customer_id: Optional[UUID] = Query(None, description="Filtrar por cliente"),
    pdv_id: Optional[UUID] = Query(None, description="Filtrar por PDV"),
    status: Optional[InvoiceStatus] = Query(None, description="Estado de la factura"),
    search: Optional[str] = Query(None, description="Buscar por número o notas"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar facturas con filtros avanzados
    
    Permite filtrar por fechas, cliente, PDV, estado y número de factura.
    Todos los roles pueden ver las facturas.
    """
    service = InvoiceService(db)
    filters = InvoiceFilters(
        status=status,
        customer_id=customer_id,
        pdv_id=pdv_id,
        date_from=start_date,
        date_to=end_date,
        search=search
    )
    return service.get_invoices(auth_context.tenant_id, filters, limit, offset)


@router.get("/{invoice_id}", response_model=InvoiceDetail)
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


@router.patch("/{invoice_id}", response_model=InvoiceOut)
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


@router.post("/{invoice_id}/confirm")
def confirm_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Confirmar una factura (cambiar de draft a open)
    
    Una vez confirmada, se actualiza el stock y ya no se puede modificar.
    """
    service = InvoiceService(db)
    return service.confirm_invoice(invoice_id, auth_context.tenant_id)


@router.post("/{invoice_id}/cancel")
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

@router.post("/{invoice_id}/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
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
    return service.add_payment(invoice_id, payment_data, auth_context.tenant_id, auth_context.user_id)


@router.get("/{invoice_id}/payments", response_model=List[PaymentOut])
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


# --- EMAIL ---

@router.post("/{invoice_id}/send-email", response_model=InvoiceEmailResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_invoice_email(
    invoice_id: UUID,
    to_email: str = Form(..., description="Email del destinatario"),
    subject: Optional[str] = Form(None, description="Asunto personalizado"),
    message: Optional[str] = Form(None, description="Mensaje personalizado"),
    pdf_file: UploadFile = File(..., description="Archivo PDF de la factura"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Enviar factura por email con PDF adjunto.
    
    Recibe el PDF generado desde el frontend y lo envía por email
    usando tareas asíncronas de Celery.
    """
    # Validar tipo de archivo
    if not pdf_file.content_type or not pdf_file.content_type.startswith('application/pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un PDF válido"
        )
    
    # Validar tamaño del archivo (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    pdf_content = await pdf_file.read()
    if len(pdf_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo PDF es demasiado grande (máximo 10MB)"
        )
    
    service = InvoiceService(db)
    
    result = service.send_invoice_email(
        invoice_id=invoice_id,
        to_email=to_email,
        pdf_content=pdf_content,
        pdf_filename=pdf_file.filename or f"factura_{invoice_id}.pdf",
        company_id=auth_context.tenant_id,
        custom_message=message,
        subject=subject
    )
    
    return result


# --- REPORTES Y ESTADÍSTICAS ---

@router.get("/reports/summary")
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


@router.get("/next-number/{pdv_id}")
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


@router.get("/reports/monthly-status", response_model=InvoicesMonthlySummary)
def get_invoices_monthly_status(
    year: int = Query(..., ge=2000, le=2100, description="Año, ej. 2025"),
    month: int = Query(..., ge=1, le=12, description="Mes (1-12)"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "viewer"]))
):
    """
    Resumen mensual por estado para el tenant actual:
    - total: número de facturas y recaudado del mes
    - open:  número de facturas y recaudado de facturas OPEN
    - paid:  número de facturas y recaudado de facturas PAID
    - void:  número de facturas y recaudado de facturas VOID
    """
    service = InvoiceService(db)
    return service.get_monthly_status_summary(auth_context.tenant_id, year, month)


@router.get("/reports/top-products", response_model=TopProductsResponse)
async def get_top_products_endpoint(
    period: str = Query("month", description="Periodo: day, week, month"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "viewer"]))
):
    """
    Top-selling products for the tenant in the given period.
    """
    return await get_top_products(db=db, tenant_id=auth_context.tenant_id, period=period)


@router.get("/reports/comparison", response_model=SalesComparison)
async def get_sales_comparison_endpoint(
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "viewer"]))
):
    """
    Sales comparison (today vs yesterday) for the tenant.
    """
    return await get_sales_comparison(db=db, tenant_id=auth_context.tenant_id)


@router.get("/reports/sales-by-pdv", response_model=PDVSalesResponse)
async def get_sales_by_pdv_endpoint(
    period: str = Query("month", description="Periodo: day, week, month"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "viewer"]))
):
    """
    Sales comparison by PDV for charts - useful for comparing performance across stores.
    """
    return await get_sales_by_pdv(db=db, tenant_id=auth_context.tenant_id, period=period)


