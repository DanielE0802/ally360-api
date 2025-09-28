from fastapi import APIRouter, status, Depends, HTTPException, Query
from uuid import UUID
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dependencies.dbDependecies import get_db
from app.modules.auth.dependencies import get_auth_context, require_owner_or_admin, AuthDependencies
from app.modules.auth.schemas import AuthContext
from app.modules.products import service
from app.modules.products.schemas import ConfigurableProductCreate, SimpleProductWithStockCreate, ProductOut, ProductVariantOut, StockOut, ProductOutWithPdvs, ProductOutDefault
from app.modules.inventory.service import InventoryService

product_router = APIRouter(prefix="/products", tags=["Products"])

@product_router.post("/", response_model=ProductOut)
def create_product(
    data: ConfigurableProductCreate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Create a new product (owner/admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    # Create product
    product = service.create_product_with_variants(db, data, auth_context.tenant_id)
    
    # Create stock records for all PDVs
    inventory_service = InventoryService(db)
    inventory_service.create_stock_for_new_product(auth_context.tenant_id, product.id)
    
    return product

@product_router.post("/simple", response_model=ProductOutDefault)
def create_simple_product(
    data: SimpleProductWithStockCreate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Create a simple product (owner/admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    print(f"DEBUG: auth_context.tenant_id = {auth_context.tenant_id}")
    print(f"DEBUG: auth_context.tenant_id type = {type(auth_context.tenant_id)}")
    
    # Create product (stocks are created within this function)
    product = service.create_simple_product(db, data, auth_context.tenant_id)
    
    return product

@product_router.get("/", response_model=List[ProductOutWithPdvs])
def list_products(
    category_id: Optional[UUID] = Query(None),
    brand_id: Optional[UUID] = Query(None),
    name: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """List products with filters."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.get_all_products(
        db, 
        auth_context.tenant_id,
        category_id=category_id,
        brand_id=brand_id,
        name=name,
        limit=limit,
        offset=offset
    )

@product_router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get product by ID."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.get_product_by_id(db, auth_context.tenant_id, product_id)

@product_router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: UUID,
    data: dict,  # TODO: Create proper update schema
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Update product (owner/admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.update_product(db, auth_context.tenant_id, product_id, data)

@product_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Delete product (owner/admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    service.delete_product(db, auth_context.tenant_id, product_id)

@product_router.get("/{product_id}/variants", response_model=List[ProductVariantOut])
def get_variants(
    product_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get product variants."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.get_variants_by_product(db, product_id, auth_context.tenant_id)