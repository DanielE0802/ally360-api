from fastapi import APIRouter
from app.modules.inventory.models import Product, Category
from app.dependencies.dbDependecies import db_dependency

inventory_router = APIRouter()

@inventory_router.get("/products")
async def getAllProducts(db: db_dependency ):
    products = db.query(Product).all()
    return {"products": products}

@inventory_router.get("/products/{product_id}")
async def getProductById(product_id: str, db: db_dependency):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return {"error": "Product not found"}
    return {"product": product}

@inventory_router.get("/categories")
async def getAllCategories(db: db_dependency):
    categories = db.query(Category).all()
    return {"categories": categories}




@inventory_router.post("/register")
async def register():
    return {"message": "Register endpoint"}
