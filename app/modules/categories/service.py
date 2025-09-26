from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID

from app.modules.categories.models import Category
from app.modules.categories.schemas import CategoryCreate, CategoryUpdate

def create_category(db: Session, data: CategoryCreate, company_id: UUID):
    exists = db.query(Category).filter_by(name=data.name, company_id=company_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="Category already exists")

    category = Category(**data.model_dump(), company_id=company_id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

def get_all_categories(db: Session, company_id: UUID):
    categories = db.query(Category).filter_by(company_id=company_id).all()
    return {"categories": categories}

def get_category_by_id(db: Session, category_id: UUID, company_id: UUID):
    category = db.query(Category).filter_by(id=category_id, company_id=company_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

def update_category(db: Session, category_id: UUID, data: CategoryUpdate, company_id: UUID):
    category = db.query(Category).filter_by(id=category_id, company_id=company_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(category, k, v)
    
    db.commit()
    db.refresh(category)
    return category

def delete_category(db: Session, category_id: UUID, company_id: UUID):
    category = db.query(Category).filter_by(id=category_id, company_id=company_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    db.delete(category)
    db.commit()
    return {"detail": "Category deleted successfully"}