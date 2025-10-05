from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID

class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: str
    nit: str
    economic_activity: Optional[str] = None
    quantity_employees: int = Field(default=1, ge=0, description="Number of employees, must be a non-negative integer")
    social_reason: Optional[str] = None
    logo: Optional[str] = None
    
    class Config:
        from_attributes = True

class CompanyOut(CompanyCreate):
    id: UUID

    class Config:
        from_attributes = True

class CompanyUpdate(BaseModel):
    """Schema for updating company information. NIT cannot be updated."""
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    economic_activity: Optional[str] = None
    quantity_employees: Optional[int] = Field(None, ge=0, description="Number of employees, must be a non-negative integer")
    social_reason: Optional[str] = None
    # NIT is excluded - cannot be updated
    # logo will be handled by separate image upload endpoint

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
    