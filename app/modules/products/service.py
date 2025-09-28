from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from sqlalchemy.orm import joinedload
from .models import Product
from .schemas import ProductCreate, ProductUpdate, ConfigurableProductCreate, SimpleProductWithStockCreate, ProductOut
from app.modules.products.models import ProductVariant, Stock
from app.modules.brands.models import Brand
from app.modules.categories.models import Category

def create_product_with_variants(db: Session, data: ConfigurableProductCreate, tenant_id: UUID):
    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        is_configurable=True,
        brand_id=data.brand_id,
        category_id=data.category_id,
        tenant_id=tenant_id
    )
    db.add(product)
    db.flush()

    for variant_data in data.variants:
        variant = ProductVariant(
            product_id=product.id,
            sku=variant_data.sku,
            price=variant_data.price,
            color=variant_data.color,
            size=variant_data.size,
            tenant_id=tenant_id
        )
        db.add(variant)
        db.flush()

        for stock in variant_data.stocks:
            db.add(Stock(
                product_id=product.id,
                variant_id=variant.id, 
                pdv_id=stock.pdv_id, 
                quantity=stock.quantity,
                tenant_id=tenant_id
            ))

    db.commit()
    db.refresh(product)
    return product

def create_simple_product(db: Session, data: SimpleProductWithStockCreate, tenant_id: UUID):
    print(f"DEBUG SERVICE: tenant_id = {tenant_id}")
    print(f"DEBUG SERVICE: tenant_id type = {type(tenant_id)}")
    
    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        is_configurable=False,
        brand_id=data.brand_id,
        category_id=data.category_id,
        tenant_id=tenant_id
    )
    db.add(product)
    db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku=data.sku,
        price=data.price,
        tenant_id=tenant_id
    )
    db.add(variant)
    db.flush()

    for stock in data.stocks:
        db.add(Stock(
            product_id=product.id,
            variant_id=variant.id, 
            pdv_id=stock.pdv_id, 
            quantity=stock.quantity,
            tenant_id=tenant_id
        ))

    db.commit()
    db.refresh(product)
    return product

def get_all_products(db: Session, tenant_id: UUID, **kwargs):
    query = db.query(Product) \
        .options(joinedload(Product.brand), joinedload(Product.category)) \
        .filter(Product.tenant_id == tenant_id)
    
    # Add filters if provided
    category_id = kwargs.get('category_id')
    brand_id = kwargs.get('brand_id')
    name = kwargs.get('name')
    limit = kwargs.get('limit', 50)
    offset = kwargs.get('offset', 0)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if name:
        query = query.filter(Product.name.ilike(f"%{name}%"))
        
    products = query.offset(offset).limit(limit).all()
    return products

def get_product_by_id(db: Session, tenant_id: UUID, product_id: UUID):
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return product

def get_variants_by_product(db: Session, product_id: UUID, tenant_id: UUID):
    # First check if product belongs to tenant
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return db.query(ProductVariant).filter(ProductVariant.product_id == product_id).all()

def get_stock_by_variant(db: Session, variant_id: UUID):
    return db.query(Stock).filter(Stock.variant_id == variant_id).all()

def update_product(db: Session, tenant_id: UUID, product_id: UUID, data: dict):
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    
    for key, value in data.items():
        if hasattr(product, key):
            setattr(product, key, value)
    
    db.commit()
    db.refresh(product)
    return product

def delete_product(db: Session, tenant_id: UUID, product_id: UUID):
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    db.delete(product)
    db.commit()
    return {"message": "Producto eliminado exitosamente"}