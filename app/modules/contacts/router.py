"""
Router para el módulo de Contactos

Endpoints REST para gestión completa de contactos:
- CRUD completo con validaciones
- Búsqueda avanzada con filtros
- Soft delete y restore
- Estadísticas y reportes
- Gestión de adjuntos
- Endpoints especializados para integración con Invoices y Bills

Todos los endpoints requieren autenticación y están scoped por company_id.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies

from app.modules.contacts.service import ContactService, ContactAttachmentService
from app.modules.contacts.schemas import (
    ContactCreate, ContactUpdate, ContactOut, ContactDetail, ContactList,
    ContactSearchFilters, ContactAttachmentCreate, ContactAttachmentOut,
    ContactRestore, ContactStats, ContactForInvoice, ContactForBill,
    ContactBulkAction
)

router = APIRouter(
    prefix="/contacts",
    tags=["Contacts"],
    responses={404: {"description": "Not found"}}
)


# ===== ENDPOINTS PRINCIPALES =====

@router.post("/", response_model=ContactDetail, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Crear un nuevo contacto
    
    - **name**: Nombre del contacto (requerido)
    - **type**: Array con tipos [client, provider, etc.]
    - **email**: Email válido (opcional)
    - **id_number**: Número de documento (debe ser único por empresa)
    - **fiscal_responsibilities**: Responsabilidades fiscales para Colombia
    """
    contact_service = ContactService(db)
    return contact_service.create_contact(contact_data, auth_context.tenant_id, auth_context.user_id)


