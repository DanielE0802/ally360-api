from fastapi import APIRouter, status, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.categories import service
from app.modules.categories.schemas import (
    CategoryCreate, CategoryUpdate, CategoryOut, CategoryList
)

categories_router = APIRouter(tags=["Categories"])

@categories_router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    category_service = service.CategoryService(db)
    return category_service.create_category(data, auth_context.tenant_id, auth_context.user.id)

@categories_router.get("/", response_model=CategoryList)
def list_categories(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    category_service = service.CategoryService(db)
    return category_service.get_all_categories(auth_context.tenant_id, limit, offset)

@categories_router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: UUID, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    category_service = service.CategoryService(db)
    return category_service.get_category_by_id(category_id, auth_context.tenant_id)

@categories_router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: UUID, 
    data: CategoryUpdate, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    category_service = service.CategoryService(db)
    return category_service.update_category(category_id, data, auth_context.tenant_id, auth_context.user.id)

@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    category_service = service.CategoryService(db)
    category_service.delete_category(category_id, auth_context.tenant_id)
    
