from fastapi import APIRouter, HTTPException, status, Path, Depends
from app.dependencies.dbDependecies import db_dependency
from app.dependencies.companyDependencies import UserCompanyContext
from app.modules.pdv.models import PDV
from app.modules.pdv.schemas import PDVcreate, PDVUpdate, PDVOutput, PDVList
from app.modules.pdv import service
from uuid import UUID

pdv_router = APIRouter()

@pdv_router.post("/", response_model=PDVOutput)
async def create_pdv(
    pdv: PDVcreate,
    db: db_dependency,
    current: UserCompanyContext
):
    """Endpoint to create a new PDV."""
    return service.create_pdv(pdv, db, current)



@pdv_router.get("/", response_model=PDVList)
async def get_all_pdvs(
    db: db_dependency,
    current: UserCompanyContext
):
    """Endpoint to retrieve PDV information."""
    return service.get_all_pdvs(db, current)

@pdv_router.get("/{pdv_id}", response_model=PDVOutput)
async def get_pdv_by_id(
    pdv_id: UUID,
    db: db_dependency,
    current: UserCompanyContext
):
    """Endpoint to retrieve a PDV by its ID."""
    return service.get_pdv_by_id(pdv_id, db, current)

@pdv_router.patch("/{pdv_id}", response_model=PDVOutput)
async def update_pdv(
    pdv_id: UUID,
    pdv_update: PDVUpdate,
    db: db_dependency,
    current: UserCompanyContext
):
    """Endpoint to update a PDV."""
    return service.update_pdv(pdv_id, pdv_update, db, current)

@pdv_router.delete("/{pdv_id}", response_model=dict)
async def delete_pdv(
    pdv_id: UUID,
    db: db_dependency,
    current: UserCompanyContext
):
    """Endpoint to delete a PDV."""
    return service.delete_pdv(pdv_id, db, current)

