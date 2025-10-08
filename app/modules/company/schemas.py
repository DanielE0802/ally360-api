from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
import re
from app.common.validators import validate_colombia_phone, validate_colombia_nit_base, format_colombia_phone, format_colombia_nit_base

class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: str
    nit: str = Field(..., description="NIT colombiano sin dígito de verificación (ej: 901886184)")
    economic_activity: Optional[str] = None
    quantity_employees: str = Field(default="1-10", description="Number of employees range, e.g., '1-10', '50-100', '500+'")
    social_reason: Optional[str] = None
    logo: Optional[str] = None
    uniquePDV: bool = Field(default=False, description="Create a main PDV automatically with company information")
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if not validate_colombia_phone(v):
            raise ValueError(
                'Número de teléfono inválido. Use formato colombiano: '
                '+573XXXXXXXXX (móvil) o +571XXXXXXX (fijo), también acepta sin +57'
            )
        return format_colombia_phone(v)
    
    @field_validator('nit')
    @classmethod
    def validate_nit(cls, v):
        if not validate_colombia_nit_base(v):
            raise ValueError(
                'NIT inválido. Debe ser un NIT colombiano válido sin dígito de verificación. '
                'Formato: XXXXXXXXX (8-10 dígitos, ej: 901886184)'
            )
        return format_colombia_nit_base(v)
    
    @field_validator('quantity_employees')
    @classmethod
    def validate_quantity_employees(cls, v):
        if not v:
            raise ValueError('Cantidad de empleados es requerida')
        
        # Patrones válidos: "1-10", "50-100", "500+", "1000+"
        patterns = [
            r'^\d+-\d+$',  # Rango: 1-10, 50-100
            r'^\d+\+$',    # Más de: 500+, 1000+
            r'^\d+$'       # Número específico: 5, 50
        ]
        
        if any(re.match(pattern, v.strip()) for pattern in patterns):
            return v.strip()
        
        raise ValueError('Formato inválido. Use: "1-10", "50-100", "500+" o un número específico')
    
    class Config:
        from_attributes = True

class CompanyOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: str
    nit: str = Field(..., description="NIT colombiano sin dígito de verificación")
    economic_activity: Optional[str] = None
    quantity_employees: str = Field(default="1-10", description="Number of employees range, e.g., '1-10', '50-100', '500+'")
    social_reason: Optional[str] = None
    logo: Optional[str] = None
    uniquePDV: bool = Field(default=False, description="Create a main PDV automatically with company information")

    class Config:
        from_attributes = True

class CompanyCreateResponse(BaseModel):
    """Response schema for company creation with PDV creation info"""
    id: UUID
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: str
    nit: str = Field(..., description="NIT colombiano sin dígito de verificación")
    economic_activity: Optional[str] = None
    quantity_employees: str
    social_reason: Optional[str] = None
    logo: Optional[str] = None
    uniquePDV: bool
    main_pdv_created: bool = Field(description="Indicates if a main PDV was created automatically")

    class Config:
        from_attributes = True

class CompanyUpdate(BaseModel):
    """Schema for updating company information. NIT cannot be updated."""
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    economic_activity: Optional[str] = None
    quantity_employees: Optional[str] = Field(None, description="Number of employees range, e.g., '1-10', '50-100', '500+'")
    social_reason: Optional[str] = None
    # NIT is excluded - cannot be updated
    # logo will be handled by separate image upload endpoint

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if v is None:
            return v
        if not validate_colombia_phone(v):
            raise ValueError(
                'Número de teléfono inválido. Use formato colombiano: '
                '+573XXXXXXXXX (móvil) o +571XXXXXXX (fijo), también acepta sin +57'
            )
        return format_colombia_phone(v)

    @field_validator('quantity_employees')
    @classmethod
    def validate_quantity_employees(cls, v):
        if v is None:
            return v
            
        # Patrones válidos: "1-10", "50-100", "500+", "1000+"
        patterns = [
            r'^\d+-\d+$',  # Rango: 1-10, 50-100
            r'^\d+\+$',    # Más de: 500+, 1000+
            r'^\d+$'       # Número específico: 5, 50
        ]
        
        if any(re.match(pattern, v.strip()) for pattern in patterns):
            return v.strip()
        
        raise ValueError('Formato inválido. Use: "1-10", "50-100", "500+" o un número específico')

class CompanyImageUploadResponse(BaseModel):
    message: str
    logo_url: str

class CompanyLogoResponse(BaseModel):
    logo_url: str
    expires_in: str
        
class AssignUserToCompany(BaseModel):
    user_id: UUID
    company_id: UUID
    role: str = "empleado"
    
    
class CompanyOutWithRole(CompanyOut):
    role: str


class CompanyMeDetail(BaseModel):
    """Schema completo para /company/me con toda la información relacionada"""
    id: UUID
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: str
    nit: str = Field(..., description="NIT colombiano sin dígito de verificación")
    economic_activity: Optional[str] = None
    quantity_employees: str = Field(default="1-10", description="Number of employees range")
    social_reason: Optional[str] = None
    logo: Optional[str] = None
    logo_url: Optional[str] = Field(None, description="Secure URL for logo access")
    is_active: bool
    created_at: datetime
    
    # User role in this company
    user_role: str = Field(..., description="Role of the current user in this company")
    
    # PDVs relacionados con ubicaciones
    pdvs: list['PDVWithLocation'] = Field(default=[], description="All PDVs with location details")
    
    class Config:
        from_attributes = True


class PDVWithLocation(BaseModel):
    """Schema para PDV con información de ubicación completa"""
    id: UUID = Field(..., description="Unique identifier of the PDV")
    name: str = Field(..., description="Name of the PDV")
    address: Optional[str] = Field(None, description="Address of the PDV")
    phone_number: Optional[str] = Field(None, description="Phone number of the PDV")
    is_main: bool = Field(default=False, description="If this is the main PDV")
    is_active: bool = Field(..., description="Indicates if the PDV is active")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Location information
    department_id: Optional[int] = Field(None, description="Department ID")
    city_id: Optional[int] = Field(None, description="City ID")
    department: Optional['DepartmentOut'] = Field(None, description="Department details")
    city: Optional['CityOut'] = Field(None, description="City details")

    class Config:
        from_attributes = True


class DepartmentOut(BaseModel):
    """Schema para departamentos"""
    id: int = Field(..., description="Department ID")
    name: str = Field(..., description="Department name")
    code: str = Field(..., description="Department DANE code")

    class Config:
        from_attributes = True


class CityOut(BaseModel):
    """Schema para ciudades"""
    id: int = Field(..., description="City ID")
    name: str = Field(..., description="City name")
    code: str = Field(..., description="City DANE code")
    department_id: int = Field(..., description="Department ID")

    class Config:
        from_attributes = True
    