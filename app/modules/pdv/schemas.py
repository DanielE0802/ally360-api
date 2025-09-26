
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

class PDVcreate(BaseModel):
    name: str = Field(..., description="Name of the PDV")
    address: str = Field(..., description="Address of the PDV")
    phone_number: Optional[str] = Field(default=None, description="Phone number of the PDV")
    is_active: bool = Field(default=True, description="Indicates if the PDV is active")

    class Config:
        orm_mode = True

class PDVOutput(PDVcreate):
    id: UUID = Field(..., description="Unique identifier of the PDV")

class PDVUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the PDV")
    address: Optional[str] = Field(None, description="Address of the PDV")
    phone_number: Optional[str] = Field(None, description="Phone number of the PDV")
    is_active: Optional[bool] = Field(None, description="Indicates if the PDV is active")
    
    class Config:
        orm_mode = True

class PDVList(BaseModel):
    pdvs: list[PDVOutput] = Field(..., description="List of PDVs")

    class Config:
        orm_mode = True