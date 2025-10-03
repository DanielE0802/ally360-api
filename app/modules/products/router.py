from fastapi import APIRouter, status, Depends, HTTPException, Query, UploadFile, File
from uuid import UUID
from typing import List, Optional, Annotated
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.dbDependecies import get_db
from app.database.database import get_async_db
from app.modules.auth.dependencies import get_auth_context, require_owner_or_admin, AuthDependencies
from app.modules.auth.schemas import AuthContext
from app.modules.products import service
from app.modules.products.schemas import (
    ConfigurableProductCreate, 
    SimpleProductWithStockCreate, 
    ProductOut, 
    ProductVariantOut, 
    StockOut, 
    ProductOutWithPdvs, 
    ProductOutDefault,
    GetProductResponse,
    PaginatedProductResponse,
    ProductPDVResponse,
    PaginatedProductPDVResponse,
    ProductImageCreate,
    ProductImageOut,
    ImageUploadResponse,
    LowStockResponse
)
from app.modules.inventory.service import InventoryService
from app.modules.taxes.service import TaxService
from app.modules.taxes.schemas import TaxCalculation

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
    
    # Create product (stocks are created within this function)
    product = service.create_simple_product(db, data, auth_context.tenant_id)
    
    return product

@product_router.get("/", response_model=PaginatedProductResponse)
async def list_products(
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(10, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por nombre, SKU o descripción"),
    category_id: Optional[str] = Query(None, description="Filtrar por categoría"),
    brand_id: Optional[str] = Query(None, description="Filtrar por marca"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo")
):
    """Lista productos con filtros y paginación."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.get_products(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        page=page,
        limit=limit,
        search=search,
        category_id=category_id,
        brand_id=brand_id,
        is_active=is_active
    )

@product_router.get("/stock", response_model=LowStockResponse)
async def low_stock_products(
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    low_stock: bool = Query(False, description="Solo productos con stock crítico"),
):
    """Get products with low stock for the tenant."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    if not low_stock:
        return LowStockResponse(products=[], total_count=0)
    return await service.get_low_stock_products(db=db, tenant_id=str(auth_context.tenant_id))

@product_router.get("/{product_id}", response_model=GetProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Get product by ID."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.get_product_by_id_async(db, str(auth_context.tenant_id), product_id)

@product_router.patch("/{product_id}", response_model=GetProductResponse)
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


@product_router.post("/{product_id}/taxes")
def assign_taxes_to_product(
    product_id: UUID,
    tax_ids: List[UUID],
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """
    Asignar impuestos a un producto (owner/admin only).
    
    Reemplaza todos los impuestos existentes del producto con los nuevos.
    """
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    tax_service = TaxService(db)
    return tax_service.assign_taxes_to_product(product_id, tax_ids, auth_context.tenant_id)


@product_router.get("/{product_id}/taxes")
def get_product_taxes(
    product_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """
    Obtener impuestos asignados a un producto.
    """
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    tax_service = TaxService(db)
    return tax_service.get_product_taxes(product_id, auth_context.tenant_id)


@product_router.post("/{product_id}/calculate-taxes", response_model=List[TaxCalculation])
def calculate_product_taxes(
    product_id: UUID,
    base_amount: float = Query(..., ge=0, description="Base gravable"),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """
    Calcular impuestos de un producto para una base gravable específica.
    
    Útil para estimar impuestos antes de generar facturas.
    """
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    from decimal import Decimal
    from app.modules.taxes.calculator import TaxCalculator
    
    calculator = TaxCalculator(db)
    return calculator.calculate_product_taxes(product_id, Decimal(str(base_amount)), auth_context.tenant_id)


# Nuevos endpoints para manejo de productos con información por PDV

@product_router.get("/pdv", response_model=PaginatedProductPDVResponse)
async def list_products_with_pdv(
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    page: int = Query(1, ge=1, description="Número de página"),
    limit: int = Query(10, ge=1, le=100, description="Elementos por página"),
    search: Optional[str] = Query(None, description="Buscar por nombre, SKU o descripción"),
    category_id: Optional[str] = Query(None, description="Filtrar por categoría"),
    brand_id: Optional[str] = Query(None, description="Filtrar por marca"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    pdv_id: Optional[str] = Query(None, description="Filtrar por PDV específico"),
    low_stock_only: bool = Query(False, description="Mostrar solo productos con stock bajo")
):
    """Lista productos con información detallada por PDV."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.get_products_with_pdv(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        page=page,
        limit=limit,
        search=search,
        category_id=category_id,
        brand_id=brand_id,
        is_active=is_active,
        pdv_id=pdv_id,
        low_stock_only=low_stock_only
    )


@product_router.get("/{product_id}/pdv", response_model=ProductPDVResponse)
async def get_product_with_pdv(
    product_id: str,
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Obtiene un producto específico con información detallada por PDV."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.get_product_by_id_with_pdv(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        product_id=product_id
    )


@product_router.get("/alerts/low-stock", response_model=List[ProductPDVResponse])
async def get_low_stock_alerts(
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    pdv_id: Optional[str] = Query(None, description="Filtrar por PDV específico")
):
    """Obtiene productos con stock bajo para alertas."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.get_low_stock_products(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        pdv_id=pdv_id
    )


@product_router.patch("/{product_id}/stock/{pdv_id}/min-quantity")
async def update_min_stock(
    product_id: str,
    pdv_id: str,
    min_quantity: int = Query(..., ge=0, description="Nueva cantidad mínima"),
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Actualiza la cantidad mínima de stock para un producto en un PDV específico."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.update_min_stock(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        product_id=product_id,
        pdv_id=pdv_id,
        min_quantity=min_quantity
    )

# Endpoints para manejo de imágenes de productos

@product_router.post("/{product_id}/images", response_model=ImageUploadResponse)
async def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    is_primary: bool = Query(False, description="Si es la imagen principal"),
    sort_order: int = Query(0, description="Orden de visualización"),
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Sube una imagen para un producto."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    # Validar tipo de archivo
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Tipos permitidos: {', '.join(allowed_types)}"
        )
    
    # Validar tamaño (máximo 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo es demasiado grande. Tamaño máximo: 5MB"
        )
    
    try:
        image = await service.upload_product_image(
            db=db,
            tenant_id=str(auth_context.tenant_id),
            product_id=product_id,
            file_content=file_content,
            file_name=file.filename or "image",
            content_type=file.content_type,
            is_primary=is_primary,
            sort_order=sort_order
        )
        
        return ImageUploadResponse(
            success=True,
            message="Imagen subida exitosamente",
            image=image
        )
    except Exception as e:
        return ImageUploadResponse(
            success=False,
            message=f"Error subiendo imagen: {str(e)}",
            image=None
        )

@product_router.delete("/{product_id}/images/{image_id}")
async def delete_product_image(
    product_id: str,
    image_id: str,
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Elimina una imagen de producto."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.delete_product_image(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        product_id=product_id,
        image_id=image_id
    )

@product_router.get("/{product_id}/images", response_model=List[ProductImageOut])
async def get_product_images(
    product_id: str,
    db: AsyncSession = Depends(get_async_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role())
):
    """Obtiene todas las imágenes de un producto."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return await service.get_product_images(
        db=db,
        tenant_id=str(auth_context.tenant_id),
        product_id=product_id
    )