from app.modules.products.schemas import LowStockProduct, LowStockResponse
async def get_low_stock_products(db, tenant_id: str) -> LowStockResponse:
    """Return products with stock below min_stock for the tenant."""
    from sqlalchemy import select, and_
    from app.modules.products.models import Product, Stock
    from app.modules.pdv.models import PDV

    query = (
        select(Product, Stock, PDV)
        .join(Stock, Stock.product_id == Product.id)
        .join(PDV, Stock.pdv_id == PDV.id)
        .where(
            Product.tenant_id == tenant_id,
            Stock.quantity <= Stock.min_quantity
        )
    )
    result = await db.execute(query)
    items = []
    for product, stock, pdv in result.fetchall():
        items.append(LowStockProduct(
            id=str(product.id),
            name=product.name,
            sku=product.sku,
            current_stock=stock.quantity,
            min_stock=stock.min_quantity,
            pdv_id=str(pdv.id),
            pdv_name=pdv.name
        ))
    return LowStockResponse(products=items, total_count=len(items))
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status, UploadFile
from uuid import UUID, uuid4
from typing import Optional, List
from datetime import timedelta
import math
import logging
import base64
import io

from .models import Product, ProductTax, Tax
from .schemas import ProductCreate, ProductUpdate, ConfigurableProductCreate, SimpleProductWithStockCreate, ProductOut, GetProductResponse, ProductImageCreate, ProductImageOut
from app.modules.products.models import ProductVariant, Stock, ProductImage
from app.modules.brands.models import Brand
from app.modules.categories.models import Category
from app.modules.pdv.models import PDV
from app.modules.files.service import minio_service

logger = logging.getLogger(__name__)

def process_base64_images(product_id: UUID, images: List[str], tenant_id: UUID, db: Session) -> None:
    """Procesa imágenes en base64 y las guarda en MinIO"""
    print("Processing base64 images...")
    print(f"Received {len(images)} images for product {product_id}")
    
    if not images:
        return
    
    for i, base64_image in enumerate(images):
        try:
            # Validar formato base64
            print(f"Processing image {i+1}")
            if not base64_image.startswith('data:image/'):
                logger.warning(f"Imagen {i} no tiene formato base64 válido")
                continue
            
            # Extraer el tipo de contenido y los datos
            header, data = base64_image.split(',', 1)
            content_type = header.split(';')[0].split(':')[1]
            
            # Decodificar base64
            image_data = base64.b64decode(data)
            
            # Determinar extensión
            extension = content_type.split('/')[-1]
            if extension == 'jpeg':
                extension = 'jpg'
            
            # Generar key único para el archivo
            file_key = f"products/{tenant_id}/{product_id}/images/{uuid4()}.{extension}"
            file_name = f"image_{i+1}.{extension}"
            
            print(f"Uploading to MinIO with key: {file_key}")
            
            # Subir a MinIO (versión síncrona)
            minio_service.client.put_object(
                bucket_name=minio_service.bucket_name,
                object_name=file_key,
                data=io.BytesIO(image_data),
                length=len(image_data),
                content_type=content_type
            )
            
            print(f"Successfully uploaded to MinIO: {file_key}")
            
            # Crear registro en la base de datos
            product_image = ProductImage(
                product_id=product_id,
                file_key=file_key,
                file_name=file_name,
                file_size=len(image_data),
                content_type=content_type,
                is_primary=(i == 0),  # Primera imagen es principal
                sort_order=i,
                tenant_id=tenant_id
            )
            
            db.add(product_image)
            print(f"Added ProductImage to session: {file_key}")
            
        except Exception as e:
            logger.error(f"Error procesando imagen {i}: {e}")
            print(f"Error processing image {i}: {e}")
            continue
    
    # Hacer commit después de procesar todas las imágenes
    try:
        db.commit()
        print("Successfully committed all images to database")
    except Exception as e:
        logger.error(f"Error committing images to database: {e}")
        print(f"Error committing to database: {e}")
        db.rollback()
        raise

