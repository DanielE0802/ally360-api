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

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from app.modules.pos.services import (
    CashRegisterService, CashMovementService, 
    SellerService, POSInvoiceService
)
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
    
    # Enums
    CashRegisterStatus, MovementType
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
    
    Validaciones:
    - Solo una caja abierta por PDV simultáneamente
    - PDV debe existir y pertenecer al tenant
    - Usuario debe tener permisos de caja
    """
    service = CashRegisterService(db)
    return service.open_cash_register(
        register_data=register_data,
        pdv_id=pdv_id,
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id
    )


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