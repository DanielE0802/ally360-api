from fastapi import APIRouter, Depends, status
from app.dependencies.dbDependecies import db_dependency
from app.dependencies.companyDependencies import UserCompanyContext
from app.modules.brands import service
from app.modules.brands.schemas import BrandCreate, BrandUpdate, BrandOut, BrandList
from uuid import UUID

brand_router = APIRouter(prefix="/brands", tags=["Brands"])

@brand_router.post("/", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(brand: BrandCreate, db: db_dependency, current: UserCompanyContext):
    return service.create_brand(db, brand, current["company_id"])

@brand_router.get("/", response_model=BrandList)
def list_brands(db: db_dependency, current: UserCompanyContext):
    return service.get_all_brands(db, current["company_id"])

@brand_router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: UUID, db: db_dependency, current: UserCompanyContext):
    return service.get_brand_by_id(db, brand_id, current["company_id"])

@brand_router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(brand_id: UUID, update: BrandUpdate, db: db_dependency, current: UserCompanyContext):
    return service.update_brand(db, brand_id, update, current["company_id"])

@brand_router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(brand_id: UUID, db: db_dependency, current: UserCompanyContext):
    service.delete_brand(db, brand_id, current["company_id"])