@router.get("/", response_model=ContactList)
async def get_contacts(
    limit: int = Query(100, ge=1, le=500, description="Número máximo de contactos a retornar"),
    offset: int = Query(0, ge=0, description="Número de contactos a omitir"),
    search: Optional[str] = Query(None, description="Búsqueda por nombre, email o documento"),
    type: Optional[str] = Query(None, description="Filtrar por tipo: client, provider"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    seller_id: Optional[UUID] = Query(None, description="Filtrar por vendedor asignado"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar contactos con filtros opcionales
    
    Soporta paginación y múltiples filtros:
    - Búsqueda de texto libre
    - Filtro por tipo de contacto
    - Filtro por estado activo/inactivo
    - Filtro por vendedor asignado
    """
    # Construir filtros
    filters = ContactSearchFilters()
    if search:
        filters.search = search
    if type:
        from app.modules.contacts.models import ContactType
        try:
            filters.type = ContactType(type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de contacto inválido: {type}. Valores permitidos: client, provider"
            )
    if is_active is not None:
        filters.is_active = is_active
    if seller_id:
        filters.seller_id = seller_id
    
    contact_service = ContactService(db)
    return contact_service.get_contacts(auth_context.tenant_id, limit, offset, filters)


@router.get("/{contact_id}", response_model=ContactDetail)
async def get_contact(
    contact_id: UUID = Path(..., description="ID del contacto"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """Obtener un contacto específico por ID"""
    contact_service = ContactService(db)
    return contact_service.get_contact_by_id(contact_id, auth_context.tenant_id)


@router.put("/{contact_id}", response_model=ContactDetail)
async def update_contact(
    contact_data: ContactUpdate,
    contact_id: UUID = Path(..., description="ID del contacto"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Actualizar un contacto existente
    
    Solo se actualizan los campos proporcionados.
    Los campos no incluidos mantienen su valor actual.
    """
    contact_service = ContactService(db)
    return contact_service.update_contact(contact_id, contact_data, auth_context.tenant_id, auth_context.user_id)


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: UUID = Path(..., description="ID del contacto"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Eliminar un contacto (soft delete)
    
    El contacto no se elimina físicamente, solo se marca como eliminado
    para mantener la integridad referencial con facturas y compras.
    """
    contact_service = ContactService(db)
    return contact_service.delete_contact(contact_id, auth_context.tenant_id, auth_context.user_id)


@router.post("/{contact_id}/restore", response_model=ContactDetail)
async def restore_contact(
    restore_data: Optional[ContactRestore] = None,
    contact_id: UUID = Path(..., description="ID del contacto"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Restaurar un contacto eliminado
    
    Permite restaurar contactos que fueron eliminados previamente,
    siempre que no exista conflicto con documentos duplicados.
    """
    contact_service = ContactService(db)
    return contact_service.restore_contact(contact_id, auth_context.tenant_id, auth_context.user_id, restore_data)


# ===== ENDPOINTS DE ESTADÍSTICAS =====

@router.get("/stats/summary", response_model=ContactStats)
async def get_contact_stats(
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "accountant", "viewer"]))
):
    """
    Obtener estadísticas de contactos
    
    Retorna conteos por:
    - Total de contactos
    - Contactos activos
    - Clientes, proveedores, mixtos
    - Contactos eliminados
    """
    contact_service = ContactService(db)
    return contact_service.get_contact_stats(auth_context.tenant_id)


# ===== ENDPOINTS DE INTEGRACIÓN =====

@router.get("/clients/for-invoices", response_model=List[ContactForInvoice])
async def get_clients_for_invoices(
    search: Optional[str] = Query(None, description="Búsqueda por nombre, email o documento"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener contactos que son clientes para usar en facturas
    
    Retorna solo contactos activos que tienen el tipo 'client'.
    Formato optimizado para seleccionar cliente en facturas.
    """
    contact_service = ContactService(db)
    return contact_service.get_clients_for_invoices(auth_context.tenant_id, search)


@router.get("/providers/for-bills", response_model=List[ContactForBill])
async def get_providers_for_bills(
    search: Optional[str] = Query(None, description="Búsqueda por nombre, email o documento"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener contactos que son proveedores para usar en compras
    
    Retorna solo contactos activos que tienen el tipo 'provider'.
    Formato optimizado para seleccionar proveedor en compras.
    """
    contact_service = ContactService(db)
    return contact_service.get_providers_for_bills(auth_context.tenant_id, search)


# ===== ENDPOINTS DE ADJUNTOS =====

@router.post("/{contact_id}/attachments", response_model=ContactAttachmentOut, status_code=status.HTTP_201_CREATED)
async def create_contact_attachment(
    attachment_data: ContactAttachmentCreate,
    contact_id: UUID = Path(..., description="ID del contacto"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Agregar adjunto a un contacto
    
    Permite adjuntar documentos como:
    - RUT (Registro Único Tributario)
    - Cédula o documento de identidad
    - Certificado de cámara de comercio
    - Otros documentos legales
    """
    attachment_service = ContactAttachmentService(db)
    return attachment_service.create_attachment(contact_id, attachment_data, auth_context.tenant_id, auth_context.user_id)


@router.delete("/attachments/{attachment_id}")
async def delete_contact_attachment(
    attachment_id: UUID = Path(..., description="ID del adjunto"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """Eliminar adjunto de contacto"""
    attachment_service = ContactAttachmentService(db)
    return attachment_service.delete_attachment(attachment_id, auth_context.tenant_id)


# ===== ENDPOINTS DE ACCIONES MASIVAS =====

@router.post("/bulk/activate")
async def bulk_activate_contacts(
    action_data: ContactBulkAction,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Activar múltiples contactos
    
    Permite activar varios contactos de una vez.
    Útil para operaciones administrativas masivas.
    """
    contact_service = ContactService(db)
    results = []
    
    for contact_id in action_data.contact_ids:
        try:
            contact = contact_service.get_contact_by_id(contact_id, auth_context.tenant_id)
            if contact and not contact.is_active:
                contact.is_active = True
                contact.updated_by = auth_context.user_id
                db.commit()
                results.append({"id": contact_id, "status": "activated"})
            else:
                results.append({"id": contact_id, "status": "already_active"})
        except Exception as e:
            results.append({"id": contact_id, "status": "error", "message": str(e)})
    
    return {"results": results}


@router.post("/bulk/deactivate")
async def bulk_deactivate_contacts(
    action_data: ContactBulkAction,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Desactivar múltiples contactos
    
    Permite desactivar varios contactos de una vez.
    Los contactos desactivados no aparecen en búsquedas por defecto.
    """
    contact_service = ContactService(db)
    results = []
    
    for contact_id in action_data.contact_ids:
        try:
            contact = contact_service.get_contact_by_id(contact_id, auth_context.tenant_id)
            if contact and contact.is_active:
                contact.is_active = False
                contact.updated_by = auth_context.user_id
                db.commit()
                results.append({"id": contact_id, "status": "deactivated"})
            else:
                results.append({"id": contact_id, "status": "already_inactive"})
        except Exception as e:
            results.append({"id": contact_id, "status": "error", "message": str(e)})
    
    return {"results": results}