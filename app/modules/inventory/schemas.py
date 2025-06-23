from pydantic import BaseModel, Field
from typing import Optional

class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, example="Sample Product")
    description: str = Field(min_length=1, max_length=500, example="This is a sample product description.")
    price: int = Field(gt=0, example=100)
    quantity: int = Field(gt=0, example=10)
    is_active: bool = Field(default=True, example=True)

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        example="Updated Product"
    )
    description: Optional[str] = Field(
        None,
        min_length=1,
        max_length=500,
        example="This is an updated product description."
    )
    price: Optional[int] = Field(
        None,
        gt=0,
        example=150
    )
    quantity: Optional[int] = Field(
        None,
        gt=0,
        example=20
    )
    is_active: Optional[bool] = Field(
        None,
        example=True
    )