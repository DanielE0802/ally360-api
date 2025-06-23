from fastapi import APIRouter, HTTPException, status, Path 
from app.modules.inventory.models import Product, Category
from app.dependencies.dbDependecies import db_dependency
from app.modules.inventory.schemas import ProductCreate, ProductUpdate
from uuid import UUID

product_router = APIRouter()
category_router = APIRouter()


@product_router.get("/products")
async def get_all_products(db: db_dependency ):
    """ Retrieve all products from the database. """
    products = db.query(Product).all()
    return {"products": products}

@product_router.get("/products/{product_id}")
async def get_product_by_id(product_id: UUID, db: db_dependency):
    """ Retrieve a product by its ID. """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Produc not found')
    return {"product": product}

@product_router.post("/product")
async def create_product(
    product: ProductCreate,
    db: db_dependency
):
    existing_product = db.query(Product).filter(Product.name == product.name).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this name already exists"
        )
    
    new_product = Product(**product.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    return {"product": new_product}

@product_router.patch("/product/{product_id}")
async def patch_product(
    product_update: ProductUpdate,
    db: db_dependency,
    product_id: UUID = Path(..., description="The ID of the product to update"),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')
    
    for key, value in product_update.dict(exclude_unset=True).items():
        setattr(product, key, value)
    
    db.commit()
    db.refresh(product)
    return {"product": product}

@product_router.delete("/product/{product_id}")
async def delete_product(product_id: UUID, db: db_dependency):
    """ Delete a product by its ID. """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Product not found')
    
    db.delete(product)
    db.commit()
    return {"detail": "Product deleted successfully"}

"------------------------------- Category Endpoints -------------------------------"

@category_router.get("/categories")
async def get_all_categories(db: db_dependency):
    """ Retrieve all categories from the database. """
    categories = db.query(Category).all()
    return {"categories": categories}

@category_router.get("/categories/{category_id}")
async def get_category_by_id(category_id: UUID, db: db_dependency):
    """ Retrieve a category by its ID. """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
    return {"category": category}
