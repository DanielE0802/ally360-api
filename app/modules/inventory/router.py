from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.modules.auth.dependencies import get_auth_context, require_owner_or_admin, AuthDependencies
from app.modules.auth.schemas import AuthContext
from app.dependencies.dbDependecies import get_db
from app.modules.inventory.service import InventoryService
from app.modules.inventory.schemas import (
    StockOut, StockUpdate, InventoryMovementCreate, InventoryMovementOut,
    TransferMovementCreate, ProductStockSummary, MovementType
)

stock_router = APIRouter(prefix="/stock", tags=["Stock Management"])

@stock_router.get("/product/{product_id}", response_model=List[StockOut])
def get_product_stock(
    product_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get stock for a product across all PDVs."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.get_stock_by_product(auth_context.tenant_id, product_id)

@stock_router.get("/product/{product_id}/summary", response_model=ProductStockSummary)
def get_product_stock_summary(
    product_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get complete stock summary for a product."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.get_product_stock_summary(auth_context.tenant_id, product_id)

@stock_router.get("/product/{product_id}/pdv/{pdv_id}", response_model=StockOut)
def get_stock_by_product_and_pdv(
    product_id: UUID,
    pdv_id: UUID,
    variant_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get stock for specific product at specific PDV."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.get_stock_by_product_and_pdv(
        auth_context.tenant_id, product_id, pdv_id, variant_id
    )

@stock_router.patch("/product/{product_id}/pdv/{pdv_id}", response_model=StockOut)
def adjust_stock(
    product_id: UUID,
    pdv_id: UUID,
    stock_data: StockUpdate,
    variant_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Manually adjust stock quantity (admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.adjust_stock(
        auth_context.tenant_id, 
        product_id, 
        pdv_id, 
        stock_data, 
        auth_context.user_id,
        variant_id
    )

movements_router = APIRouter(prefix="/movements", tags=["Inventory Movements"])

@movements_router.post("/", response_model=InventoryMovementOut)
def create_movement(
    movement_data: InventoryMovementCreate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Create inventory movement and update stock."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.create_movement(
        auth_context.tenant_id, 
        movement_data, 
        auth_context.user_id
    )

@movements_router.post("/transfer", response_model=List[InventoryMovementOut])
def transfer_stock(
    transfer_data: TransferMovementCreate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Transfer stock between PDVs."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.transfer_stock(
        auth_context.tenant_id, 
        transfer_data, 
        auth_context.user_id
    )

@movements_router.get("/", response_model=List[InventoryMovementOut])
def get_movements(
    product_id: Optional[UUID] = Query(None),
    pdv_id: Optional[UUID] = Query(None),
    movement_type: Optional[MovementType] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get inventory movements with filters."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service = InventoryService(db)
    return service.get_movements(
        auth_context.tenant_id,
        product_id=product_id,
        pdv_id=pdv_id,
        movement_type=movement_type,
        limit=limit,
        offset=offset
    )