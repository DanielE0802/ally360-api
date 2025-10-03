class LowStockProduct(BaseModel):
    id: str
    name: str
    sku: str
    current_stock: int
    min_stock: int
    pdv_id: str
    pdv_name: str

class LowStockResponse(BaseModel):
    products: List[LowStockProduct]
    total_count: int
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime

# Schema base para paginación estándar
class PaginatedResponse(BaseModel):
    """Respuesta paginada estándar para todas las listas"""
    total: int
    page: int
    limit: int
    hasNext: bool
    hasPrev: bool

# Schemas básicos para relaciones
class CategoryResponse(BaseModel):
    """Información básica de categoría"""
    id: str
    name: str

    class Config:
        from_attributes = True

class BrandResponse(BaseModel):
    """Información básica de marca"""
    id: str
    name: str

    class Config:
        from_attributes = True

# Schema para información del producto por PDV
class ProductPDVInfo(BaseModel):
    """Información del producto por punto de venta"""
    pdv_id: str
    pdv_name: str
    quantity: int = 0
    min_quantity: int = 0
    
    class Config:
        from_attributes = True

# Schemas para manejo de imágenes
class ProductImageCreate(BaseModel):
    """Schema para crear imagen de producto"""
    is_primary: bool = False
    sort_order: int = 0

class ProductImageOut(BaseModel):
    """Schema de respuesta para imagen de producto"""
    id: str
    file_key: str
    file_name: str
    file_size: int
    content_type: str
    is_primary: bool
    sort_order: int
    url: str  # URL presignada para acceso
    
    class Config:
        from_attributes = True

class ImageUploadResponse(BaseModel):
    """Respuesta para subida de imagen"""
    success: bool
    message: str
    image: Optional[ProductImageOut] = None

# Schema principal del producto según la interfaz requerida
class GetProductResponse(BaseModel):
    """Schema de respuesta para obtener productos"""
    id: str
    name: str
    description: Optional[str] = None
    barCode: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    typeProduct: Literal['1', '2'] = '1'  # 1=Simple, 2=Configurable
    taxesOption: int = 0  # Cantidad de impuestos asignados
    sku: Optional[str] = None
    priceSale: float = 0.0
    priceBase: float = 0.0
    quantityStock: int = 0  # Total stock (suma de todos los PDVs)
    globalStock: int = 0  # Total stock (alias de quantityStock)
    state: Optional[bool] = True
    sellInNegative: Optional[bool] = False
    category: CategoryResponse
    brand: BrandResponse
    productPdv: List[ProductPDVInfo] = Field(default_factory=list)  # Stock por PDV
    
    # Campos calculados por el frontend (opcionales)
    inventoryType: Optional[Literal['Existencias', 'Sin existencias', 'Pocas existencias']] = None

    class Config:
        from_attributes = True

# Respuesta paginada para productos
class ProductListResponse(PaginatedResponse):
    """Respuesta paginada para lista de productos"""
    data: List[GetProductResponse]
    applied_filters: Optional[Dict[str, Any]] = None
    counts_by_status: List[Dict[str, Any]] = []

