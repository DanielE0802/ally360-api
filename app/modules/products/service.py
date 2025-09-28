from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from sqlalchemy.orm import joinedload
from .models import Product, ProductTax, Tax
from .schemas import ProductCreate, ProductUpdate, ConfigurableProductCreate, SimpleProductWithStockCreate, ProductOut
from app.modules.products.models import ProductVariant, Stock
from app.modules.brands.models import Brand
from app.modules.categories.models import Category

def create_product_with_variants(db: Session, data: ConfigurableProductCreate, tenant_id: UUID):
    # Validar que el SKU no exista para este tenant
    existing_product = db.query(Product).filter(
        Product.sku == data.sku, 
        Product.tenant_id == tenant_id
    ).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un producto con el SKU '{data.sku}' en esta empresa"
        )
    
    # Validar que la marca existe y pertenece al tenant
    brand = db.query(Brand).filter(Brand.id == data.brand_id, Brand.tenant_id == tenant_id).first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La marca especificada no existe o no pertenece a esta empresa"
        )
    
    # Validar que la categoría existe y pertenece al tenant
    category = db.query(Category).filter(Category.id == data.category_id, Category.tenant_id == tenant_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La categoría especificada no existe o no pertenece a esta empresa"
        )
    
    # Validar que los SKUs de las variantes no se dupliquen
    variant_skus = [v.sku for v in data.variants]
    if len(variant_skus) != len(set(variant_skus)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los SKUs de las variantes no pueden duplicarse"
        )
    
    # Validar que los SKUs de las variantes no existan en otros productos de este tenant
    for variant_data in data.variants:
        existing_variant = db.query(ProductVariant).join(Product).filter(
            ProductVariant.sku == variant_data.sku,
            Product.tenant_id == tenant_id
        ).first()
        if existing_variant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una variante con el SKU '{variant_data.sku}' en esta empresa"
            )
    
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

    try:
        db.commit()
        db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        # Handle specific database integrity errors
        if "uq_product_tenant_sku" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un producto con el SKU '{data.sku}' en esta empresa"
            )
        elif "uq_product_variant_tenant_sku" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una variante con uno de los SKUs especificados en esta empresa"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

def create_simple_product(db: Session, data: SimpleProductWithStockCreate, tenant_id: UUID):
    # Validar que el SKU no exista para este tenant
    existing_product = db.query(Product).filter(
        Product.sku == data.sku, 
        Product.tenant_id == tenant_id
    ).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un producto con el SKU '{data.sku}' en esta empresa"
        )
    
    # Validar que la marca existe y pertenece al tenant
    brand = db.query(Brand).filter(Brand.id == data.brand_id, Brand.tenant_id == tenant_id).first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La marca especificada no existe o no pertenece a esta empresa"
        )
    
    # Validar que la categoría existe y pertenece al tenant
    category = db.query(Category).filter(Category.id == data.category_id, Category.tenant_id == tenant_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La categoría especificada no existe o no pertenece a esta empresa"
        )
    
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

    # Asignar impuestos si se proporcionan
    if hasattr(data, 'tax_ids') and data.tax_ids:
        # Validar que todos los impuestos existen y están disponibles para el tenant
        taxes = db.query(Tax).filter(
            Tax.id.in_(data.tax_ids),
            (Tax.company_id == tenant_id) | (Tax.company_id.is_(None))
        ).all()
        
        if len(taxes) != len(data.tax_ids):
            found_ids = {tax.id for tax in taxes}
            missing_ids = set(data.tax_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Impuestos no encontrados: {list(missing_ids)}"
            )
        
        # Crear las relaciones ProductTax
        for tax_id in data.tax_ids:
            product_tax = ProductTax(
                product_id=product.id,
                tax_id=tax_id,
                tenant_id=tenant_id
            )
            db.add(product_tax)

    try:
        db.commit()
        db.refresh(product)
        return product
    except Exception as e:
        db.rollback()
        # Handle specific database integrity errors
        if "uq_product_tenant_sku" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un producto con el SKU '{data.sku}' en esta empresa"
            )
        elif "uq_product_variant_tenant_sku" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una variante con el SKU '{data.sku}' en esta empresa"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

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