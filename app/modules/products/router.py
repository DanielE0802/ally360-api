from fastapi import APIRouter, status
from uuid import UUID
from app.dependencies.dbDependecies import db_dependency
from app.dependencies.companyDependencies import UserCompanyContext
from app.modules.products import service
from typing import List
from app.modules.products.schemas import ConfigurableProductCreate, SimpleProductWithStockCreate, ProductOut, ProductVariantOut, StockOut, ProductOutWithPdvs, ProductOutDefault

product_router = APIRouter(prefix="/products", tags=["Products"])

@product_router.post("/configurable", response_model=ProductOut)
def create_configurable(data: ConfigurableProductCreate, db: db_dependency, current: UserCompanyContext):
    return service.create_product_with_variants(db, data, current["company_id"])

@product_router.post("/simple", response_model=ProductOutDefault)
def create_simple(data: SimpleProductWithStockCreate, db: db_dependency, current: UserCompanyContext):
    return service.create_simple_product(db, data, current["company_id"])

@product_router.get("/", response_model=List[ProductOutWithPdvs])
def list_products(db: db_dependency, current: UserCompanyContext):
    return service.get_all_products(db, current["company_id"])

@product_router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: UUID, db: db_dependency, current: UserCompanyContext):
    return service.get_product_by_id(db, current["company_id"], product_id)

@product_router.get("/{product_id}/variants", response_model=List[ProductVariantOut])
def get_variants(product_id: UUID, db: db_dependency):
    return service.get_variants_by_product(db, product_id)

@product_router.get("/variants/{variant_id}/stock", response_model=List[StockOut])
def get_stock(variant_id: UUID, db: db_dependency):
    return service.get_stock_by_variant(db, variant_id)

@product_router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: UUID, db: db_dependency, current: UserCompanyContext):
    return service.delete_product(db, current["company_id"], product_id)