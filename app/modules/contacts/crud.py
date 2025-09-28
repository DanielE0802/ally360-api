"""
CRUD operations para el módulo de Contactos

Implementa operaciones de base de datos para:
- CRUD básico de contactos
- Búsquedas avanzadas con filtros
- Soft delete y restore
- Gestión de adjuntos
- Validaciones de integridad multi-tenant

Todas las operaciones están scoped por company_id para multi-tenancy.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.modules.contacts.models import Contact, ContactAttachment, ContactType


class ContactCrud:
    """Operaciones CRUD para contactos"""
    
    def __init__(self, db: Session):
        self.db = db

    def create(self, contact_data: dict, company_id: UUID, user_id: UUID) -> Contact:
        """Crear nuevo contacto"""
        contact = Contact(
            **contact_data,
            company_id=company_id,
            created_by=user_id,
            updated_by=user_id
        )
        
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def get_by_id(self, contact_id: UUID, company_id: UUID, include_deleted: bool = False) -> Optional[Contact]:
        """Obtener contacto por ID"""
        query = self.db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.company_id == company_id
        )
        
        if not include_deleted:
            query = query.filter(Contact.deleted_at.is_(None))
        
        return query.first()

    def get_by_document(self, id_number: str, company_id: UUID, exclude_id: Optional[UUID] = None) -> Optional[Contact]:
        """Obtener contacto por número de documento"""
        query = self.db.query(Contact).filter(
            Contact.company_id == company_id,
            Contact.id_number == id_number,
            Contact.deleted_at.is_(None)
        )
        
        if exclude_id:
            query = query.filter(Contact.id != exclude_id)
        
        return query.first()

    def get_many(
        self, 
        company_id: UUID,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        contact_type: Optional[ContactType] = None,
        is_active: Optional[bool] = None,
        seller_id: Optional[UUID] = None,
        include_deleted: bool = False
    ) -> tuple[List[Contact], int]:
        """Listar contactos con filtros"""
        query = self.db.query(Contact).filter(Contact.company_id == company_id)
        
        # Filtro de eliminados
        if not include_deleted:
            query = query.filter(Contact.deleted_at.is_(None))
        
        # Búsqueda de texto
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Contact.name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.id_number.ilike(search_term)
                )
            )
        
        # Filtro por tipo
        if contact_type:
            query = query.filter(Contact.type.contains([contact_type.value]))
        
        # Filtro por estado activo
        if is_active is not None:
            query = query.filter(Contact.is_active == is_active)
        
        # Filtro por vendedor
        if seller_id:
            query = query.filter(Contact.seller_id == seller_id)
        
        # Contar total
        total = query.count()
        
        # Aplicar paginación y ordenar
        contacts = query.order_by(Contact.name).offset(offset).limit(limit).all()
        
        return contacts, total

    def get_clients(self, company_id: UUID, search: Optional[str] = None, limit: int = 50) -> List[Contact]:
        """Obtener contactos que son clientes"""
        query = self.db.query(Contact).filter(
            Contact.company_id == company_id,
            Contact.type.contains([ContactType.CLIENT.value]),
            Contact.deleted_at.is_(None),
            Contact.is_active == True
        )
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Contact.name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.id_number.ilike(search_term)
                )
            )
        
        return query.order_by(Contact.name).limit(limit).all()

    def get_providers(self, company_id: UUID, search: Optional[str] = None, limit: int = 50) -> List[Contact]:
        """Obtener contactos que son proveedores"""
        query = self.db.query(Contact).filter(
            Contact.company_id == company_id,
            Contact.type.contains([ContactType.PROVIDER.value]),
            Contact.deleted_at.is_(None),
            Contact.is_active == True
        )
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Contact.name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.id_number.ilike(search_term)
                )
            )
        
        return query.order_by(Contact.name).limit(limit).all()

    def update(self, contact: Contact, update_data: dict, user_id: UUID) -> Contact:
        """Actualizar contacto"""
        for field, value in update_data.items():
            if hasattr(contact, field):
                setattr(contact, field, value)
        
        contact.updated_by = user_id
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def soft_delete(self, contact: Contact, user_id: UUID) -> Contact:
        """Soft delete de contacto"""
        contact.deleted_at = datetime.utcnow()
        contact.is_active = False
        contact.updated_by = user_id
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def restore(self, contact: Contact, user_id: UUID) -> Contact:
        """Restaurar contacto eliminado"""
        contact.deleted_at = None
        contact.is_active = True
        contact.updated_by = user_id
        
        self.db.commit()
        self.db.refresh(contact)
        
        return contact

    def get_stats(self, company_id: UUID) -> dict:
        """Obtener estadísticas de contactos"""
        base_query = self.db.query(Contact).filter(Contact.company_id == company_id)
        
        # Contactos activos (no eliminados)
        active_query = base_query.filter(Contact.deleted_at.is_(None))
        
        stats = {
            'total_contacts': active_query.count(),
            'active_contacts': active_query.filter(Contact.is_active == True).count(),
            'clients': active_query.filter(Contact.type.contains([ContactType.CLIENT.value])).count(),
            'providers': active_query.filter(Contact.type.contains([ContactType.PROVIDER.value])).count(),
            'mixed': active_query.filter(
                and_(
                    Contact.type.contains([ContactType.CLIENT.value]),
                    Contact.type.contains([ContactType.PROVIDER.value])
                )
            ).count(),
            'deleted_contacts': base_query.filter(Contact.deleted_at.is_not(None)).count()
        }
        
        return stats


class ContactAttachmentCrud:
    """Operaciones CRUD para adjuntos de contactos"""
    
    def __init__(self, db: Session):
        self.db = db

    def create(self, attachment_data: dict, company_id: UUID, user_id: UUID) -> ContactAttachment:
        """Crear adjunto"""
        attachment = ContactAttachment(
            **attachment_data,
            company_id=company_id,
            uploaded_by=user_id
        )
        
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        
        return attachment

    def get_by_id(self, attachment_id: UUID, company_id: UUID) -> Optional[ContactAttachment]:
        """Obtener adjunto por ID"""
        return self.db.query(ContactAttachment).filter(
            ContactAttachment.id == attachment_id,
            ContactAttachment.company_id == company_id
        ).first()

    def get_by_contact(self, contact_id: UUID, company_id: UUID) -> List[ContactAttachment]:
        """Obtener adjuntos de un contacto"""
        return self.db.query(ContactAttachment).filter(
            ContactAttachment.contact_id == contact_id,
            ContactAttachment.company_id == company_id
        ).order_by(ContactAttachment.created_at.desc()).all()

    def delete(self, attachment: ContactAttachment) -> None:
        """Eliminar adjunto"""
        self.db.delete(attachment)
        self.db.commit()