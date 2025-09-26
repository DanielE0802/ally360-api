from fastapi import APIRouter, status
from uuid import UUID

from app.dependencies.dbDependecies import db_dependency
from app.dependencies.companyDependencies import UserCompanyContext
from app.modules.categories import service
from app.modules.categories.schemas import (
    CategoryCreate, CategoryUpdate, CategoryOut, CategoryList
)

categories_router = APIRouter(prefix="/categories", tags=["Categories"])

@categories_router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: db_dependency, current: UserCompanyContext):
    return service.create_category(db, data, current["company_id"])

@categories_router.get("/", response_model=CategoryList)
def list_categories(db: db_dependency, current: UserCompanyContext):
    return service.get_all_categories(db, current["company_id"])

@categories_router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: UUID, db: db_dependency, current: UserCompanyContext):
    return service.get_category_by_id(db, category_id, current["company_id"])

@categories_router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: UUID, data: CategoryUpdate, db: db_dependency, current: UserCompanyContext):
    return service.update_category(db, category_id, data, current["company_id"])

@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: UUID, db: db_dependency, current: UserCompanyContext):
    service.delete_category(db, category_id, current["company_id"])
    
