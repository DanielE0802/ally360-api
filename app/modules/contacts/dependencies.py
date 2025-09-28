"""
Dependencias específicas para el módulo de Contactos

Implementa validaciones y dependencias reutilizables:
- Validación de existencia de contactos
- Verificación de permisos por tipo de contacto
- Validaciones de integridad para eliminación
- Dependencias especializadas para integración con otros módulos

Todas las dependencias incluyen validación multi-tenant automática.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from app.dependencies.dbDependecies import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.dependencies.companyDependencies import get_company_from_header
from app.modules.company.models import Company

from app.modules.contacts.models import Contact, ContactType
from app.modules.contacts.service import ContactService


async def get_contact_by_id(
    contact_id: UUID,
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_header)
) -> Contact:
    """
    Dependency para obtener contacto por ID con validación multi-tenant
    
    Raises:
        HTTPException: Si el contacto no existe o no pertenece a la empresa
    """
    contact_service = ContactService(db)
    return contact_service.get_contact_by_id(contact_id, company.id)


async def get_active_contact_by_id(
    contact_id: UUID,
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_header)
) -> Contact:
    """
    Dependency para obtener contacto activo por ID
    
    Raises:
        HTTPException: Si el contacto no existe, no pertenece a la empresa o está inactivo
    """
    contact = await get_contact_by_id(contact_id, db, company)
    
    if not contact.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contacto está inactivo"
        )
    
    return contact


async def get_client_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_header)
) -> Contact:
    """
    Dependency para obtener contacto que sea cliente
    
    Útil para validar en endpoints de facturas.
    
    Raises:
        HTTPException: Si el contacto no es cliente
    """
    contact = await get_active_contact_by_id(contact_id, db, company)
    
    if ContactType.CLIENT.value not in contact.type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contacto no es un cliente válido"
        )
    
    return contact


async def get_provider_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_header)
) -> Contact:
    """
    Dependency para obtener contacto que sea proveedor
    
    Útil para validar en endpoints de compras.
    
    Raises:
        HTTPException: Si el contacto no es proveedor
    """
    contact = await get_active_contact_by_id(contact_id, db, company)
    
    if ContactType.PROVIDER.value not in contact.type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contacto no es un proveedor válido"
        )
    
    return contact


async def validate_contact_for_deletion(
    contact: Contact = Depends(get_contact_by_id),
    db: Session = Depends(get_db)
) -> Contact:
    """
    Dependency para validar si un contacto puede ser eliminado
    
    Verifica si tiene documentos asociados que impidan la eliminación.
    En el MVP permitimos eliminar contactos con documentos asociados.
    
    Args:
        contact: Contacto a validar
        db: Sesión de base de datos
    
    Returns:
        Contact: El contacto si puede ser eliminado
    
    Raises:
        HTTPException: Si el contacto ya está eliminado
    """
    if contact.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contacto ya está eliminado"
        )
    
    # TODO: En versiones futuras, agregar validaciones más estrictas:
    # - Verificar facturas pendientes
    # - Verificar compras pendientes  
    # - Verificar pagos pendientes
    # Por ahora en el MVP permitimos eliminar siempre
    
    return contact


async def validate_contact_for_restore(
    contact: Contact = Depends(get_contact_by_id),
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_header)
) -> Contact:
    """
    Dependency para validar si un contacto puede ser restaurado
    
    Verifica que esté eliminado y que no haya conflictos de documentos.
    
    Args:
        contact: Contacto a validar
        db: Sesión de base de datos
        company: Empresa actual
    
    Returns:
        Contact: El contacto si puede ser restaurado
    
    Raises:
        HTTPException: Si el contacto no puede ser restaurado
    """
    if not contact.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contacto no está eliminado"
        )
    
    # Verificar conflictos de documento
    if contact.id_number:
        contact_service = ContactService(db)
        existing = db.query(Contact).filter(
            Contact.company_id == company.id,
            Contact.id_number == contact.id_number,
            Contact.id != contact.id,
            Contact.deleted_at.is_(None)
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede restaurar: existe otro contacto activo con el documento {contact.id_number}"
            )
    
    return contact


async def validate_unique_document(
    id_number: str,
    contact_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_header)
) -> bool:
    """
    Dependency para validar unicidad de documento
    
    Args:
        id_number: Número de documento a validar
        contact_id: ID del contacto actual (para actualizaciones)
        db: Sesión de base de datos
        company: Empresa actual
    
    Returns:
        bool: True si el documento es único
    
    Raises:
        HTTPException: Si el documento ya existe
    """
    query = db.query(Contact).filter(
        Contact.company_id == company.id,
        Contact.id_number == id_number,
        Contact.deleted_at.is_(None)
    )
    
    if contact_id:
        query = query.filter(Contact.id != contact_id)
    
    existing = query.first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un contacto con el documento {id_number}"
        )
    
    return True


# ===== DEPENDENCIAS DE PERMISOS =====

async def require_contact_read_permission(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para verificar permisos de lectura de contactos"""
    # En el MVP todos los usuarios autenticados pueden leer contactos
    # TODO: Implementar roles específicos en versiones futuras
    return current_user


async def require_contact_write_permission(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para verificar permisos de escritura de contactos"""
    # En el MVP todos los usuarios autenticados pueden escribir contactos
    # TODO: Implementar roles específicos en versiones futuras
    return current_user


async def require_contact_delete_permission(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para verificar permisos de eliminación de contactos"""
    # En el MVP solo admins pueden eliminar contactos
    # TODO: Implementar validación de rol admin
    return current_user