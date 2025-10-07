"""
CRUD operations for locations (departments and cities).
"""
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from .models import Department, City


class LocationsCRUD:
    """CRUD operations for Colombian locations."""
    
    @staticmethod
    def get_all_departments(db: Session) -> List[Department]:
        """Obtener todos los departamentos ordenados por nombre."""
        return db.query(Department).order_by(Department.name).all()
    
    @staticmethod
    def get_department_by_id(db: Session, department_id: int) -> Optional[Department]:
        """Obtener un departamento por ID."""
        return db.query(Department).filter(Department.id == department_id).first()
    
    @staticmethod
    def get_department_with_cities(db: Session, department_id: int) -> Optional[Department]:
        """Obtener un departamento con todas sus ciudades."""
        return (
            db.query(Department)
            .options(joinedload(Department.cities))
            .filter(Department.id == department_id)
            .first()
        )
    
    @staticmethod
    def get_all_cities(db: Session, department_id: Optional[int] = None) -> List[City]:
        """
        Obtener todas las ciudades, opcionalmente filtradas por departamento.
        Incluye información del departamento.
        """
        query = db.query(City).options(joinedload(City.department))
        
        if department_id:
            query = query.filter(City.department_id == department_id)
        
        return query.order_by(City.name).all()
    
    @staticmethod
    def get_city_by_id(db: Session, city_id: int) -> Optional[City]:
        """Obtener una ciudad por ID con información del departamento."""
        return (
            db.query(City)
            .options(joinedload(City.department))
            .filter(City.id == city_id)
            .first()
        )
    
    @staticmethod
    def search_cities(
        db: Session, 
        search: str, 
        department_id: Optional[int] = None,
        limit: int = 50
    ) -> List[City]:
        """Buscar ciudades por nombre."""
        query = (
            db.query(City)
            .options(joinedload(City.department))
            .filter(City.name.ilike(f"%{search}%"))
        )
        
        if department_id:
            query = query.filter(City.department_id == department_id)
        
        return query.order_by(City.name).limit(limit).all()
    
    @staticmethod
    def get_locations_summary(db: Session) -> dict:
        """Obtener resumen de ubicaciones."""
        total_departments = db.query(func.count(Department.id)).scalar()
        total_cities = db.query(func.count(City.id)).scalar()
        
        return {
            "total_departments": total_departments,
            "total_cities": total_cities
        }