def product_to_response(product: Product) -> dict:
    """Convierte un modelo Product al formato GetProductResponse"""
    # Calcular stock total
    total_stock = sum(stock.quantity for stock in product.stocks) if product.stocks else 0
    
    # Crear array de productPdv con información por PDV
    product_pdv = []
    if product.stocks:
        for stock in product.stocks:
            pdv_info = {
                "pdv_id": str(stock.pdv_id),
                "pdv_name": stock.pdv.name if hasattr(stock, 'pdv') and stock.pdv else f"PDV {stock.pdv_id}",
                "quantity": stock.quantity,
                "min_quantity": getattr(stock, 'min_quantity', 0)
            }
            product_pdv.append(pdv_info)
    
    # Obtener URLs de imágenes
    images = []
    if hasattr(product, 'images') and product.images:
        for image in sorted(product.images, key=lambda x: x.sort_order):
            try:
                # Generar URL presignada para descarga (válida por 1 hora)
                image_url = minio_service.get_presigned_download_url(
                    image.file_key,
                    expires=timedelta(hours=1)
                )
                images.append(image_url)
            except Exception as e:
                logger.warning(f"Error generando URL para imagen {image.id}: {e}")
                continue
    
    # Obtener información de brand y category
    brand_info = {
        "id": str(product.brand.id) if product.brand else "",
        "name": product.brand.name if product.brand else ""
    }
    
    category_info = {
        "id": str(product.category.id) if product.category else "",
        "name": product.category.name if product.category else ""
    }
    
    # Determinar typeProduct basado en is_configurable
    type_product = "2" if product.is_configurable else "1"
    
    # Contar impuestos asignados
    taxes_count = len(product.product_taxes) if product.product_taxes else 0
    
    return {
        "id": str(product.id),
        "name": product.name,
        "description": product.description,
        "barCode": product.bar_code,
        "images": images,  # URLs presignadas de las imágenes
        "typeProduct": type_product,
        "taxesOption": taxes_count,
        "sku": product.sku,
        "priceSale": float(product.price_sale) if product.price_sale else 0.0,
        "priceBase": float(product.price_base) if product.price_base else 0.0,
        "quantityStock": total_stock,
        "globalStock": total_stock,  # Alias del stock total
        "state": product.is_active if hasattr(product, 'is_active') else True,
        "sellInNegative": product.sell_in_negative if hasattr(product, 'sell_in_negative') else False,
        "category": category_info,
        "brand": brand_info,
        "productPdv": product_pdv
    }

async def get_products(
    db: AsyncSession,
    tenant_id: str,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    is_active: Optional[bool] = None
) -> dict:
    """
    Obtiene una lista paginada de productos
    """
    try:
        # Convertir tenant_id a UUID
        tenant_uuid = UUID(tenant_id)
        
        # Construir query base
        query = select(Product).where(Product.tenant_id == tenant_uuid)
        
        # Aplicar filtros opcionales
        if search:
            query = query.where(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%")
                )
            )
        
        if category_id:
            query = query.where(Product.category_id == UUID(category_id))
        
        if brand_id:
            query = query.where(Product.brand_id == UUID(brand_id))
        
        if is_active is not None:
            query = query.where(Product.is_active == is_active)
        
        # Incluir relaciones
        query = query.options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.stocks).selectinload(Stock.pdv),
            selectinload(Product.product_taxes),
            selectinload(Product.images)
        )
        
        # Contar total de registros
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Aplicar paginación
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        # Ejecutar query
        result = await db.execute(query)
        products = result.scalars().all()
        
        # Convertir productos al formato de respuesta
        product_data = [product_to_response(product) for product in products]
        
        # Calcular metadatos de paginación
        has_next = (offset + limit) < total
        has_prev = page > 1
        
        # Métricas/Metadatos para filtros (conteos rápidos por estado activo)
        # Nota: productos no tienen estados múltiples como invoices/bills; exponemos conteos por is_active si aplica
        counts_by_status = []
        for active_state in [True, False]:
            base_q = select(func.count()).select_from(Product).where(Product.tenant_id == tenant_uuid)
            # aplicar mismos filtros excepto is_active y paginación
            if search:
                base_q = base_q.where(
                    or_(
                        Product.name.ilike(f"%{search}%"),
                        Product.sku.ilike(f"%{search}%"),
                        Product.description.ilike(f"%{search}%")
                    )
                )
            if category_id:
                base_q = base_q.where(Product.category_id == UUID(category_id))
            if brand_id:
                base_q = base_q.where(Product.brand_id == UUID(brand_id))
            base_q = base_q.where(Product.is_active == active_state)
            count_res = await db.execute(base_q)
            counts_by_status.append({"status": "ACTIVE" if active_state else "INACTIVE", "count": count_res.scalar() or 0})

        return {
            "data": product_data,
            "total": total,
            "page": page,
            "limit": limit,
            "hasNext": has_next,
            "hasPrev": has_prev,
            "applied_filters": {
                "search": search,
                "category_id": category_id,
                "brand_id": brand_id,
                "is_active": is_active,
            },
            "counts_by_status": counts_by_status
        }
        
    except Exception as e:
        raise Exception(f"Error obteniendo productos: {str(e)}")

