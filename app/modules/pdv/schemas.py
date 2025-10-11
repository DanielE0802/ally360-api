
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.common.validators import validate_colombia_phone, format_colombia_phone

# Location schemas for responses
class DepartmentOut(BaseModel):
    id: int = Field(..., description="Department ID")
    name: str = Field(..., description="Department name")
    code: str = Field(..., description="Department DANE code")

    class Config:
        from_attributes = True

class CityOut(BaseModel):
    id: int = Field(..., description="City ID")
    name: str = Field(..., description="City name")
    code: str = Field(..., description="City DANE code")
    department_id: int = Field(..., description="Department ID")
    department: Optional[DepartmentOut] = Field(None, description="Department details")

    class Config:
        from_attributes = True

class PDVcreate(BaseModel):
    name: str = Field(..., description="Name of the PDV")
    address: str = Field(..., description="Address of the PDV")
    phone_number: Optional[str] = Field(default=None, description="Phone number of the PDV")
    is_main: bool = Field(default=False, description="If this is the main PDV")
    department_id: Optional[int] = Field(None, description="Department ID")
    city_id: Optional[int] = Field(None, description="City ID")
    is_active: bool = Field(default=True, description="Indicates if the PDV is active")

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if v is None or v.strip() == "":
            return None
        if not validate_colombia_phone(v):
            raise ValueError(
                'Teléfono inválido. Use formato colombiano: '
                '+573XXXXXXXXX (móvil) o +576XXXXXXX/+575XXXXXXX/+574XXXXXXX/+572XXXXXXX/+571XXXXXXX (fijo)'
            )
        return format_colombia_phone(v)

    class Config:
        from_attributes = True

class PDVOutput(BaseModel):
    id: UUID = Field(..., description="Unique identifier of the PDV")
    name: str = Field(..., description="Name of the PDV")
    address: Optional[str] = Field(None, description="Address of the PDV")
    phone_number: Optional[str] = Field(None, description="Phone number of the PDV")
    is_main: bool = Field(default=False, description="If this is the main PDV")
    department_id: Optional[int] = Field(None, description="Department ID")
    city_id: Optional[int] = Field(None, description="City ID")
    is_active: bool = Field(..., description="Indicates if the PDV is active")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Related data
    department: Optional[DepartmentOut] = Field(None, description="Department details")
    city: Optional[CityOut] = Field(None, description="City details")

    class Config:
        from_attributes = True

class PDVUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the PDV")
    address: Optional[str] = Field(None, description="Address of the PDV")
    phone_number: Optional[str] = Field(None, description="Phone number of the PDV")
    is_main: Optional[bool] = Field(None, description="If this is the main PDV")
    department_id: Optional[int] = Field(None, description="Department ID")
    city_id: Optional[int] = Field(None, description="City ID")
    is_active: Optional[bool] = Field(None, description="Indicates if the PDV is active")

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if v is None or v.strip() == "":
            return None
        if not validate_colombia_phone(v):
            raise ValueError(
                'Teléfono inválido. Use formato colombiano: '
                '+573XXXXXXXXX (móvil) o +576XXXXXXX/+575XXXXXXX/+574XXXXXXX/+572XXXXXXX/+571XXXXXXX (fijo)'
            )
        return format_colombia_phone(v)
    
    class Config:
        from_attributes = True

class PDVList(BaseModel):
    pdvs: list[PDVOutput] = Field(..., description="List of PDVs")
    total: int = Field(..., description="Total number of PDVs")
    limit: int = Field(..., description="Number of PDVs per page")
    offset: int = Field(..., description="Number of PDVs skipped")

    class Config:
        from_attributes = True