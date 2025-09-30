from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from enum import Enum
from datetime import datetime


class TaxType(str, Enum):
    VAT = "VAT"  # IVA
    INC = "INC"  # INC (Impuesto Nacional al Consumo)
    WITHHOLDING = "WITHHOLDING"  # Retención
    MUNICIPAL = "MUNICIPAL"  # Impuestos municipales (ReteICA, etc.)
    OTHER = "OTHER"  # Otros


class TaxBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nombre del impuesto (ej. 'IVA 19%')")
    code: str = Field(..., min_length=1, max_length=10, description="Código DIAN (ej. '01' para IVA)")
    rate: Decimal = Field(..., ge=0, le=1, description="Tasa del impuesto (ej. 0.19 para 19%)")
    type: TaxType = Field(..., description="Tipo de impuesto")
    
    @field_validator('rate')
    @classmethod
    def validate_rate(cls, v):
        if v < 0 or v > 1:
            raise ValueError('La tasa debe estar entre 0 y 1')
        return v


class TaxCreate(TaxBase):
    """Esquema para crear un impuesto local de empresa"""
    pass


class TaxUpdate(BaseModel):
    """Esquema para actualizar un impuesto (solo locales)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=10)
    rate: Optional[Decimal] = Field(None, ge=0, le=1)
    type: Optional[TaxType] = None
    
    @field_validator('rate')
    @classmethod
    def validate_rate(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError('La tasa debe estar entre 0 y 1')
        return v


class TaxOut(TaxBase):
    """Esquema para devolver información de un impuesto"""
    id: UUID
    is_editable: bool
    company_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaxList(BaseModel):
    """Esquema para listar impuestos con paginación"""
    taxes: List[TaxOut]
    total: int
    limit: int
    offset: int


class ProductTaxCreate(BaseModel):
    """Esquema para asignar impuestos a un producto"""
    tax_id: UUID


class ProductTaxOut(BaseModel):
    """Esquema para devolver impuestos de un producto"""
    id: UUID
    tax_id: UUID
    tax: TaxOut

    class Config:
        from_attributes = True


class TaxCalculation(BaseModel):
    """Esquema para el cálculo de impuestos"""
    tax_id: UUID
    tax_name: str
    tax_rate: Decimal
    base_amount: Decimal
    tax_amount: Decimal


class InvoiceTaxCreate(BaseModel):
    """Esquema para crear impuestos en factura (futuro)"""
    product_id: UUID
    tax_id: UUID
    base_amount: Decimal = Field(..., ge=0, description="Base gravable")
    tax_amount: Decimal = Field(..., ge=0, description="Valor del impuesto")


class InvoiceTaxOut(BaseModel):
    """Esquema para devolver impuestos de factura"""
    id: UUID
    invoice_id: UUID
    product_id: UUID
    tax_id: UUID
    base_amount: Decimal
    tax_amount: Decimal
    tax: TaxOut

    class Config:
        from_attributes = True