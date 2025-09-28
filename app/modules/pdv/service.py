from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.modules.pdv.models import PDV
from app.modules.pdv.schemas import PDVcreate, PDVUpdate
from app.modules.inventory.service import InventoryService
from uuid import UUID

def create_pdv(pdv: PDVcreate, db: Session, tenant_id: str):
    existing_pdv = db.query(PDV).filter(PDV.tenant_id == tenant_id, PDV.name == pdv.name).first()
    if existing_pdv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un punto de venta con el nombre '{pdv.name}' en esta empresa"
        )

    new_pdv = PDV(**pdv.model_dump(), tenant_id=tenant_id)
    db.add(new_pdv)
    db.commit()
    db.refresh(new_pdv)

    # Create initial stock for all existing products in this tenant
    inventory_service = InventoryService(db)
    inventory_service.create_stock_for_new_pdv(tenant_id, new_pdv.id)

    return new_pdv


def get_all_pdvs(db: Session, tenant_id: str, limit: int = 100, offset: int = 0):
    pdvs = db.query(PDV).filter(PDV.tenant_id == tenant_id).offset(offset).limit(limit).all()
    total = db.query(PDV).filter(PDV.tenant_id == tenant_id).count()
    return {"pdvs": pdvs, "total": total, "limit": limit, "offset": offset}

def get_pdv_by_id(pdv_id: UUID, db: Session, tenant_id: str):
    pdv = db.query(PDV).filter(PDV.id == pdv_id, PDV.tenant_id == tenant_id).first()
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    return pdv

def update_pdv(pdv_id: UUID, pdv_update: PDVUpdate, db: Session, tenant_id: str):
    pdv = db.query(PDV).filter(PDV.id == pdv_id, PDV.tenant_id == tenant_id).first()
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    
    for key, value in pdv_update.model_dump(exclude_unset=True).items():
        setattr(pdv, key, value)
    
    db.commit()
    db.refresh(pdv)
    return pdv

def delete_pdv(pdv_id: UUID, db: Session, tenant_id: str):
    pdv = db.query(PDV).filter(PDV.id == pdv_id, PDV.tenant_id == tenant_id).first()
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    
    db.delete(pdv)
    db.commit()
    return {"message": "PDV deleted successfully"}