async def get_product_by_id_async(db: AsyncSession, tenant_id: str, product_id: str) -> dict:
    """
    Obtiene un producto por ID de forma asíncrona
    """
    try:
        tenant_uuid = UUID(tenant_id)
        product_uuid = UUID(product_id)
        
        query = select(Product).where(
            Product.id == product_uuid,
            Product.tenant_id == tenant_uuid
        ).options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.stocks).selectinload(Stock.pdv),
            selectinload(Product.product_taxes),
            selectinload(Product.images)
        )
        
        result = await db.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Producto no encontrado"
            )
        
        return product_to_response(product)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de producto inválido"
        )
    except Exception as e:
        raise Exception(f"Error obteniendo producto: {str(e)}")

async def upload_product_image(
    product_id: UUID,
    image_file: UploadFile,
    tenant_id: UUID,
    user_id: UUID,
    db: AsyncSession
) -> ProductImageOut:
    """Upload single image file for a product"""
    # Check if product exists and belongs to tenant
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
            Product.deleted_at == None
        )
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Validate file
    if image_file.content_type not in ['image/jpeg', 'image/png', 'image/jpg']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and JPG files are allowed"
        )
    
    # Read file content
    content = await image_file.read()
    
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 5MB limit"
        )
    
    # Generate unique filename
    image_id = uuid4()
    ext = image_file.filename.split('.')[-1].lower()
    filename = f"{image_id}.{ext}"
    
    # Create MinIO key
    key = f"products/{tenant_id}/{product_id}/images/{filename}"
    
    try:
        # Upload to MinIO using direct client
        minio_service.client.put_object(
            bucket_name=minio_service.bucket_name,
            object_name=key,
            data=io.BytesIO(content),
            length=len(content),
            content_type=image_file.content_type
        )
    except Exception as e:
        logger.error(f"Error uploading image to MinIO: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image"
        )
    
    # Get next sort order
    result = await db.execute(
        select(func.max(ProductImage.sort_order))
        .where(ProductImage.product_id == product_id)
    )
    max_order = result.scalar() or 0
    
    # Create image record
    product_image = ProductImage(
        id=image_id,
        product_id=product_id,
        file_key=key,
        content_type=image_file.content_type,
        sort_order=max_order + 1,
        uploaded_by=user_id
    )
    
    db.add(product_image)
    await db.commit()
    await db.refresh(product_image)
    
    # Generate download URL
    download_url = minio_service.get_presigned_download_url(key)
    
    return ProductImageOut(
        id=product_image.id,
        product_id=product_image.product_id,
        download_url=download_url,
        content_type=product_image.content_type,
        sort_order=product_image.sort_order,
        created_at=product_image.created_at
    )

async def delete_product_image(
    db: AsyncSession,
    tenant_id: str,
    product_id: str,
    image_id: str
) -> dict:
    """
    Elimina una imagen de producto de MinIO y de la BD
    """
    try:
        tenant_uuid = UUID(tenant_id)
        product_uuid = UUID(product_id)
        image_uuid = UUID(image_id)
        
        # Buscar la imagen
        query = select(ProductImage).where(
            ProductImage.id == image_uuid,
            ProductImage.product_id == product_uuid,
            ProductImage.tenant_id == tenant_uuid
        )
        result = await db.execute(query)
        image = result.scalar_one_or_none()
        
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Imagen no encontrada"
            )
        
        # Eliminar de MinIO
        minio_service.delete_file(image.file_key)
        
        # Eliminar de la base de datos
        await db.delete(image)
        await db.commit()
        
        return {"message": "Imagen eliminada exitosamente"}
        
    except Exception as e:
        await db.rollback()
        raise Exception(f"Error eliminando imagen: {str(e)}")

