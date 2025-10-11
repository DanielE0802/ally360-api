"""
Routers FastAPI para el módulo POS (Point of Sale)

Define todos los endpoints REST para:
- CashRegisters: Apertura/cierre de cajas
- CashMovements: Movimientos de caja
- Sellers: Gestión de vendedores
- POSInvoices: Ventas POS

Todos los endpoints implementan:
- Validación de permisos por rol
- Filtros multi-tenant automáticos
- Paginación y ordenamiento
- Documentación Swagger completa
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import date
from decimal import Decimal

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from app.modules.pos.services import (
    CashRegisterService, CashMovementService, 
    SellerService, POSInvoiceService
)
from app.modules.pos.reports import POSReportsService, DateRange
from app.modules.pos.payments import AdvancedPaymentService
from app.modules.pos.multi_cash import MultiCashService
from app.modules.pos.analytics import RealTimeAnalyticsService
from app.modules.pos.schemas import (
    # CashRegister schemas
    CashRegisterOpen, CashRegisterClose, CashRegisterOut, 
    CashRegisterDetail, CashRegisterList,
    
    # CashMovement schemas
    CashMovementCreate, CashMovementOut, CashMovementList,
    
    # Seller schemas
    SellerCreate, SellerUpdate, SellerOut, SellerList,
    
    # POS Invoice schemas
    POSInvoiceCreate, POSInvoiceOut, POSInvoiceDetail,
    
    # Advanced Payments schemas ← NUEVO
    MixedPaymentRequest, MixedPaymentResponse,
    QRPaymentRequest, QRPaymentResponse,
    QRPaymentStatusRequest, QRPaymentStatusResponse,
    PaymentValidationResponse,
    
    # Multi-Cash schemas ← NUEVO v1.3.0
    MultiCashSessionCreate, MultiCashSessionResponse, ShiftTransferRequest,
    ShiftTransferResponse, ConsolidatedAuditResponse, MultiCashSessionClose,
    
    # Real-Time Analytics schemas ← NUEVO v1.3.0
    LiveDashboardResponse, AlertResponse, SalesTargetCheck, PredictiveAnalyticsResponse,
    LiveMetricsResponse, ComparativeAnalyticsResponse,
    
    # Enums
    CashRegisterStatus, MovementType, QRPaymentProvider
)
from app.modules.pos.reports import (
    DateRangeSchema, SalesBySellerResponse, CashAuditResponse,
    ShiftAnalysisResponse, TopProductsResponse
)


# ===== CASH REGISTERS ROUTER =====

cash_registers_router = APIRouter(prefix="/cash-registers", tags=["POS"])


@cash_registers_router.post("/open", response_model=CashRegisterOut, status_code=status.HTTP_201_CREATED)
async def open_cash_register(
    register_data: CashRegisterOpen,
    pdv_id: UUID = Query(..., description="ID del punto de venta"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    Abrir caja registradora en el PDV del contexto JWT.
    
    - **opening_balance**: Saldo inicial de apertura
    - **opening_notes**: Notas opcionales de apertura  
    - **seller_id**: ID del vendedor responsable (opcional, para reportes)
    
    Validaciones:
    - Solo una caja abierta por PDV simultáneamente
    - PDV debe existir y pertenecer al tenant
    - Seller (si se proporciona) debe existir y estar activo
    - Usuario debe tener permisos de caja
    
    Beneficios de asociar vendedor:
    - Reportes de ventas por vendedor
    - Comisiones y análisis de performance
    - Auditoría mejorada de operaciones
    """
    service = CashRegisterService(db)
    return service.open_cash_register(
        register_data=register_data,
        pdv_id=pdv_id,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


@cash_registers_router.get("/current", response_model=CashRegisterOut)
async def get_current_cash_register(
    pdv_id: UUID = Query(..., description="ID del punto de venta"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    Devuelve la caja abierta actual para el PDV indicado.
    
    - 404 si no hay caja abierta
    - Multi-tenant: filtra por tenant_id del contexto
    """
    service = CashRegisterService(db)
    register = service.get_current_cash_register(
        tenant_id=auth_context.tenant_id,
        pdv_id=pdv_id
    )
    if not register:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay caja abierta para este PDV")
    return register


@cash_registers_router.post("/{register_id}/close", response_model=CashRegisterOut)
async def close_cash_register(
    register_id: UUID = Path(..., description="ID de la caja registradora"),
    close_data: CashRegisterClose = ...,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    Cerrar caja registradora con arqueo automático.
    
    - **closing_balance**: Saldo final declarado
    - **closing_notes**: Notas opcionales de cierre
    
    Funcionalidades:
    - Calcula balance real basado en movimientos
    - Genera ajuste automático si hay diferencias
    - Cambia estado a CLOSED
    - Registra usuario y hora de cierre
    """
    service = CashRegisterService(db)
    return service.close_cash_register(
        register_id=register_id,
        close_data=close_data,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


@cash_registers_router.get("/", response_model=CashRegisterList)
async def get_cash_registers(
    pdv_id: Optional[UUID] = Query(None, description="Filtrar por PDV"),
    status: Optional[CashRegisterStatus] = Query(None, description="Filtrar por estado"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Listar cajas registradoras con filtros opcionales.
    
    Query Parameters:
    - **pdv_id**: Filtrar por punto de venta específico
    - **status**: Filtrar por estado (open/closed)
    - **limit**: Número máximo de resultados (1-1000)
    - **offset**: Número de registros a saltar
    
    Ordenamiento: Por fecha de apertura descendente
    """
    service = CashRegisterService(db)
    result = service.get_cash_registers(
        tenant_id=auth_context.tenant_id,
        pdv_id=pdv_id,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return CashRegisterList(
        cash_registers=result["cash_registers"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"]
    )


@cash_registers_router.get("/{register_id}", response_model=CashRegisterDetail)
async def get_cash_register_detail(
    register_id: UUID = Path(..., description="ID de la caja registradora"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Obtener detalle completo de caja registradora con movimientos.
    
    Incluye:
    - Información básica de la caja
    - Todos los movimientos de la caja
    - Cálculos de balance y diferencias
    - Resumen por tipo de movimiento
    """
    service = CashRegisterService(db)
    return service.get_cash_register_detail(
        register_id=register_id,
        tenant_id=auth_context.tenant_id
    )


# ===== CASH MOVEMENTS ROUTER =====

cash_movements_router = APIRouter(prefix="/cash-movements", tags=["POS"])


@cash_movements_router.post("/", response_model=CashMovementOut, status_code=status.HTTP_201_CREATED)
async def create_cash_movement(
    movement_data: CashMovementCreate,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    Registrar movimiento manual de caja.
    
    - **cash_register_id**: ID de la caja registradora
    - **type**: Tipo de movimiento (deposit, withdrawal, expense, adjustment)
    - **amount**: Monto (siempre positivo)
    - **reference**: Referencia opcional
    - **notes**: Notas del movimiento
    
    Validaciones:
    - Caja debe estar abierta
    - Caja debe pertenecer al tenant
    - Monto debe ser mayor a cero
    
    Nota: Los movimientos tipo SALE se generan automáticamente con las ventas POS
    """
    service = CashMovementService(db)
    return service.create_movement(
        movement_data=movement_data,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


@cash_movements_router.get("/", response_model=CashMovementList)
async def get_cash_movements(
    cash_register_id: Optional[UUID] = Query(None, description="Filtrar por caja específica"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Listar movimientos de caja con filtros opcionales.
    
    Query Parameters:
    - **cash_register_id**: Filtrar por caja específica
    - **limit**: Número máximo de resultados (1-1000)
    - **offset**: Número de registros a saltar
    
    Incluye resumen por tipo de movimiento
    Ordenamiento: Por fecha de creación descendente
    """
    service = CashMovementService(db)
    result = service.get_movements(
        cash_register_id=cash_register_id,
        tenant_id=auth_context.tenant_id,
        limit=limit,
        offset=offset
    )
    
    return CashMovementList(
        movements=result["movements"],
        summary=result["summary"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"]
    )


# ===== SELLERS ROUTER =====

sellers_router = APIRouter(prefix="/sellers", tags=["POS"])


@sellers_router.post("/", response_model=SellerOut, status_code=status.HTTP_201_CREATED)
async def create_seller(
    seller_data: SellerCreate,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Crear nuevo vendedor.
    
    - **name**: Nombre completo del vendedor
    - **email**: Email (opcional, debe ser único)
    - **phone**: Teléfono de contacto
    - **document**: Documento de identidad (opcional, debe ser único)
    - **commission_rate**: Tasa de comisión (0-1)
    - **base_salary**: Salario base
    - **notes**: Notas adicionales
    
    Validaciones:
    - Email único por tenant (si se proporciona)
    - Documento único por tenant (si se proporciona)
    - Solo owner/admin pueden crear vendedores
    """
    service = SellerService(db)
    return service.create_seller(
        seller_data=seller_data,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


@sellers_router.get("/", response_model=SellerList)
async def get_sellers(
    active_only: bool = Query(False, description="Solo vendedores activos"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Listar vendedores con filtros opcionales.
    
    Query Parameters:
    - **active_only**: Mostrar solo vendedores activos
    - **limit**: Número máximo de resultados (1-1000)
    - **offset**: Número de registros a saltar
    
    Ordenamiento: Por nombre alfabético
    """
    service = SellerService(db)
    result = service.get_sellers(
        tenant_id=auth_context.tenant_id,
        active_only=active_only,
        limit=limit,
        offset=offset
    )
    
    return SellerList(
        sellers=result["sellers"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"]
    )


@sellers_router.get("/{seller_id}", response_model=SellerOut)
async def get_seller(
    seller_id: UUID = Path(..., description="ID del vendedor"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Obtener vendedor específico por ID.
    
    Retorna información completa del vendedor incluyendo:
    - Datos personales y de contacto
    - Configuración de comisiones
    - Estado activo/inactivo
    - Fechas de creación y actualización
    """
    service = SellerService(db)
    return service.get_seller_by_id(
        seller_id=seller_id,
        tenant_id=auth_context.tenant_id
    )


@sellers_router.patch("/{seller_id}", response_model=SellerOut)
async def update_seller(
    seller_id: UUID = Path(..., description="ID del vendedor"),
    seller_data: SellerUpdate = ...,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Actualizar vendedor existente.
    
    Permite actualización parcial de campos:
    - Solo se actualizan los campos proporcionados
    - Validaciones de unicidad para email y documento
    - Solo owner/admin pueden actualizar vendedores
    """
    service = SellerService(db)
    return service.update_seller(
        seller_id=seller_id,
        seller_data=seller_data,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


@sellers_router.delete("/{seller_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seller(
    seller_id: UUID = Path(..., description="ID del vendedor"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Desactivar vendedor (soft delete).
    
    - Marca el vendedor como inactivo
    - Establece deleted_at timestamp
    - No elimina el registro físicamente
    - Solo owner/admin pueden desactivar vendedores
    
    Nota: Vendedores con ventas asociadas no pueden ser eliminados
    """
    service = SellerService(db)
    service.delete_seller(
        seller_id=seller_id,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )
    
    return {"message": "Vendedor desactivado exitosamente"}


# ===== POS INVOICES ROUTER =====

pos_invoices_router = APIRouter(prefix="/pos/sales", tags=["POS"])

# Shift endpoints (current shift is derived from current open cash register)
shift_router = APIRouter(prefix="/pos/shift", tags=["POS"])


@shift_router.get("/current", response_model=CashRegisterOut)
async def get_current_shift(
    pdv_id: UUID = Query(..., description="ID del punto de venta"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    Devuelve el turno actual vinculado al PDV.

    Nota: En este diseño, el turno actual es 1:1 con la caja abierta actual.
    """
    service = CashRegisterService(db)
    register = service.get_current_cash_register(
        tenant_id=auth_context.tenant_id,
        pdv_id=pdv_id
    )
    if not register:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay turno/caja abierto para este PDV")
    return register


@pos_invoices_router.post("/", response_model=POSInvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_pos_sale(
    sale_data: POSInvoiceCreate,
    pdv_id: UUID = Query(..., description="ID del punto de venta"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    Crear venta POS completa con pagos automáticos.
    
    - **customer_id**: Cliente de la venta
    - **seller_id**: Vendedor asociado
    - **items**: Lista de productos con cantidades
    - **payments**: Lista de pagos (debe cubrir el total)
    - **notes**: Notas de la venta
    
    Proceso completo:
    1. Valida caja abierta en PDV
    2. Crea factura type=POS 
    3. Descuenta stock automáticamente
    4. Registra pagos obligatorios
    5. Genera movimientos de caja
    6. Maneja vuelto si aplica
    
    Validaciones:
    - Caja abierta obligatoria
    - Stock suficiente por producto
    - Pagos deben cubrir total mínimo
    - Cliente y vendedor activos
    """
    service = POSInvoiceService(db)
    return service.create_pos_sale(
        sale_data=sale_data,
        pdv_id=pdv_id,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


@pos_invoices_router.get("/", response_model=List[POSInvoiceOut])
async def get_pos_sales(
    start_date: Optional[date] = Query(None, description="Fecha inicial"),
    end_date: Optional[date] = Query(None, description="Fecha final"),
    seller_id: Optional[UUID] = Query(None, description="Filtrar por vendedor"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Listar ventas POS con filtros opcionales.
    
    Query Parameters:
    - **start_date**: Fecha inicial del filtro
    - **end_date**: Fecha final del filtro  
    - **seller_id**: Filtrar por vendedor específico
    - **limit**: Número máximo de resultados
    - **offset**: Número de registros a saltar
    
    Retorna solo facturas con type=POS
    Ordenamiento: Por fecha de emisión descendente
    """
    # Implementar en el service correspondiente
    # Por ahora retornamos lista vacía
    return []


@pos_invoices_router.get("/{invoice_id}", response_model=POSInvoiceDetail)
async def get_pos_sale_detail(
    invoice_id: UUID = Path(..., description="ID de la factura POS"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    Obtener detalle completo de venta POS.
    
    Incluye:
    - Información básica de la factura
    - Ítems con productos y cantidades
    - Pagos registrados por método
    - Movimientos de caja generados
    - Información de cliente y vendedor
    """
    # Implementar en el service correspondiente
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint en desarrollo"
    )


# ===== REPORTS ROUTER =====

reports_router = APIRouter(prefix="/reports", tags=["POS Reports"])


@reports_router.post("/sales-by-seller", response_model=SalesBySellerResponse)
async def get_sales_by_seller_report(
    date_range: DateRangeSchema,
    seller_id: Optional[UUID] = Query(None, description="Filtro por vendedor específico"),
    include_commissions: bool = Query(True, description="Incluir cálculo de comisiones"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    📊 Reporte de ventas por vendedor con performance individual y comisiones.
    
    **Incluye:**
    - Total de ventas y monto por vendedor
    - Ticket promedio y rangos de venta
    - Días activos y ventas por día
    - Cálculo de comisiones estimadas
    - Participación de mercado
    - Ranking por performance
    
    **Permisos:** Owner, Admin, Accountant
    """
    try:
        reports_service = POSReportsService(db)
        date_range_obj = DateRange(
            start_date=date_range.start_date,
            end_date=date_range.end_date
        )
        
        return reports_service.get_sales_by_seller_report(
            tenant_id=auth_context.tenant_id,
            date_range=date_range_obj,
            seller_id=seller_id,
            pdv_id=auth_context.pdv_id,
            include_commissions=include_commissions
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando reporte de ventas por vendedor: {str(e)}"
        )


@reports_router.post("/cash-audit", response_model=CashAuditResponse)
async def get_cash_audit_report(
    date_range: DateRangeSchema,
    include_trends: bool = Query(True, description="Incluir análisis de tendencias"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    📊 Reporte de arqueos detallados con diferencias históricas y tendencias.
    
    **Incluye:**
    - Arqueos por caja con diferencias calculadas
    - Análisis de exactitud y porcentajes de error
    - Tendencias históricas de diferencias
    - Clasificación por sobrantes/faltantes
    - Recomendaciones de mejora
    
    **Permisos:** Owner, Admin, Accountant
    """
    try:
        reports_service = POSReportsService(db)
        date_range_obj = DateRange(
            start_date=date_range.start_date,
            end_date=date_range.end_date
        )
        
        return reports_service.get_cash_audit_report(
            tenant_id=auth_context.tenant_id,
            date_range=date_range_obj,
            pdv_id=auth_context.pdv_id,
            include_trends=include_trends
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando reporte de arqueos: {str(e)}"
        )


@reports_router.post("/shift-analysis", response_model=ShiftAnalysisResponse)
async def get_shift_analysis_report(
    date_range: DateRangeSchema,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    📊 Análisis comparativo por turnos (mañana, tarde, noche).
    
    **Turnos definidos:**
    - Mañana: 06:00 - 14:00
    - Tarde: 14:00 - 22:00  
    - Noche: 22:00 - 06:00
    
    **Incluye:**
    - Ventas y montos por turno
    - Vendedores activos por turno
    - Ticket promedio por turno
    - Comparación de performance
    - Recomendaciones de optimización
    
    **Permisos:** Owner, Admin, Accountant
    """
    try:
        reports_service = POSReportsService(db)
        date_range_obj = DateRange(
            start_date=date_range.start_date,
            end_date=date_range.end_date
        )
        
        return reports_service.get_shift_analysis_report(
            tenant_id=auth_context.tenant_id,
            date_range=date_range_obj,
            pdv_id=auth_context.pdv_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando análisis de turnos: {str(e)}"
        )


@reports_router.post("/top-products", response_model=TopProductsResponse)
async def get_top_products_report(
    date_range: DateRangeSchema,
    limit: int = Query(20, ge=1, le=100, description="Número máximo de productos"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "seller"])),
    db: Session = Depends(get_db)
):
    """
    📊 Reporte de productos más vendidos en punto de venta.
    
    **Incluye:**
    - Ranking por cantidad vendida
    - Ingresos generados por producto
    - Número de facturas que incluyen el producto
    - Vendedores que han vendido cada producto
    - Participación en ventas totales
    - Índice de concentración de ventas
    
    **Permisos:** Owner, Admin, Accountant, Seller
    """
    try:
        reports_service = POSReportsService(db)
        date_range_obj = DateRange(
            start_date=date_range.start_date,
            end_date=date_range.end_date
        )
        
        return reports_service.get_top_products_report(
            tenant_id=auth_context.tenant_id,
            date_range=date_range_obj,
            pdv_id=auth_context.pdv_id,
            limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando reporte de top productos: {str(e)}"
        )


# ===== ADVANCED PAYMENTS ROUTER =====

payments_router = APIRouter(prefix="/payments", tags=["POS Advanced Payments"])


@payments_router.post("/mixed", response_model=MixedPaymentResponse)
async def process_mixed_payment(
    payment_request: MixedPaymentRequest,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    💳 Procesar pago mixto (efectivo + tarjeta + otros métodos).
    
    **Funcionalidades:**
    - Múltiples métodos de pago en una venta
    - Cálculo automático de vuelto
    - Validación de montos y métodos
    - Integración con caja registradora
    - Registro de movimientos por método
    
    **Ejemplo de uso:**
    ```json
    {
        "invoice_id": "uuid-factura",
        "payments": [
            {"method": "cash", "amount": 50000, "notes": "Efectivo"},
            {"method": "card", "amount": 30000, "reference": "VISA-1234"}
        ],
        "cash_register_id": "uuid-caja"
    }
    ```
    
    **Permisos:** Owner, Admin, Seller, Cashier
    """
    try:
        payment_service = AdvancedPaymentService(db)
        
        return payment_service.process_mixed_payment(
            invoice_id=payment_request.invoice_id,
            mixed_payments=[p.model_dump() for p in payment_request.payments],
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            cash_register_id=payment_request.cash_register_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando pago mixto: {str(e)}"
        )


@payments_router.post("/qr/generate", response_model=QRPaymentResponse)
async def generate_qr_payment(
    qr_request: QRPaymentRequest,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    📱 Generar código QR para pago con billetera digital.
    
    **Proveedores soportados:**
    - Nequi
    - DaviPlata
    - Bancolombia QR
    - PSE
    - QR Genérico
    
    **Proceso:**
    1. Genera código QR único
    2. Crea datos específicos del proveedor
    3. Establece tiempo de expiración
    4. Retorna instrucciones para el usuario
    
    **Ejemplo de respuesta:**
    ```json
    {
        "qr_code": "ABC123XYZ789",
        "qr_data": "nequi://pay?amount=50000&ref=POS-001",
        "expires_at": "2025-10-08T15:30:00Z",
        "instructions": {
            "title": "Pago con Nequi",
            "steps": ["Abre Nequi", "Escanea QR", "Confirma"]
        }
    }
    ```
    
    **Permisos:** Owner, Admin, Seller, Cashier
    """
    try:
        payment_service = AdvancedPaymentService(db)
        
        return payment_service.generate_qr_payment(
            invoice_id=qr_request.invoice_id,
            amount=qr_request.amount,
            provider=qr_request.provider,
            tenant_id=auth_context.tenant_id,
            expires_in_minutes=qr_request.expires_in_minutes
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando QR de pago: {str(e)}"
        )


@payments_router.post("/qr/status", response_model=QRPaymentStatusResponse)
async def check_qr_payment_status(
    status_request: QRPaymentStatusRequest,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    🔍 Verificar estado de pago QR.
    
    **Estados posibles:**
    - `pending`: Esperando pago del usuario
    - `processing`: Pago en proceso de confirmación
    - `completed`: Pago exitoso confirmado
    - `failed`: Pago falló o fue rechazado
    - `expired`: QR expirado sin pago
    
    **Uso típico:**
    - Polling cada 5-10 segundos mientras está pendiente
    - Actualización de UI según el estado
    - Confirmación automática cuando se completa
    
    **Permisos:** Owner, Admin, Seller, Cashier
    """
    try:
        payment_service = AdvancedPaymentService(db)
        
        return payment_service.verify_qr_payment_status(
            qr_code=status_request.qr_code,
            tenant_id=auth_context.tenant_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verificando estado de QR: {str(e)}"
        )


@payments_router.post("/validate", response_model=PaymentValidationResponse)
async def validate_payment_methods(
    payment_request: MixedPaymentRequest,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    ✅ Validar métodos y límites de pago antes de procesar.
    
    **Validaciones incluidas:**
    - Límites por método de pago
    - Restricciones por tenant
    - Validación de montos mínimos/máximos
    - Detección de patrones sospechosos
    
    **Respuesta:**
    ```json
    {
        "valid": true,
        "warnings": ["Monto alto detectado en efectivo"],
        "errors": []
    }
    ```
    
    **Uso recomendado:**
    - Validar antes de mostrar métodos de pago
    - Advertir al usuario sobre límites
    - Prevenir errores en el procesamiento
    
    **Permisos:** Owner, Admin, Seller, Cashier
    """
    try:
        payment_service = AdvancedPaymentService(db)
        
        return payment_service.validate_payment_limits(
            tenant_id=auth_context.tenant_id,
            payment_data=[p.model_dump() for p in payment_request.payments]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validando métodos de pago: {str(e)}"
        )


# ===============================
# MULTI-CASH ENDPOINTS (v1.3.0)
# ===============================

multi_cash_router = APIRouter(prefix="/multi-cash", tags=["Multi-Cash Management"])

@multi_cash_router.post("/session/create", response_model=MultiCashSessionResponse)
async def create_multi_cash_session(
    session_data: MultiCashSessionCreate,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor"])),
    db: Session = Depends(get_db)
):
    """
    🏪 **Crear Sesión Multi-Caja**
    
    Permite abrir múltiples cajas registradoras simultáneamente en el mismo PDV.
    Ideal para períodos de alta demanda o turnos solapados.
    
    **Características:**
    - ✅ Caja principal + cajas secundarias
    - ✅ Balanceador de carga automático
    - ✅ Supervisión centralizada
    - ✅ Validación de permisos por ubicación
    
    **Permisos requeridos:** Owner, Admin, Supervisor
    
    **Ejemplo:**
    ```json
    {
        "location_id": "550e8400-e29b-41d4-a716-446655440000",
        "primary_balance": 200000.00,
        "secondary_balances": [100000.00, 150000.00],
        "session_notes": "Black Friday - Turno intensivo",
        "enable_load_balancing": true,
        "allow_existing": false
    }
    ```
    """
    try:
        service = MultiCashService(db)
        return service.create_multi_cash_session(
            session_data, 
            auth_context.user, 
            auth_context.tenant_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando sesión multi-caja: {str(e)}"
        )

@multi_cash_router.get("/load-balancing/suggest")
async def get_load_balancing_suggestion(
    location_id: UUID,
    sale_amount: Decimal,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    ⚖️ **Sugerencia de Balanceador de Carga**
    
    Recomienda la mejor caja registradora para procesar una nueva venta
    basado en algoritmos de distribución de carga.
    
    **Factores considerados:**
    - 📊 Número de ventas actuales
    - 💰 Monto acumulado por caja
    - ⚡ Balance actual de efectivo
    - 🎯 Capacidad operativa
    
    **Algoritmos disponibles:**
    - `least_loaded`: Menor carga de trabajo
    - `round_robin`: Rotación secuencial
    - `sales_based`: Basado en monto de ventas
    
    **Respuesta incluye:**
    - Caja recomendada con justificación
    - Métricas de todas las cajas activas
    - Efectividad del balanceador
    """
    try:
        service = MultiCashService(db)
        return service.get_load_balancing_suggestion(
            location_id, 
            auth_context.tenant_id, 
            sale_amount
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo sugerencia de balanceador: {str(e)}"
        )

@multi_cash_router.post("/shift/transfer", response_model=ShiftTransferResponse)
async def transfer_shift(
    transfer_data: ShiftTransferRequest,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    🔄 **Transferencia de Turno**
    
    Permite transferir la responsabilidad de cajas registradoras entre operadores
    sin necesidad de cerrar las cajas, facilitando turnos solapados.
    
    **Proceso automático:**
    1. ✅ Valida permisos del operador actual
    2. 📊 Calcula balance intermedio de cajas
    3. 📝 Registra movimiento de transferencia
    4. 🔔 Notifica al nuevo operador
    5. 📋 Genera reporte de transferencia
    
    **Casos de uso:**
    - Cambios de turno sin interrumpir operaciones
    - Transferencia por descansos o emergencias
    - Rotación de personal en horas pico
    - Supervisión temporal de cajas
    
    **Permisos:** Owner, Admin, Supervisor, Operador actual
    """
    try:
        service = MultiCashService(db)
        return service.transfer_shift(
            transfer_data, 
            auth_context.user, 
            auth_context.tenant_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en transferencia de turno: {str(e)}"
        )

@multi_cash_router.post("/audit/consolidated", response_model=ConsolidatedAuditResponse)
async def consolidated_audit(
    location_id: UUID,
    register_ids: List[UUID],
    audit_date: Optional[date] = None,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "supervisor"])),
    db: Session = Depends(get_db)
):
    """
    🔍 **Auditoría Consolidada**
    
    Realiza una auditoría integral de múltiples cajas registradoras,
    proporcionando un análisis completo del desempeño y precisión.
    
    **Métricas incluidas:**
    - 💰 Balances consolidados (apertura, actual, diferencias)
    - 📊 Movimientos totales y por tipo
    - 🎯 Análisis de ventas y tickets promedio
    - ⚖️ Distribución de carga entre cajas
    - 📈 KPIs de eficiencia operativa
    
    **Recomendaciones automáticas:**
    - Optimización de distribución de ventas
    - Identificación de cajas inactivas
    - Sugerencias de rebalanceo
    - Alertas de alta actividad
    
    **Permisos:** Owner, Admin, Accountant, Supervisor
    """
    try:
        service = MultiCashService(db)
        return service.consolidate_audit(
            location_id, 
            register_ids, 
            auth_context.tenant_id, 
            audit_date
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en auditoría consolidada: {str(e)}"
        )

@multi_cash_router.post("/session/close")
async def close_multi_cash_session(
    session_close_data: MultiCashSessionClose,
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor"])),
    db: Session = Depends(get_db)
):
    """
    🔐 **Cerrar Sesión Multi-Caja**
    
    Cierra todas las cajas de una sesión multi-caja con auditoría consolidada
    y cálculo automático de diferencias y ajustes.
    
    **Proceso automático:**
    1. ✅ Valida permisos de cierre
    2. 📊 Calcula balance teórico vs declarado
    3. 💸 Genera ajustes por diferencias
    4. 📋 Consolida métricas de la sesión
    5. 🏆 Calcula porcentaje de precisión
    
    **Datos de respuesta:**
    - Resumen de cada caja cerrada
    - Diferencias totales y por caja
    - Métricas consolidadas de precisión
    - Recomendaciones para futuras sesiones
    
    **Permisos:** Owner, Admin, Supervisor
    """
    try:
        service = MultiCashService(db)
        return service.close_multi_cash_session(
            session_close_data, 
            auth_context.user, 
            auth_context.tenant_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cerrando sesión multi-caja: {str(e)}"
        )


# ===============================
# REAL-TIME ANALYTICS ENDPOINTS (v1.3.0)
# ===============================

analytics_router = APIRouter(prefix="/analytics", tags=["Real-Time Analytics"])

@analytics_router.get("/dashboard/live", response_model=LiveDashboardResponse)
async def get_live_dashboard(
    location_id: Optional[UUID] = Query(None, description="ID del PDV (opcional, todas las ubicaciones si es None)"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    📊 **Dashboard en Tiempo Real**
    
    Proporciona un dashboard completo con métricas en vivo para monitoreo 
    operativo y toma de decisiones inmediatas.
    
    **Métricas incluidas:**
    - 💰 Ventas del día y hora actual
    - 🏪 Estado de cajas registradoras activas
    - 📈 Desglose por horas de ventas
    - 🏆 Top productos del día
    - 📊 Comparaciones vs ayer y semana pasada
    - 🚨 Alertas activas del sistema
    - ⚡ Indicadores de performance (velocidad, conversión)
    
    **Actualizaciones automáticas:**
    - Datos se actualizan cada 30 segundos
    - WebSocket disponible para updates en tiempo real
    - Cálculos eficientes para respuesta rápida
    
    **Casos de uso:**
    - Monitoreo de gerentes y supervisores
    - Dashboard en pantallas de control
    - Toma de decisiones operativas
    - Identificación de oportunidades y problemas
    
    **Permisos:** Owner, Admin, Supervisor, Accountant
    """
    try:
        service = RealTimeAnalyticsService(db)
        return service.get_live_dashboard(location_id, auth_context.tenant_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo dashboard en vivo: {str(e)}"
        )

@analytics_router.get("/targets/check", response_model=SalesTargetCheck)
async def check_sales_targets(
    location_id: Optional[UUID] = Query(None, description="ID del PDV"),
    daily_target: Optional[Decimal] = Query(None, description="Meta diaria de ventas"),
    monthly_target: Optional[Decimal] = Query(None, description="Meta mensual de ventas"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor"])),
    db: Session = Depends(get_db)
):
    """
    🎯 **Verificación de Metas de Ventas**
    
    Monitorea el progreso hacia las metas de ventas diarias y mensuales,
    proporcionando alertas tempranas y recomendaciones.
    
    **Análisis incluido:**
    - ✅ Progreso diario vs meta establecida
    - 📅 Progreso mensual con proyección
    - 📊 Porcentaje de cumplimiento actual
    - 💡 Recomendaciones automáticas
    - 🚨 Alertas de metas en riesgo
    
    **Cálculos inteligentes:**
    - Progreso esperado basado en días transcurridos
    - Proyección de cumplimiento final
    - Velocidad de ventas necesaria para cumplir
    - Identificación de tendencias positivas/negativas
    
    **Recomendaciones automáticas:**
    - Estrategias para acelerar ventas
    - Ajustes de metas realistas
    - Promociones sugeridas
    - Optimización de horarios
    
    **Permisos:** Owner, Admin, Supervisor
    """
    try:
        service = RealTimeAnalyticsService(db)
        return service.check_sales_targets(
            location_id, 
            auth_context.tenant_id, 
            daily_target, 
            monthly_target
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verificando metas de ventas: {str(e)}"
        )

@analytics_router.get("/predictions", response_model=PredictiveAnalyticsResponse)
async def get_predictive_analytics(
    location_id: Optional[UUID] = Query(None, description="ID del PDV"),
    prediction_days: int = Query(7, ge=1, le=30, description="Días a predecir (1-30)"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor"])),
    db: Session = Depends(get_db)
):
    """
    🔮 **Analytics Predictivo con IA**
    
    Utiliza machine learning básico e inteligencia artificial para predecir
    tendencias futuras y proporcionar insights accionables.
    
    **Predicciones incluidas:**
    - 📈 Forecast de ventas para próximos días
    - 📊 Análisis de tendencias recientes
    - 🔄 Patrones estacionales identificados
    - 📦 Alertas de stock que se agotará
    - 💹 Predicción de demanda por producto
    
    **Algoritmos utilizados:**
    - Regresión lineal para ventas
    - Análisis de series temporales
    - Detección de patrones estacionales
    - Algoritmos de demanda basados en histórico
    
    **Nivel de confianza:**
    - Indicador de confiabilidad (0-100%)
    - Factores que afectan la precisión
    - Recomendaciones de mejora de datos
    
    **Casos de uso:**
    - Planificación de inventario
    - Estrategias de marketing
    - Asignación de personal
    - Presupuestos y proyecciones
    
    **Permisos:** Owner, Admin, Supervisor
    """
    try:
        service = RealTimeAnalyticsService(db)
        return service.get_predictive_analytics(
            location_id, 
            auth_context.tenant_id, 
            prediction_days
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando analytics predictivo: {str(e)}"
        )

@analytics_router.get("/alerts", response_model=List[AlertResponse])
async def get_live_alerts(
    location_id: Optional[UUID] = Query(None, description="ID del PDV"),
    alert_types: Optional[List[str]] = Query(None, description="Tipos de alerta: stock, sales, cash, system"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor", "seller", "cashier"])),
    db: Session = Depends(get_db)
):
    """
    🚨 **Alertas en Tiempo Real**
    
    Sistema integral de alertas automáticas para identificar problemas
    operativos y oportunidades de mejora en tiempo real.
    
    **Tipos de alertas:**
    - 📦 **Stock**: Productos con bajo inventario, agotados, sobrestock
    - 💰 **Sales**: Metas en riesgo, caídas en ventas, picos inusuales
    - 🏪 **Cash**: Diferencias en arqueos, saldos altos, movimientos sospechosos
    - ⚙️ **System**: Errores técnicos, rendimiento, conexiones
    
    **Niveles de prioridad:**
    - 🔴 **Critical**: Requiere acción inmediata
    - 🟠 **High**: Atención urgente necesaria
    - 🟡 **Medium**: Revisar pronto
    - 🟢 **Low**: Informativo
    
    **Características avanzadas:**
    - Detección automática de patrones anómalos
    - Alertas personalizables por ubicación
    - Sistema de acknowledgment
    - Historial de alertas
    - Integración con notificaciones push
    
    **Filtros disponibles:**
    - Por tipo de alerta
    - Por nivel de prioridad
    - Por ubicación específica
    - Por estado (activa, resuelta, ignorada)
    
    **Permisos:** Todos los roles operativos
    """
    try:
        service = RealTimeAnalyticsService(db)
        return service.get_live_alerts(
            location_id, 
            auth_context.tenant_id, 
            alert_types
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo alertas en vivo: {str(e)}"
        )

@analytics_router.get("/comparative", response_model=ComparativeAnalyticsResponse)
async def get_comparative_analytics(
    comparison_period: str = Query("week", regex="^(day|week|month|year)$", description="Período de comparación"),
    location_id: Optional[UUID] = Query(None, description="ID del PDV"),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "supervisor", "accountant"])),
    db: Session = Depends(get_db)
):
    """
    📊 **Analytics Comparativo**
    
    Análisis detallado comparando el rendimiento actual con períodos anteriores
    para identificar tendencias, patrones y oportunidades de mejora.
    
    **Períodos de comparación:**
    - 📅 **Day**: Hoy vs Ayer
    - 📆 **Week**: Esta semana vs Semana pasada
    - 🗓️ **Month**: Este mes vs Mes pasado
    - 📋 **Year**: Este año vs Año pasado
    
    **Métricas comparadas:**
    - 💰 Ventas totales (cantidad y monto)
    - 🎯 Ticket promedio
    - 📈 Tasa de crecimiento
    - 🔄 Tendencias identificadas
    
    **Análisis incluido:**
    - Cambios absolutos y porcentuales
    - Identificación de tendencias (alza, baja, estable)
    - Factores que explican las variaciones
    - Proyecciones basadas en tendencias
    
    **Insights automáticos:**
    - Mejores y peores días/períodos
    - Patrones estacionales
    - Impacto de promociones o eventos
    - Recomendaciones estratégicas
    
    **Visualización sugerida:**
    - Gráficos de barras comparativos
    - Líneas de tendencia
    - Indicadores de crecimiento
    - Alertas de cambios significativos
    
    **Permisos:** Owner, Admin, Supervisor, Accountant
    """
    try:
        service = RealTimeAnalyticsService(db)
        return service.get_comparative_analytics(
            location_id, 
            auth_context.tenant_id, 
            comparison_period
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando analytics comparativo: {str(e)}"
        )