# Schemas para crear/actualizar productos (mantener compatibilidad)
class ProductCreate(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    barCode: Optional[str] = None
    typeProduct: Literal['1', '2'] = '1'
    priceSale: float = 0.0
    priceBase: float = 0.0
    state: bool = True
    sellInNegative: bool = False
    brand_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    tax_ids: Optional[List[UUID]] = Field(default_factory=list, description="Lista de IDs de impuestos a asignar")
    # Soporte para imágenes en base64
    images: Optional[List[str]] = Field(default_factory=list, description="Lista de imágenes en base64")

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    barCode: Optional[str] = None
    typeProduct: Optional[Literal['1', '2']] = None
    priceSale: Optional[float] = None
    priceBase: Optional[float] = None
    state: Optional[bool] = None
    sellInNegative: Optional[bool] = None
    brand_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    tax_ids: Optional[List[UUID]] = Field(None, description="Lista de IDs de impuestos a asignar")

# Schemas para variantes y stock (mantener funcionalidad existente)
class VariantCreate(BaseModel):
    color: Optional[str] = None
    size: Optional[str] = None
    sku: str
    price: float

class StockCreate(BaseModel):
    pdv_id: UUID
    quantity: int
    min_quantity: int = 0  # Cantidad mínima para alertas

class VariantWithStockCreate(VariantCreate):
    stocks: List[StockCreate]

class ConfigurableProductCreate(ProductCreate):
    variants: List[VariantWithStockCreate]

class SimpleProductWithStockCreate(ProductCreate):
    stocks: List[StockCreate]

# Schemas para respuestas detalladas (mantener compatibilidad)
class PDVOut(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None

    class Config:
        from_attributes = True

class StockOut(BaseModel):
    id: UUID
    quantity: int
    min_quantity: int
    pdv: PDVOut

    class Config:
        from_attributes = True

class StockPerPDV(BaseModel):
    pdv_id: UUID
    pdv_name: str
    quantity: int
    min_quantity: int
    is_low_stock: bool = False  # Indicador si el stock está bajo

class ProductPDVResponse(BaseModel):
    """Schema para la respuesta de productos con información específica por PDV"""
    id: str
    name: str
    description: Optional[str] = None
    barCode: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    typeProduct: Literal['1', '2'] = '1'
    taxesOption: int = 0
    sku: Optional[str] = None
    priceSale: float = 0.0
    priceBase: float = 0.0
    state: Optional[bool] = True
    sellInNegative: Optional[bool] = False
    category: CategoryResponse
    brand: BrandResponse
    # Información específica por PDV
    stocksPdv: List[StockPerPDV] = Field(default_factory=list)
    totalStock: int = 0  # Stock total sumando todos los PDVs
    lowStockAlert: bool = False  # Si hay algún PDV con stock bajo

class TaxOut(BaseModel):
    id: UUID
    name: str
    code: str
    rate: float
    type: str

    class Config:
        from_attributes = True

class ProductTaxOut(BaseModel):
    id: UUID
    tax: TaxOut

    class Config:
        from_attributes = True

class ProductOut(BaseModel):
    """Schema de respuesta detallada (para compatibilidad)"""
    id: UUID
    name: str
    sku: str
    description: Optional[str]
    is_configurable: bool
    brand: Optional[BrandResponse]
    category: Optional[CategoryResponse]
    created_at: datetime
    pdvs: List[StockPerPDV]
    taxes: List[ProductTaxOut] = Field(default_factory=list, description="Impuestos asignados al producto")

    class Config:
        from_attributes = True

# Mantener schemas legacy para compatibilidad
class ProductVariantOut(BaseModel):
    """Schema para variantes de productos configurables"""
    id: UUID
    name: str
    sku: str
    product_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProductOutWithPdvs(BaseModel):
    """Schema de producto con información de PDVs"""
    id: UUID
    name: str
    sku: str
    description: Optional[str]
    is_configurable: bool
    brand: Optional[BrandResponse]
    category: Optional[CategoryResponse]
    pdvs: List[StockPerPDV] = Field(default_factory=list)
    
    class Config:
        from_attributes = True

class PaginatedProductResponse(PaginatedResponse):
    """Respuesta paginada para productos"""
    data: List[GetProductResponse]
    applied_filters: Optional[Dict[str, Any]] = None
    counts_by_status: List[Dict[str, Any]] = []

class PaginatedProductPDVResponse(PaginatedResponse):
    """Respuesta paginada para productos con información por PDV"""
    data: List[ProductPDVResponse]
    applied_filters: Optional[Dict[str, Any]] = None
    counts_by_status: List[Dict[str, Any]] = []

class ProductOutDefault(BaseModel):
    id: UUID
    name: str
    sku: str
    description: Optional[str]
    is_configurable: bool = False
    brand_id: Optional[UUID]
    category_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True

class ProductList(BaseModel):
    products: List[ProductOutDefault]

    class Config:
        from_attributes = True