async def get_product_images(
    db: AsyncSession,
    tenant_id: str,
    product_id: str
) -> List[ProductImageOut]:
    """
    Obtiene todas las imágenes de un producto
    """
    try:
        tenant_uuid = UUID(tenant_id)
        product_uuid = UUID(product_id)
        
        # Verificar que el producto existe
        product_query = select(Product).where(
            Product.id == product_uuid,
            Product.tenant_id == tenant_uuid
        )
        product_result = await db.execute(product_query)
        product = product_result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Producto no encontrado"
            )
        
        # Obtener las imágenes
        images_query = select(ProductImage).where(
            ProductImage.product_id == product_uuid,
            ProductImage.tenant_id == tenant_uuid
        ).order_by(ProductImage.sort_order, ProductImage.created_at)
        
        result = await db.execute(images_query)
        images = result.scalars().all()
        
        # Generar URLs presignadas
        image_list = []
        
        for image in images:
            try:
                download_url = minio_service.get_presigned_download_url(
                    image.file_key,
                    expires=timedelta(hours=1)
                )
                
                image_list.append(ProductImageOut(
                    id=str(image.id),
                    file_key=image.file_key,
                    file_name=image.file_name,
                    file_size=image.file_size,
                    content_type=image.content_type,
                    is_primary=image.is_primary,
                    sort_order=image.sort_order,
                    url=download_url
                ))
            except Exception as e:
                logger.warning(f"Error generando URL para imagen {image.id}: {e}")
                continue
        
        return image_list
        
    except Exception as e:
        raise Exception(f"Error obteniendo imágenes: {str(e)}")

# Funciones de creación de productos

