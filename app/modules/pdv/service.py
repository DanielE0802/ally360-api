from fastapi import Depends, HTTPException, status
from app.dependencies.dbDependecies import db_dependency
from app.dependencies.companyDependencies import get_current_user_and_company
from app.modules.pdv.models import PDV
from app.modules.pdv.schemas import PDVcreate, PDVUpdate, PDVOutput, PDVList
from fastapi import APIRouter
from uuid import UUID

def create_pdv(pdv: PDVcreate, db: db_dependency, current = Depends(get_current_user_and_company)):
    company_id = current.get("company_id")
    existing_pdv = db.query(PDV).filter(PDV.company_id == company_id, PDV.name == pdv.name).first()
    if existing_pdv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDV with this name already exists"
        )
    
    pdv.company_id = company_id
    db.add(pdv)
    db.commit()
    db.refresh(pdv)
    return {"message": "PDV created successfully", "pdv": pdv}


def get_all_pdvs(db: db_dependency, current = Depends(get_current_user_and_company)):
    company_id = current.get("company_id")
    pdvs = db.query(PDV).filter(PDV.company_id == company_id).all()
    return {"pdvs": pdvs}

def get_pdv_by_id(pdv_id: UUID, db: db_dependency, current = Depends(get_current_user_and_company)):
    company_id = current.get("company_id")
    pdv = db.query(PDV).filter(PDV.id == pdv_id, PDV.company_id == company_id).first()
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    return {"pdv": pdv}

def update_pdv(pdv_id: UUID, pdv_update: PDVUpdate, db: db_dependency, current = Depends(get_current_user_and_company)):
    company_id = current.get("company_id")
    pdv = db.query(PDV).filter(PDV.id == pdv_id, PDV.company_id == company_id).first()
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    
    for key, value in pdv_update.dict(exclude_unset=True).items():
        setattr(pdv, key, value)
    
    db.commit()
    db.refresh(pdv)
    return {"message": "PDV updated successfully", "pdv": pdv}


def delete_pdv(pdv_id: UUID, db: db_dependency, current = Depends(get_current_user_and_company)):
    company_id = current.get("company_id")
    pdv = db.query(PDV).filter(PDV.id == pdv_id, PDV.company_id == company_id).first()
    if not pdv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDV not found"
        )
    
    db.delete(pdv)
    db.commit()
    return {"message": "PDV deleted successfully"}
