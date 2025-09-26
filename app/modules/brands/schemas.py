from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from datetime import datetime

class BrandCreate(BaseModel):
    name: str
    description: Optional[str] = None

class BrandUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class BrandOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class BrandList(BaseModel):
    brands: list[BrandOut]

    class Config:
        from_attributes = True