def create_product_with_variants(db: Session, data: ConfigurableProductCreate, tenant_id: UUID):
    """Crea un producto configurable con variantes"""
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
    
    # Crear el producto
    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        bar_code=data.barCode,
        price_sale=data.priceSale,
        price_base=data.priceBase,
        sell_in_negative=data.sellInNegative,
        is_configurable=True,
        brand_id=data.brand_id,
        category_id=data.category_id,
        tenant_id=tenant_id
    )
    db.add(product)
    db.flush()

    # Crear variantes
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

        # Crear stocks para cada variante
        for stock in variant_data.stocks:
            db.add(Stock(
                product_id=product.id,
                variant_id=variant.id, 
                pdv_id=stock.pdv_id, 
                quantity=stock.quantity,
                min_quantity=getattr(stock, 'min_quantity', 0),
                tenant_id=tenant_id
            ))

    # Procesar imágenes si se proporcionan
    if hasattr(data, 'images') and data.images:
        process_base64_images(product.id, data.images, tenant_id, db)

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
    """Crea un producto simple con stock"""
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
    
    # Crear el producto
    product = Product(
        name=data.name,
        sku=data.sku,
        description=data.description,
        bar_code=data.barCode,
        price_sale=data.priceSale,
        price_base=data.priceBase,
        sell_in_negative=data.sellInNegative,
        is_configurable=False,
        brand_id=data.brand_id,
        category_id=data.category_id,
        tenant_id=tenant_id
    )
    db.add(product)
    db.flush()

    # Crear variante única para producto simple
    variant = ProductVariant(
        product_id=product.id,
        sku=f"{data.sku}-default",  # SKU único para la variante
        price=data.priceSale,
        tenant_id=tenant_id
    )
    db.add(variant)
    db.flush()

    # Crear stocks
    for stock in data.stocks:
        db.add(Stock(
            product_id=product.id,
            variant_id=variant.id, 
            pdv_id=stock.pdv_id, 
            quantity=stock.quantity,
            min_quantity=getattr(stock, 'min_quantity', 0),
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

    # Procesar imágenes si se proporcionan
    if hasattr(data, 'images') and data.images:
        process_base64_images(product.id, data.images, tenant_id, db)

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

# Funciones síncronas adicionales para compatibilidad

def get_all_products(db: Session, tenant_id: UUID, **kwargs):
    """Obtiene productos de forma síncrona (para compatibilidad)"""
    query = db.query(Product) \
        .options(joinedload(Product.brand), joinedload(Product.category), joinedload(Product.variants), joinedload(Product.stocks), joinedload(Product.images)) \
        .filter(Product.tenant_id == tenant_id)
    
    # Add filters if provided
    category_id = kwargs.get('category_id')
    brand_id = kwargs.get('brand_id')
    name = kwargs.get('name')
    is_active = kwargs.get('is_active')
    limit = kwargs.get('limit', 50)
    offset = kwargs.get('offset', 0)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if name:
        query = query.filter(Product.name.ilike(f"%{name}%"))
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    
    # Obtener el total de registros para la paginación
    total = query.count()
    
    # Aplicar paginación
    products = query.offset(offset).limit(limit).all()
    
    # Convertir a formato de respuesta
    products_data = [product_to_response(product) for product in products]
    
    # Calcular metadatos de paginación
    page = (offset // limit) + 1 if limit > 0 else 1
    has_next = (offset + limit) < total
    has_prev = page > 1
    
    return {
        "data": products_data,
        "total": total,
        "page": page,
        "limit": limit,
        "hasNext": has_next,
        "hasPrev": has_prev,
        "applied_filters": {
            "category_id": str(category_id) if category_id else None,
            "brand_id": str(brand_id) if brand_id else None,
            "name": name,
            "is_active": is_active,
        },
        "counts_by_status": []  # Sin estados múltiples aquí; dejamos arreglo vacío por compatibilidad
    }

def get_product_by_id(db: Session, tenant_id: UUID, product_id: UUID):
    """Obtiene un producto por ID de forma síncrona"""
    product = db.query(Product) \
        .options(joinedload(Product.brand), joinedload(Product.category), joinedload(Product.variants), joinedload(Product.stocks), joinedload(Product.images)) \
        .filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return product_to_response(product)

def get_variants_by_product(db: Session, product_id: UUID, tenant_id: UUID):
    """Obtiene variantes de un producto"""
    # First check if product belongs to tenant
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return db.query(ProductVariant).filter(ProductVariant.product_id == product_id).all()

def get_stock_by_variant(db: Session, variant_id: UUID):
    """Obtiene stock por variante"""
    return db.query(Stock).filter(Stock.variant_id == variant_id).all()

def update_product(db: Session, tenant_id: UUID, product_id: UUID, data: dict):
    """Actualiza un producto"""
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    
    # Solo permitir actualizar campos escalares seguros
    allowed_scalar_fields = {
        "name",
        "sku",
        "description",
        "bar_code",
        "price_sale",
        "price_base",
        "sell_in_negative",
        "is_active",
        "brand_id",
        "category_id",
    }

    # Actualizar campos escalares
    for key, value in list(data.items()):
        if key in allowed_scalar_fields and hasattr(product, key):
            setattr(product, key, value)

    # Validar pertenencia de brand/category al tenant si fueron actualizados
    if "brand_id" in data and data.get("brand_id") is not None:
        brand = db.query(Brand).filter(Brand.id == data["brand_id"], Brand.tenant_id == tenant_id).first()
        if not brand:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La marca especificada no existe o no pertenece a esta empresa"
            )
        product.brand_id = brand.id

    if "category_id" in data and data.get("category_id") is not None:
        category = db.query(Category).filter(Category.id == data["category_id"], Category.tenant_id == tenant_id).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La categoría especificada no existe o no pertenece a esta empresa"
            )
        product.category_id = category.id

    # Manejo explícito de imágenes enviadas como base64
    try:
        images_value = data.get("images")
        if isinstance(images_value, list) and images_value:
            # Aceptamos lista de base64; ignorar si son URLs planas
            base64_images = [img for img in images_value if isinstance(img, str) and img.startswith("data:image/")]
            if base64_images:
                process_base64_images(product.id, base64_images, tenant_id, db)
    except Exception as e:
        # No bloquear la actualización completa por fallo de imágenes
        logger.warning(f"Fallo procesando imágenes en update_product: {e}")

    # TODO: manejar actualización de impuestos (tax_ids), stocks, etc. de forma controlada

    db.commit()
    db.refresh(product)
    # Convert to response shape used by GET endpoints
    return product_to_response(product)

def delete_product(db: Session, tenant_id: UUID, product_id: UUID):
    """Elimina un producto"""
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    db.delete(product)
    db.commit()
    return {"message": "Producto eliminado exitosamente"}