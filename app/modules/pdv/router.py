from fastapi import APIRouter, HTTPException, status, Path, Depends
from sqlalchemy.orm import Session
from app.dependencies.dbDependecies import get_db
from app.modules.auth.dependencies import get_auth_context, require_owner_or_admin, require_any_role
from app.modules.auth.schemas import AuthContext
from app.modules.pdv.models import PDV
from app.modules.pdv.schemas import PDVcreate, PDVUpdate, PDVOutput, PDVList
from app.modules.pdv import service
from app.modules.inventory.service import InventoryService
from uuid import UUID

pdv_router = APIRouter(prefix="/pdvs", tags=["PDVs"])

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
    return service.create_pdv(pdv, db, auth_context.tenant_id)

@pdv_router.get("/", response_model=PDVList)
def get_all_pdvs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    return service.get_all_pdvs(db, auth_context.tenant_id, limit, offset)

@pdv_router.get("/{pdv_id}", response_model=PDVOutput)
def get_pdv_by_id(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    return service.get_pdv_by_id(pdv_id, db, auth_context.tenant_id)

@pdv_router.patch("/{pdv_id}", response_model=PDVOutput)
def update_pdv(
    pdv_id: UUID,
    pdv_update: PDVUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    return service.update_pdv(pdv_id, pdv_update, db, auth_context.tenant_id)

@pdv_router.delete("/{pdv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdv(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    return service.delete_pdv(pdv_id, db, auth_context.tenant_id)



@pdv_router.get("/", response_model=PDVList)
def get_all_pdvs(
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_any_role())
):
    """Get all PDVs for company."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.get_all_pdvs(db, auth_context.tenant_id)

@pdv_router.get("/current", response_model=PDVOutput)
def get_current_pdv(
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_any_role())
):
    """Get current PDV from context (if available)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    # TODO: Implement PDV context from JWT token
    # For now, return main PDV
    return service.get_main_pdv(db, auth_context.tenant_id)

@pdv_router.get("/{pdv_id}", response_model=PDVOutput)
def get_pdv_by_id(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_any_role())
):
    """Get PDV by ID."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.get_pdv_by_id(pdv_id, db, auth_context.tenant_id)

@pdv_router.patch("/{pdv_id}", response_model=PDVOutput)
def update_pdv(
    pdv_id: UUID,
    pdv_update: PDVUpdate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Update PDV (owner/admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.update_pdv(pdv_id, pdv_update, db, auth_context.tenant_id)

@pdv_router.delete("/{pdv_id}", response_model=dict)
def delete_pdv(
    pdv_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_owner_or_admin())
):
    """Delete PDV (owner/admin only)."""
    if not auth_context.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company context required"
        )
    
    return service.delete_pdv(pdv_id, db, auth_context.tenant_id)

