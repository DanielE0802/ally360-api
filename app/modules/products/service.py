from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from sqlalchemy.orm import joinedload
from .models import Product
from .schemas import ProductCreate, ProductUpdate, ConfigurableProductCreate, SimpleProductWithStockCreate, ProductOut
from app.modules.products.models import ProductVariant, Stock
from app.modules.brands.models import Brand
from app.modules.categories.models import Category

def create_product_with_variants(db: Session, data: ConfigurableProductCreate, company_id: UUID):
    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        is_configurable=True,
        brand_id=data.brand_id,
        category_id=data.category_id,
        company_id=company_id
    )
    db.add(product)
    db.flush()

    for variant_data in data.variants:
        variant = ProductVariant(
            product_id=product.id,
            sku=variant_data.sku,
            price=variant_data.price,
            color=variant_data.color,
            size=variant_data.size
        )
        db.add(variant)
        db.flush()

        for stock in variant_data.stocks:
            db.add(Stock(variant_id=variant.id, pdv_id=stock.pdv_id, quantity=stock.quantity))

    db.commit()
    db.refresh(product)
    return product

def create_simple_product(db: Session, data: SimpleProductWithStockCreate, company_id: UUID):
    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        is_configurable=False,
        brand_id=data.brand_id,
        category_id=data.category_id,
        company_id=company_id
    )
    db.add(product)
    db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku=data.sku,
        price=data.price
    )
    db.add(variant)
    db.flush()

    for stock in data.stocks:
        db.add(Stock(variant_id=variant.id, pdv_id=stock.pdv_id, quantity=stock.quantity))

    db.commit()
    db.refresh(product)
    return product

def get_all_products(db: Session, company_id: UUID):
    products = (
        db.query(Product)
        .filter(Product.company_id == company_id)
        .options(
            joinedload(Product.brand),
            joinedload(Product.category),
            joinedload(Product.stocks).joinedload(Stock.pdv)
        )
        .all()
    )

    result = []
    for product in products:
        stock_info = [
            {
                "pdv_id": stock.pdv.id,
                "pdv_name": stock.pdv.name,
                "quantity": stock.quantity
            }
            for stock in product.stocks
        ]

        result.append(ProductOut(
            id=product.id,
            name=product.name,
            sku=product.sku,
            description=product.description,
            is_configurable=product.is_configurable,
            created_at=product.created_at,
            brand=product.brand,
            category=product.category,
            pdvs=stock_info
        ))

    return result

def get_product_by_id(db: Session, company_id: UUID, product_id: UUID):
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return product

def get_variants_by_product(db: Session, product_id: UUID):
    return db.query(ProductVariant).filter(ProductVariant.product_id == product_id).all()

def get_stock_by_variant(db: Session, variant_id: UUID):
    return db.query(Stock).filter(Stock.variant_id == variant_id).all()

def delete_product(db: Session, company_id: UUID, product_id: UUID):
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    db.delete(product)
    db.commit()
    return {"message": "Producto eliminado exitosamente"}