from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum

class MovementType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    ADJ = "ADJ"
    TRANSFER = "TRANSFER"

# Stock schemas
class StockOut(BaseModel):
    id: UUID
    product_id: UUID
    pdv_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    pdv_name: Optional[str] = None
    variant_color: Optional[str] = None
    variant_size: Optional[str] = None

    class Config:
        from_attributes = True

class StockUpdate(BaseModel):
    quantity: int = Field(..., description="New stock quantity")
    notes: Optional[str] = Field(None, max_length=255, description="Adjustment notes")

# Movement schemas
class InventoryMovementCreate(BaseModel):
    product_id: UUID
    pdv_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int = Field(..., description="Quantity (positive for IN, negative for OUT)")
    movement_type: MovementType
    reference: Optional[str] = Field(None, max_length=100, description="Order/invoice reference")
    notes: Optional[str] = Field(None, max_length=255, description="Movement notes")

class InventoryMovementOut(BaseModel):
    id: UUID
    product_id: UUID
    pdv_id: UUID
    variant_id: Optional[UUID]
    quantity: int
    movement_type: str
    reference: Optional[str]
    notes: Optional[str]
    created_by: UUID
    created_at: datetime
    tenant_id: UUID
    
    # Joined data
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    pdv_name: Optional[str] = None
    created_by_email: Optional[str] = None

    class Config:
        from_attributes = True

class TransferMovementCreate(BaseModel):
    product_id: UUID
    variant_id: Optional[UUID] = None
    from_pdv_id: UUID
    to_pdv_id: UUID
    quantity: int = Field(..., gt=0, description="Quantity to transfer")
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=255)

# Stock summary schemas
class ProductStockSummary(BaseModel):
    product_id: UUID
    product_name: str
    product_sku: str
    total_quantity: int
    pdv_stocks: List[StockOut]

    class Config:
        from_attributes = True