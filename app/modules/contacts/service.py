"""
Servicios de negocio para el módulo de Contactos

Implementa toda la lógica de negocio para:
- CRUD completo de contactos con validaciones fiscales
- Soft delete y restore para auditabilidad
- Búsqueda avanzada por múltiples criterios
- Gestión de adjuntos de documentos
- Integración con módulos Invoices y Bills
- Validaciones específicas para Colombia (NIT, DV, responsabilidades fiscales)

Este módulo reemplaza las entidades Customer e Supplier de otros módulos.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, func, desc
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from app.modules.contacts.models import Contact, ContactAttachment, ContactType
from app.modules.contacts.schemas import (
    ContactCreate, ContactUpdate, ContactList, ContactDetail, ContactSearchFilters,
    ContactAttachmentCreate, ContactRestore, ContactStats,
    ContactForInvoice, ContactForBill
)


class ContactService:
    """Servicio principal para gestión de contactos"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_contact(self, contact_data: ContactCreate, tenant_id: UUID, user_id: UUID) -> Contact:
        """Crear un nuevo contacto"""
        try:
            # Verificar unicidad de documento si se proporciona
            if contact_data.id_number:
                existing = self.db.query(Contact).filter(
                    Contact.tenant_id == tenant_id,
                    Contact.id_number == contact_data.id_number,
                    Contact.deleted_at.is_(None)  # No contar los eliminados
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe un contacto con el documento {contact_data.id_number}"
                    )

            # Verificar que el vendedor pertenece a la empresa si se asigna
            if contact_data.seller_id:
                from app.modules.auth.models import User
                seller = self.db.query(User).filter(User.id == contact_data.seller_id).first()
                if not seller:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Vendedor no encontrado"
                    )

            # Convertir direcciones a dict si son objetos Pydantic
            billing_address = contact_data.billing_address.dict() if contact_data.billing_address else None
            shipping_address = contact_data.shipping_address.dict() if contact_data.shipping_address else None

            # Normalizar lista de tipos a strings
            type_values = []
            if contact_data.type:
                for t in contact_data.type:
                    try:
                        type_values.append(t.value)  # Pydantic Enum
                    except AttributeError:
                        type_values.append(str(t))

            contact = Contact(
                name=contact_data.name,
                type=type_values,
                email=contact_data.email,
                phone_primary=contact_data.phone_primary,
                phone_secondary=contact_data.phone_secondary,
                mobile=contact_data.mobile,
                id_type=contact_data.id_type.value if contact_data.id_type else None,
                id_number=contact_data.id_number,
                dv=contact_data.dv,
                person_type=contact_data.person_type.value if contact_data.person_type else None,
                fiscal_responsibilities=contact_data.fiscal_responsibilities,
                payment_terms_days=contact_data.payment_terms_days,
                credit_limit=contact_data.credit_limit,
                seller_id=contact_data.seller_id,
                price_list_id=contact_data.price_list_id,
                billing_address=billing_address,
                shipping_address=shipping_address,
                notes=contact_data.notes,
                tenant_id=tenant_id,
                created_by=user_id,
                updated_by=user_id
            )
            
            self.db.add(contact)
            self.db.commit()
            self.db.refresh(contact)
            
            return contact
            
        except HTTPException:
            raise
        except IntegrityError as e:
            self.db.rollback()
            if "uq_contact_company_id_number" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un contacto con este documento en la empresa"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error de integridad: {str(e)}"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando contacto: {str(e)}"
            )

    def get_contacts(
        self, 
        tenant_id: UUID, 
        limit: int = 100, 
        offset: int = 0,
        filters: Optional[ContactSearchFilters] = None
    ) -> ContactList:
        """Listar contactos con filtros avanzados"""
        try:
            query = self.db.query(Contact).filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None)  # Solo contactos no eliminados
            )
            
            # Aplicar filtros
            if filters:
                if filters.search:
                    search_term = f"%{filters.search}%"
                    query = query.filter(
                        or_(
                            Contact.name.ilike(search_term),
                            Contact.email.ilike(search_term),
                            Contact.id_number.ilike(search_term)
                        )
                    )
                
                if filters.type:
                    # Buscar contactos que contengan el tipo especificado
                    query = query.filter(Contact.type.contains([filters.type.value]))
                
                if filters.is_active is not None:
                    query = query.filter(Contact.is_active == filters.is_active)
                
                if filters.seller_id:
                    query = query.filter(Contact.seller_id == filters.seller_id)
            
            # Contar total
            total = query.count()
            
            # Aplicar paginación y ordenar
            contacts = query.order_by(Contact.name).offset(offset).limit(limit).all()
            
            return ContactList(
                items=contacts,
                total=total,
                limit=limit,
                offset=offset
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando contactos: {str(e)}"
            )

    def get_contact_by_id(self, contact_id: UUID, tenant_id: UUID, include_deleted: bool = False) -> Contact:
        """Obtener contacto por ID"""
        query = self.db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.tenant_id == tenant_id
        )
        
        if not include_deleted:
            query = query.filter(Contact.deleted_at.is_(None))
        
        contact = query.first()
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contacto no encontrado"
            )
        
        return contact

    def update_contact(
        self, 
        contact_id: UUID, 
        contact_update: ContactUpdate, 
        tenant_id: UUID,
        user_id: UUID
    ) -> Contact:
        """Actualizar contacto"""
        try:
            contact = self.get_contact_by_id(contact_id, tenant_id)
            
            # Verificar unicidad de documento si se actualiza
            if contact_update.id_number and contact_update.id_number != contact.id_number:
                existing = self.db.query(Contact).filter(
                    Contact.tenant_id == tenant_id,
                    Contact.id_number == contact_update.id_number,
                    Contact.id != contact_id,
                    Contact.deleted_at.is_(None)
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe otro contacto con el documento {contact_update.id_number}"
                    )
            
            # Actualizar campos
            update_data = contact_update.dict(exclude_unset=True, exclude_none=True)
            
            for field, value in update_data.items():
                if field == 'type' and value:
                    # Normalizar a lista de strings
                    normalized = []
                    for t in value:
                        try:
                            normalized.append(t.value)
                        except AttributeError:
                            normalized.append(str(t))
                    setattr(contact, field, normalized)
                elif field == 'id_type' and value:
                    setattr(contact, field, value.value)
                elif field == 'person_type' and value:
                    setattr(contact, field, value.value)
                elif field in ['billing_address', 'shipping_address'] and value:
                    # Convertir a dict si es objeto Pydantic
                    setattr(contact, field, value.dict() if hasattr(value, 'dict') else value)
                elif field not in ['billing_address', 'shipping_address'] or value is not None:
                    setattr(contact, field, value)
            
            contact.updated_by = user_id
            
            self.db.commit()
            self.db.refresh(contact)
            
            return contact
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error actualizando contacto: {str(e)}"
            )

    def delete_contact(self, contact_id: UUID, tenant_id: UUID, user_id: UUID) -> Dict[str, str]:
        """Soft delete de contacto"""
        try:
            contact = self.get_contact_by_id(contact_id, tenant_id)
            
            if contact.deleted_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El contacto ya está eliminado"
                )
            
            # TODO: Verificar si tiene facturas o compras asociadas (opcional)
            # En el MVP permitimos eliminar aunque tenga documentos asociados
            
            # Soft delete
            contact.deleted_at = datetime.utcnow()
            contact.is_active = False
            contact.updated_by = user_id
            
            self.db.commit()
            
            return {"message": "Contacto eliminado exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error eliminando contacto: {str(e)}"
            )

    def restore_contact(
        self, 
        contact_id: UUID, 
        tenant_id: UUID, 
        user_id: UUID,
        restore_data: Optional[ContactRestore] = None
    ) -> Contact:
        """Restaurar contacto eliminado"""
        try:
            contact = self.get_contact_by_id(contact_id, tenant_id, include_deleted=True)
            
            if not contact.deleted_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El contacto no está eliminado"
                )
            
            # Verificar unicidad de documento antes de restaurar
            if contact.id_number:
                existing = self.db.query(Contact).filter(
                    Contact.tenant_id == tenant_id,
                    Contact.id_number == contact.id_number,
                    Contact.id != contact_id,
                    Contact.deleted_at.is_(None)
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"No se puede restaurar: existe otro contacto activo con el documento {contact.id_number}"
                    )
            
            # Restaurar
            contact.deleted_at = None
            contact.is_active = True
            contact.updated_by = user_id
            
            # Agregar nota de restauración si se proporciona
            if restore_data and restore_data.reason:
                existing_notes = contact.notes or ""
                restore_note = f"\n[RESTAURADO {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}]: {restore_data.reason}"
                contact.notes = existing_notes + restore_note
            
            self.db.commit()
            self.db.refresh(contact)
            
            return contact
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error restaurando contacto: {str(e)}"
            )

    def get_contact_stats(self, tenant_id: UUID) -> ContactStats:
        """Obtener estadísticas de contactos"""
        try:
            # Contactos activos (no eliminados)
            active_query = self.db.query(Contact).filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None)
            )
            
            total_contacts = active_query.count()
            active_contacts = active_query.filter(Contact.is_active == True).count()
            
            # Contar por tipo
            clients = active_query.filter(Contact.type.contains([ContactType.CLIENT.value])).count()
            providers = active_query.filter(Contact.type.contains([ContactType.PROVIDER.value])).count()
            
            # Contactos mixtos (cliente y proveedor)
            mixed = active_query.filter(
                and_(
                    Contact.type.contains([ContactType.CLIENT.value]),
                    Contact.type.contains([ContactType.PROVIDER.value])
                )
            ).count()
            
            # Contactos eliminados
            deleted_contacts = self.db.query(Contact).filter(
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_not(None)
            ).count()
            
            return ContactStats(
                total_contacts=total_contacts,
                active_contacts=active_contacts,
                clients=clients,
                providers=providers,
                mixed=mixed,
                deleted_contacts=deleted_contacts
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error obteniendo estadísticas: {str(e)}"
            )

    # ===== MÉTODOS DE INTEGRACIÓN =====

    def get_clients_for_invoices(self, tenant_id: UUID, search: Optional[str] = None) -> List[ContactForInvoice]:
        """Obtener contactos que son clientes para usar en facturas"""
        try:
            query = self.db.query(Contact).filter(
                Contact.tenant_id == tenant_id,
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
            
            contacts = query.order_by(Contact.name).limit(50).all()
            
            return [ContactForInvoice.from_orm(contact) for contact in contacts]
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error obteniendo clientes: {str(e)}"
            )

    def get_providers_for_bills(self, tenant_id: UUID, search: Optional[str] = None) -> List[ContactForBill]:
        """Obtener contactos que son proveedores para usar en compras"""
        try:
            query = self.db.query(Contact).filter(
                Contact.tenant_id == tenant_id,
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
            
            contacts = query.order_by(Contact.name).limit(50).all()
            
            return [ContactForBill.from_orm(contact) for contact in contacts]
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error obteniendo proveedores: {str(e)}"
            )


