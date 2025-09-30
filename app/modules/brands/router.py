from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.brands import service
from app.modules.brands.schemas import BrandCreate, BrandUpdate, BrandOut, BrandList
from uuid import UUID

brand_router = APIRouter(tags=["Brands"])

@brand_router.post("/", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(
    brand: BrandCreate, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    brand_service = service.BrandService(db)
    return brand_service.create_brand(brand, auth_context.tenant_id, auth_context.user.id)

@brand_router.get("/", response_model=BrandList)
def list_brands(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    brand_service = service.BrandService(db)
    return brand_service.get_all_brands(auth_context.tenant_id, limit, offset)

@brand_router.get("/{brand_id}", response_model=BrandOut)
def get_brand(
    brand_id: UUID, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    brand_service = service.BrandService(db)
    return brand_service.get_brand_by_id(brand_id, auth_context.tenant_id)

@brand_router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: UUID, 
    update: BrandUpdate, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    brand_service = service.BrandService(db)
    return brand_service.update_brand(brand_id, update, auth_context.tenant_id, auth_context.user.id)

@brand_router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand(
    brand_id: UUID, 
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    brand_service = service.BrandService(db)
    brand_service.delete_brand(brand_id, auth_context.tenant_id)