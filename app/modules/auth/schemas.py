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
