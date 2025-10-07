from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.pdv import service
from app.modules.pdv.schemas import PDVcreate, PDVUpdate, PDVOutput, PDVList

pdv_router = APIRouter(prefix="/pdvs", tags=["PDVs"])

@pdv_router.post("/", response_model=PDVOutput, status_code=status.HTTP_201_CREATED)
def create_pdv(
    pdv: PDVcreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Crear nuevo punto de venta (PDV).
    
    Solo usuarios con rol owner o admin pueden crear PDVs.
    """
    return service.create_pdv(pdv, db, auth_context.tenant_id)

@pdv_router.get("/", response_model=PDVList)
def get_all_pdvs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Obtener lista de todos los PDVs de la empresa.
    
    Disponible para todos los roles autenticados.
    """
    return service.get_all_pdvs(db, auth_context.tenant_id, limit, offset)

@pdv_router.get("/{pdv_id}", response_model=PDVOutput)
def get_pdv_by_id(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Obtener PDV por ID.
    
    Disponible para todos los roles autenticados.
    """
    return service.get_pdv_by_id(pdv_id, db, auth_context.tenant_id)

@pdv_router.patch("/{pdv_id}", response_model=PDVOutput)
def update_pdv(
    pdv_id: UUID,
    pdv_update: PDVUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Actualizar PDV existente.
    
    **Para editar PDV (similar a empresa).**
    
    Solo usuarios con rol owner o admin pueden editar PDVs.
    
    Campos que se pueden actualizar:
    - name: Nombre del PDV
    - address: Dirección
    - phone_number: Teléfono (formato colombiano)
    - is_active: Estado activo/inactivo
    """
    return service.update_pdv(pdv_id, pdv_update, db, auth_context.tenant_id)

@pdv_router.delete("/{pdv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdv(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Eliminar PDV.
    
    Solo usuarios con rol owner o admin pueden eliminar PDVs.
    """
    return service.delete_pdv(pdv_id, db, auth_context.tenant_id)

