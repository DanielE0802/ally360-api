"""
Módulo de Contactos - Ally360 ERP

Este módulo gestiona un sistema unificado de contactos que reemplaza
las entidades separadas de Customer y Supplier en el sistema.

Características principales:
- Sistema multi-tenant con aislamiento por company_id
- Validaciones fiscales específicas para Colombia (NIT, DV)
- Soft delete para mantener integridad referencial
- Tipos flexibles (cliente, proveedor, o ambos)
- Integración con módulos de Invoices y Bills
- Gestión de adjuntos de documentos
- Búsqueda avanzada y filtros

Componentes:
- models.py: SQLAlchemy models con validaciones colombianas
- schemas.py: Pydantic schemas para validación y serialización
- service.py: Lógica de negocio y operaciones CRUD
- router.py: Endpoints REST API
- dependencies.py: Dependencias específicas del módulo
- tests.py: Pruebas unitarias y de integración
"""

__version__ = "1.0.0"
__author__ = "Ally360 Development Team"

# Importar modelos principales para facilitar el acceso
from .models import Contact, ContactAttachment, ContactType, IdType, PersonType
from .schemas import (
    ContactCreate, ContactUpdate, ContactOut, ContactDetail,
    ContactForInvoice, ContactForBill, ContactList, ContactStats
)
from .service import ContactService, ContactAttachmentService

__all__ = [
    # Models
    "Contact",
    "ContactAttachment", 
    "ContactType",
    "IdType",
    "PersonType",
    
    # Schemas
    "ContactCreate",
    "ContactUpdate", 
    "ContactOut",
    "ContactDetail",
    "ContactForInvoice",
    "ContactForBill",
    "ContactList",
    "ContactStats",
    
    # Services
    "ContactService",
    "ContactAttachmentService"
]