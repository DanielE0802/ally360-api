from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from app.modules.brands.models import Brand
from app.modules.brands.schemas import BrandCreate, BrandUpdate

def create_brand(db: Session, brand_data: BrandCreate, company_id: UUID):
    existing = db.query(Brand).filter_by(name=brand_data.name, company_id=company_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Brand already exists in this company")

    brand = Brand(**brand_data.model_dump(), company_id=company_id)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand

def get_all_brands(db: Session, company_id: UUID):
    brands = db.query(Brand).filter_by(company_id=company_id).all()
    return {"brands": brands}

def get_brand_by_id(db: Session, brand_id: UUID, company_id: UUID):
    brand = db.query(Brand).filter_by(id=brand_id, company_id=company_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

def update_brand(db: Session, brand_id: UUID, update: BrandUpdate, company_id: UUID):
    brand = db.query(Brand).filter_by(id=brand_id, company_id=company_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(brand, k, v)
    
    db.commit()
    db.refresh(brand)
    return brand

def delete_brand(db: Session, brand_id: UUID, company_id: UUID):
    brand = db.query(Brand).filter_by(id=brand_id, company_id=company_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    db.delete(brand)
    db.commit()
    return {"detail": "Brand deleted successfully"}