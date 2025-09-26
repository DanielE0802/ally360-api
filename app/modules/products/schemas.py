from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from datetime import datetime
from typing import List

class ProductCreate(BaseModel):
    name: str
    sku: str
    description: Optional[str] = None
    is_configurable: bool = False
    brand_id: Optional[UUID]
    category_id: Optional[UUID]

class ProductUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    is_configurable: Optional[bool]
    brand_id: Optional[UUID]
    category_id: Optional[UUID]
    
class ProductOutDefault(ProductCreate):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class ProductOutWithPdvs(ProductOutDefault):
    pdvs: list[UUID] = Field(default_factory=list, description="List of PDV IDs where the product is available")
    
    class Config:
        from_attributes = True

class ProductList(BaseModel):
    products: list[ProductOutDefault]

    class Config:
        from_attributes = True

class VariantCreate(BaseModel):
    color: Optional[str]
    size: Optional[str]
    sku: str
    price: float

class StockCreate(BaseModel):
    pdv_id: UUID
    quantity: int

class VariantWithStockCreate(VariantCreate):
    stocks: list[StockCreate]

class ConfigurableProductCreate(ProductCreate):
    variants: list[VariantWithStockCreate]

class SimpleProductWithStockCreate(ProductCreate):
    sku: str
    price: float
    stocks: list[StockCreate]
    
class ProductVariantOut(ProductOutDefault):
    variants: list[VariantCreate]

class PDVOut(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None

    class Config:
        from_attributes = True

class StockOut(BaseModel):
    id: UUID
    quantity: int
    pdv: PDVOut

    class Config:
        from_attributes = True
        

class BrandOut(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True

class CategoryOut(BaseModel):
    id: UUID
    name: str

    class Config:
        from_attributes = True

class StockPerPDV(BaseModel):
    pdv_id: UUID
    pdv_name: str
    quantity: int

class ProductOut(BaseModel):
    id: UUID
    name: str
    sku: str
    description: Optional[str]
    is_configurable: bool
    brand: Optional[BrandOut]
    category: Optional[CategoryOut]
    created_at: datetime
    pdvs: List[StockPerPDV]

    class Config:
        from_attributes = True