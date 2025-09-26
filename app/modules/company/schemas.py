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
        
class AssignUserToCompany(BaseModel):
    user_id: UUID
    company_id: UUID
    role: str = "empleado"
    
    
class CompanyOutWithRole(CompanyOut):
    role: str
    