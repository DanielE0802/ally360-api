from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID

class ProfileCreate(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    dni: str
    role: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    profile: ProfileCreate
    
class ProfileOut(ProfileCreate):
    id: UUID
    
    class Config:
        orm_mode = True


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    is_active: bool
    profile: ProfileOut

    class Config:
        orm_mode = True
        
class TokenResponse(BaseModel):
    access_token: str
    token_type: str


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
        orm_mode = True

class CompanyOut(CompanyCreate):
    id: UUID

    class Config:
        orm_mode = True
        
class AssignUserToCompany(BaseModel):
    user_id: UUID
    company_id: UUID
    role: str = "empleado"
    
    
class CompanyOutWithRole(CompanyOut):
    role: str
    