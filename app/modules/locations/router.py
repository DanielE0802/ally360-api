"""
API routes for Colombian locations (departments and cities).
Este módulo es público y no requiere tenant_id.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from . import schemas
from .crud import LocationsCRUD

# Router público para ubicaciones
router = APIRouter(prefix="/locations", tags=["Locations"])

@router.get(
    "/departments",
    response_model=schemas.DepartmentList,
    summary="Get all departments",
    description="""
    Obtener todos los departamentos de Colombia.
    
    Endpoint público que no requiere autenticación ni tenant.
    Útil para formularios de registro y configuración inicial.
    """
)
async def get_departments(db: Session = Depends(get_db)):
    """Obtener todos los departamentos de Colombia."""
    departments = LocationsCRUD.get_all_departments(db)
    
    return schemas.DepartmentList(
        departments=[schemas.DepartmentOut.from_orm(dept) for dept in departments],
        total=len(departments)
    )


@router.get(
    "/departments/{department_id}",
    response_model=schemas.DepartmentWithCities,
    summary="Get department with cities",
    description="""
    Obtener un departamento específico con todas sus ciudades.
    
    Endpoint público que no requiere autenticación.
    """
)
async def get_department_with_cities(
    department_id: int,
    db: Session = Depends(get_db)
):
    """Obtener un departamento con todas sus ciudades."""
    department = LocationsCRUD.get_department_with_cities(db, department_id)
    
    if not department:
        raise HTTPException(
            status_code=404,
            detail=f"Department with ID {department_id} not found"
        )
    
    return schemas.DepartmentWithCities.from_orm(department)


@router.get(
    "/cities",
    response_model=schemas.CityList,
    summary="Get cities",
    description="""
    Obtener ciudades de Colombia, opcionalmente filtradas por departamento.
    
    Endpoint público que no requiere autenticación.
    Soporta filtro por departamento y búsqueda por nombre.
    """
)
async def get_cities(
    department_id: Optional[int] = Query(None, description="Filtrar por departamento"),
    search: Optional[str] = Query(None, description="Buscar por nombre de ciudad"),
    limit: int = Query(100, ge=1, le=500, description="Límite de resultados"),
    db: Session = Depends(get_db)
):
    """Obtener ciudades, opcionalmente filtradas."""
    
    if search:
        cities = LocationsCRUD.search_cities(db, search, department_id, limit)
    else:
        cities = LocationsCRUD.get_all_cities(db, department_id)
        cities = cities[:limit]  # Aplicar límite
    
    # Obtener información del departamento si se filtró
    department_name = None
    if department_id:
        department = LocationsCRUD.get_department_by_id(db, department_id)
        if department:
            department_name = department.name
    
    # Convertir a schema con información del departamento
    cities_with_dept = []
    for city in cities:
        city_data = {
            "id": city.id,
            "name": city.name,
            "code": city.code,
            "department_id": city.department_id,
            "department_name": city.department.name
        }
        cities_with_dept.append(schemas.CityWithDepartment(**city_data))
    
    return schemas.CityList(
        cities=cities_with_dept,
        total=len(cities_with_dept),
        department_id=department_id,
        department_name=department_name
    )


@router.get(
    "/cities/{city_id}",
    response_model=schemas.CityWithDepartment,
    summary="Get city by ID",
    description="""
    Obtener una ciudad específica por ID con información del departamento.
    
    Endpoint público que no requiere autenticación.
    """
)
async def get_city(
    city_id: int,
    db: Session = Depends(get_db)
):
    """Obtener una ciudad específica por ID."""
    city = LocationsCRUD.get_city_by_id(db, city_id)
    
    if not city:
        raise HTTPException(
            status_code=404,
            detail=f"City with ID {city_id} not found"
        )
    
    return schemas.CityWithDepartment(
        id=city.id,
        name=city.name,
        code=city.code,
        department_id=city.department_id,
        department_name=city.department.name
    )


@router.get(
    "/summary",
    response_model=schemas.LocationsResponse,
    summary="Get locations summary",
    description="""
    Obtener resumen de ubicaciones disponibles.
    
    Endpoint público útil para verificar que los datos estén cargados.
    """
)
async def get_locations_summary(db: Session = Depends(get_db)):
    """Obtener resumen de ubicaciones."""
    summary = LocationsCRUD.get_locations_summary(db)
    
    return schemas.LocationsResponse(
        departments=[],
        cities=[],
        total_departments=summary["total_departments"],
        total_cities=summary["total_cities"]
    )