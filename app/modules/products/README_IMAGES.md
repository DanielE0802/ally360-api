# Guía de uso del CRUD de Productos con Imágenes

## Resumen de funcionalidades implementadas

### ✅ **Campo "images" agregado al CRUD**
- Los schemas `ProductCreate`, `ConfigurableProductCreate` y `SimpleProductWithStockCreate` ahora incluyen un campo `images` opcional
- Las imágenes se pueden enviar en formato base64 durante la creación del producto
- Se procesan automáticamente y se almacenan en MinIO

### ✅ **Nuevos campos por PDV**
- `min_quantity` en la tabla Stock para alertas de stock bajo
- `globalStock`: suma total del stock en todos los PDVs
- `productPdv`: array con información detallada por PDV

### ✅ **Sistema completo de imágenes**
- Almacenamiento en MinIO con URLs presignadas
- Endpoints específicos para manejo de imágenes
- Soporte para imagen principal y orden de visualización

## Ejemplos de uso

### 1. Crear producto simple con imágenes

```json
POST /products/simple
{
  "name": "iPhone 15 Pro Max",
  "sku": "IP15PM-256",
  "description": "iPhone 15 Pro Max 256GB Titanio Natural",
  "barCode": "194253440802",
  "typeProduct": "1",
  "priceSale": 1299.99,
  "priceBase": 999.99,
  "state": true,
  "sellInNegative": false,
  "brand_id": "b47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_id": "c47ac10b-58cc-4372-a567-0e02b2c3d480",
  "tax_ids": ["t47ac10b-58cc-4372-a567-0e02b2c3d481"],
  "images": [
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAhEAACAQMDBQAAAAAAAAAAAAABAgMABAUGIWGRkqGx0f/EABUBAQEAAAAAAAAAAAAAAAAAAAMF/8QAGhEAAgIDAAAAAAAAAAAAAAAAAAECEgMRkf/aAAwDAQACEQMRAD8AltJagyeH0AthI5xdrLcNM91BF5pX2HaH9bcfaSXWGaRmknyJckliyjqTzSlT54b6bk+h0R//2Q==",
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAhEAACAQMDBQAAAAAAAAAAAAABAgMABAUGIWGRkqGx0f/EABUBAQEAAAAAAAAAAAAAAAAAAAMF/8QAGhEAAgIDAAAAAAAAAAAAAAAAAAECEgMRkf/aAAwDAQACEQMRAD8AltJagyeH0AthI5xdrLcNM91BF5pX2HaH9bcfaSXWGaRmknyJckliyjqTzSlT54b6bk+h0R//2Q=="
  ],
  "stocks": [
    {
      "pdv_id": "p47ac10b-58cc-4372-a567-0e02b2c3d482",
      "quantity": 50,
      "min_quantity": 10
    },
    {
      "pdv_id": "p47ac10b-58cc-4372-a567-0e02b2c3d483",
      "quantity": 30,
      "min_quantity": 5
    }
  ]
}
```

### 2. Respuesta del producto creado

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "iPhone 15 Pro Max",
  "description": "iPhone 15 Pro Max 256GB Titanio Natural",
  "barCode": "194253440802",
  "images": [
    "https://minio.ally360.com/ally360/products/tenant-id/product-id/images/image1.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
    "https://minio.ally360.com/ally360/products/tenant-id/product-id/images/image2.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
  ],
  "typeProduct": "1",
  "taxesOption": 1,
  "sku": "IP15PM-256",
  "priceSale": 1299.99,
  "priceBase": 999.99,
  "quantityStock": 80,
  "globalStock": 80,
  "state": true,
  "sellInNegative": false,
  "category": {
    "id": "c47ac10b-58cc-4372-a567-0e02b2c3d480",
    "name": "Smartphones"
  },
  "brand": {
    "id": "b47ac10b-58cc-4372-a567-0e02b2c3d479",
    "name": "Apple"
  },
  "productPdv": [
    {
      "pdv_id": "p47ac10b-58cc-4372-a567-0e02b2c3d482",
      "pdv_name": "Sucursal Centro",
      "quantity": 50,
      "min_quantity": 10
    },
    {
      "pdv_id": "p47ac10b-58cc-4372-a567-0e02b2c3d483",
      "pdv_name": "Sucursal Norte",
      "quantity": 30,
      "min_quantity": 5
    }
  ]
}
```

### 3. Endpoints adicionales para imágenes

```bash
# Subir imagen individual
POST /products/{product_id}/images
Content-Type: multipart/form-data
- file: archivo de imagen
- is_primary: boolean (opcional)
- sort_order: integer (opcional)

# Obtener todas las imágenes de un producto
GET /products/{product_id}/images

# Eliminar una imagen específica
DELETE /products/{product_id}/images/{image_id}
```

## Validaciones implementadas

### Imágenes base64
- ✅ Formato válido: `data:image/{tipo};base64,{datos}`
- ✅ Tipos permitidos: jpeg, jpg, png, gif, webp
- ✅ Primera imagen se marca como principal automáticamente
- ✅ Orden secuencial automático (0, 1, 2...)

### Imágenes por archivo
- ✅ Tipos MIME permitidos: image/jpeg, image/jpg, image/png, image/gif, image/webp
- ✅ Tamaño máximo: 5MB
- ✅ Validación de contenido real del archivo

### Stock por PDV
- ✅ Campo `min_quantity` opcional (default: 0)
- ✅ Cálculo automático de `globalStock`
- ✅ Array `productPdv` con información detallada

## Migración necesaria

Para que funcione completamente, necesitas ejecutar:

```bash
# Generar migración
alembic revision --autogenerate -m "Add product images table and min_quantity to stocks"

# Aplicar migración  
alembic upgrade head
```

## Estructura de la base de datos

### Tabla `product_images`
- `id`: UUID (PK)
- `product_id`: UUID (FK a products)
- `file_key`: VARCHAR(500) - Key en MinIO
- `file_name`: VARCHAR(255) - Nombre original
- `file_size`: INTEGER - Tamaño en bytes
- `content_type`: VARCHAR(100) - MIME type
- `is_primary`: BOOLEAN - Si es imagen principal
- `sort_order`: INTEGER - Orden de visualización
- `tenant_id`: UUID - Multi-tenancy
- `created_at`, `updated_at`: TIMESTAMP

### Campo agregado a `stocks`
- `min_quantity`: INTEGER DEFAULT 0 - Cantidad mínima para alertas

## Flujo completo

1. **Crear producto**: Se envían imágenes base64 en el JSON
2. **Procesamiento**: Las imágenes se decodifican y suben a MinIO
3. **Almacenamiento**: Se guardan referencias en `product_images`
4. **Respuesta**: Se devuelven URLs presignadas válidas por 1 hora
5. **Consultas posteriores**: Siempre se generan URLs presignadas frescas

Este sistema asegura que las imágenes estén disponibles de forma segura y escalable.