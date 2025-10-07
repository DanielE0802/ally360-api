"""
Pydantic schemas for locations (departments and cities).
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class CityBase(BaseModel):
    """Base schema para ciudades."""
    id: int
    name: str = Field(..., description="Nombre de la ciudad")
    code: str = Field(..., description="Código DANE de la ciudad")
    department_id: int = Field(..., description="ID del departamento")


class CityOut(CityBase):
    """Schema de salida para ciudades."""
    
    class Config:
        from_attributes = True


class CityWithDepartment(CityBase):
    """Schema de ciudad con información del departamento."""
    department_name: str = Field(..., description="Nombre del departamento")
    
    class Config:
        from_attributes = True


class DepartmentBase(BaseModel):
    """Base schema para departamentos."""
    id: int
    name: str = Field(..., description="Nombre del departamento")
    code: str = Field(..., description="Código DANE del departamento")


class DepartmentOut(DepartmentBase):
    """Schema de salida para departamentos."""
    
    class Config:
        from_attributes = True


class DepartmentWithCities(DepartmentBase):
    """Schema de departamento con sus ciudades."""
    cities: List[CityOut] = Field(default_factory=list, description="Ciudades del departamento")
    
    class Config:
        from_attributes = True


class LocationsResponse(BaseModel):
    """Schema de respuesta para endpoints de ubicaciones."""
    departments: List[DepartmentOut] = Field(default_factory=list)
    cities: List[CityOut] = Field(default_factory=list)
    total_departments: int = Field(..., description="Total de departamentos")
    total_cities: int = Field(..., description="Total de ciudades")


class DepartmentList(BaseModel):
    """Schema para lista de departamentos."""
    departments: List[DepartmentOut] = Field(..., description="Lista de departamentos")
    total: int = Field(..., description="Total de departamentos")


class CityList(BaseModel):
    """Schema para lista de ciudades."""
    cities: List[CityWithDepartment] = Field(..., description="Lista de ciudades")
    total: int = Field(..., description="Total de ciudades")
    department_id: Optional[int] = Field(None, description="ID del departamento filtrado")
    department_name: Optional[str] = Field(None, description="Nombre del departamento filtrado")