"""
Models for Colombian departments and cities.
"""
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


class Department(Base):
    """
    Modelo para departamentos de Colombia.
    Datos estáticos que se cargan una vez.
    """
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(5), nullable=False, unique=True, index=True)  # Código DANE
    
    # Relación con ciudades
    cities = relationship("City", back_populates="department", cascade="all, delete-orphan")
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class City(Base):
    """
    Modelo para ciudades/municipios de Colombia.
    Datos estáticos que se cargan una vez.
    """
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(10), nullable=False, unique=True, index=True)  # Código DANE
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    
    # Relación con departamento
    department = relationship("Department", back_populates="cities")
    
    def __str__(self):
        return f"{self.name}, {self.department.name}"