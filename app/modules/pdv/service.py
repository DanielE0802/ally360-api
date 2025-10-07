from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.modules.pdv.models import PDV
from app.modules.pdv.schemas import PDVcreate, PDVUpdate
from app.modules.inventory.service import InventoryService
from app.modules.locations.models import Department, City
from uuid import UUID

def create_pdv(pdv: PDVcreate, db: Session, tenant_id: str):
    # Validate location data if provided
    if pdv.department_id:
        department = db.query(Department).filter(Department.id == pdv.department_id).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with ID {pdv.department_id} not found"
            )

    if pdv.city_id:
        city = db.query(City).filter(City.id == pdv.city_id).first()
        if not city:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"City with ID {pdv.city_id} not found"
            )
        
        # Validate that city belongs to the specified department
        if pdv.department_id and city.department_id != pdv.department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"City {city.name} does not belong to the specified department"
            )

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

    # Load relationships for response
    db.refresh(new_pdv)
    pdv_with_relations = db.query(PDV).options(
        joinedload(PDV.department),
        joinedload(PDV.city).joinedload(City.department)
    ).filter(PDV.id == new_pdv.id).first()

    return pdv_with_relations


def get_all_pdvs(db: Session, tenant_id: str, limit: int = 100, offset: int = 0):
    pdvs = db.query(PDV).options(
        joinedload(PDV.department),
        joinedload(PDV.city).joinedload(City.department)
    ).filter(PDV.tenant_id == tenant_id).offset(offset).limit(limit).all()
    
    total = db.query(PDV).filter(PDV.tenant_id == tenant_id).count()
    return {"pdvs": pdvs, "total": total, "limit": limit, "offset": offset}

def get_pdv_by_id(pdv_id: UUID, db: Session, tenant_id: str):
    pdv = db.query(PDV).options(
        joinedload(PDV.department),
        joinedload(PDV.city).joinedload(City.department)
    ).filter(PDV.id == pdv_id, PDV.tenant_id == tenant_id).first()
    
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    return pdv

def update_pdv(pdv_id: UUID, pdv_update: PDVUpdate, db: Session, tenant_id: str):
    # Validate location data if provided
    if pdv_update.department_id:
        department = db.query(Department).filter(Department.id == pdv_update.department_id).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with ID {pdv_update.department_id} not found"
            )
    
    if pdv_update.city_id:
        city = db.query(City).filter(City.id == pdv_update.city_id).first()
        if not city:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"City with ID {pdv_update.city_id} not found"
            )
        
        # Validate that city belongs to the specified department (if both are provided)
        if pdv_update.department_id and city.department_id != pdv_update.department_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"City {city.name} does not belong to the specified department"
            )

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
    
    # Load relationships for response
    pdv_with_relations = db.query(PDV).options(
        joinedload(PDV.department),
        joinedload(PDV.city).joinedload(City.department)
    ).filter(PDV.id == pdv.id).first()
    
    return pdv_with_relations

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