class ContactAttachmentService:
    """Servicio para gestión de adjuntos de contactos"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_attachment(
        self, 
        contact_id: UUID, 
        attachment_data: ContactAttachmentCreate,
        tenant_id: UUID,
        user_id: UUID
    ) -> ContactAttachment:
        """Crear adjunto para contacto"""
        try:
            # Verificar que el contacto existe y pertenece a la empresa
            contact_service = ContactService(self.db)
            contact = contact_service.get_contact_by_id(contact_id, tenant_id)
            
            attachment = ContactAttachment(
                contact_id=contact_id,
                file_url=attachment_data.file_url,
                file_name=attachment_data.file_name,
                file_size=attachment_data.file_size,
                content_type=attachment_data.content_type,
                description=attachment_data.description,
                tenant_id=tenant_id,
                uploaded_by=user_id
            )
            
            self.db.add(attachment)
            self.db.commit()
            self.db.refresh(attachment)
            
            return attachment
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando adjunto: {str(e)}"
            )

    def delete_attachment(self, attachment_id: UUID, tenant_id: UUID) -> Dict[str, str]:
        """Eliminar adjunto"""
        try:
            attachment = self.db.query(ContactAttachment).filter(
                ContactAttachment.id == attachment_id,
                ContactAttachment.tenant_id == tenant_id
            ).first()
            
            if not attachment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Adjunto no encontrado"
                )
            
            # TODO: Eliminar archivo físico de MinIO
            
            self.db.delete(attachment)
            self.db.commit()
            
            return {"message": "Adjunto eliminado exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error eliminando adjunto: {str(e)}"
            )