from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from app.modules.brands.models import Brand
from app.modules.brands.schemas import BrandCreate, BrandUpdate

def create_brand(db: Session, brand_data: BrandCreate, tenant_id: str):
    existing = db.query(Brand).filter_by(name=brand_data.name, tenant_id=tenant_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Ya existe una marca con el nombre '{brand_data.name}' en esta empresa"
        )

    brand = Brand(**brand_data.model_dump(), tenant_id=tenant_id)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand

def get_all_brands(db: Session, tenant_id: str, limit: int = 100, offset: int = 0):
    brands = db.query(Brand).filter_by(tenant_id=tenant_id).offset(offset).limit(limit).all()
    total = db.query(Brand).filter_by(tenant_id=tenant_id).count()
    return {"brands": brands, "total": total, "limit": limit, "offset": offset}

def get_brand_by_id(db: Session, brand_id: UUID, tenant_id: str):
    brand = db.query(Brand).filter_by(id=brand_id, tenant_id=tenant_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

def update_brand(db: Session, brand_id: UUID, update: BrandUpdate, tenant_id: str):
    brand = db.query(Brand).filter_by(id=brand_id, tenant_id=tenant_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(brand, k, v)
    
    db.commit()
    db.refresh(brand)
    return brand

def delete_brand(db: Session, brand_id: UUID, tenant_id: str):
    brand = db.query(Brand).filter_by(id=brand_id, tenant_id=tenant_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    db.delete(brand)
    db.commit()
    return {"detail": "Brand deleted successfully"}