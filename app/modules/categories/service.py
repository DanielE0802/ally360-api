from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID

from app.modules.categories.models import Category
from app.modules.categories.schemas import CategoryCreate, CategoryUpdate

def create_category(db: Session, data: CategoryCreate, tenant_id: str):
    exists = db.query(Category).filter_by(name=data.name, tenant_id=tenant_id).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Ya existe una categoría con el nombre '{data.name}' en esta empresa"
        )

    category = Category(**data.model_dump(), tenant_id=tenant_id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

def get_all_categories(db: Session, tenant_id: str, limit: int = 100, offset: int = 0):
    categories = db.query(Category).filter_by(tenant_id=tenant_id).offset(offset).limit(limit).all()
    total = db.query(Category).filter_by(tenant_id=tenant_id).count()
    return {"categories": categories, "total": total, "limit": limit, "offset": offset}

def get_category_by_id(db: Session, category_id: UUID, tenant_id: str):
    category = db.query(Category).filter_by(id=category_id, tenant_id=tenant_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

def update_category(db: Session, category_id: UUID, data: CategoryUpdate, tenant_id: str):
    category = db.query(Category).filter_by(id=category_id, tenant_id=tenant_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(category, k, v)
    
    db.commit()
    db.refresh(category)
    return category

def delete_category(db: Session, category_id: UUID, tenant_id: str):
    category = db.query(Category).filter_by(id=category_id, tenant_id=tenant_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    db.delete(category)
    db.commit()
    return {"detail": "Category deleted successfully"}