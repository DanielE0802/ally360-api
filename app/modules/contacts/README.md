# Módulo de Contactos - Ally360 ERP

## Descripción General

El módulo de **Contactos** es un sistema unificado para gestionar clientes y proveedores en el ERP Ally360. Reemplaza las entidades separadas de `Customer` y `Supplier`, proporcionando una solución más flexible y escalable.

## Características Principales

### 🏢 Multi-Tenant
- Todos los contactos están aislados por `company_id`
- Middleware automático de tenant resolution
- Validaciones estrictas de pertenencia empresarial

### 🇨🇴 Validaciones Fiscales Colombianas
- **NIT (Número de Identificación Tributaria)** con dígito verificador
- Función automática de cálculo de DV: `calculate_nit_dv()`
- Validación completa: `validate_nit_with_dv()`
- Soporte para diferentes tipos de documento (CC, NIT, CE, Pasaporte)
- Responsabilidades fiscales configurables

### 🔄 Flexibilidad de Tipos
- **Cliente**: Para facturación (Invoices)
- **Proveedor**: Para compras (Bills) 
- **Mixto**: Puede ser cliente Y proveedor
- Array de tipos permite combinaciones: `["client", "provider"]`

### 🗑️ Soft Delete
- Los contactos no se eliminan físicamente
- Campo `deleted_at` para auditabilidad
- Funciones `soft_delete()` y `restore()`
- Mantiene integridad referencial con facturas/compras

### 📎 Gestión de Adjuntos
- Documentos como RUT, cédula, certificados
- Integración con MinIO para almacenamiento
- Metadata completa: tamaño, tipo MIME, descripción

## Estructura del Módulo

```
app/modules/contacts/
├── __init__.py          # Exports y metadata del módulo
├── models.py            # SQLAlchemy models
├── schemas.py           # Pydantic validation schemas
├── service.py           # Lógica de negocio
├── router.py            # Endpoints REST API
├── dependencies.py      # Dependencias específicas
├── tests.py            # Pruebas unitarias
├── README.md           # Esta documentación
└── CHANGELOG.md        # Historial de cambios
```

## Modelos de Datos

### Contact
**Tabla principal:** `contacts`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `company_id` | UUID | Tenant/Empresa (FK) |
| `name` | String | Nombre del contacto |
| `type` | Array | Tipos: `["client", "provider"]` |
| `email` | String | Email de contacto |
| `phone_primary` | String | Teléfono principal |
| `phone_secondary` | String | Teléfono secundario |
| `mobile` | String | Celular |
| `id_type` | Enum | Tipo documento (CC, NIT, CE, etc.) |
| `id_number` | String | Número de documento |
| `dv` | Integer | Dígito verificador (calculado) |
| `person_type` | Enum | Persona natural/jurídica |
| `fiscal_responsibilities` | Array | Responsabilidades fiscales |
| `payment_terms_days` | Integer | Días de plazo de pago |
| `credit_limit` | Decimal | Límite de crédito |
| `seller_id` | UUID | Vendedor asignado (FK) |
| `price_list_id` | UUID | Lista de precios (FK) |
| `billing_address` | JSON | Dirección de facturación |
| `shipping_address` | JSON | Dirección de envío |
| `notes` | Text | Notas adicionales |
| `is_active` | Boolean | Estado activo/inactivo |
| `created_at` | DateTime | Fecha de creación |
| `updated_at` | DateTime | Última actualización |
| `deleted_at` | DateTime | Fecha de eliminación (soft delete) |

### ContactAttachment
**Tabla de adjuntos:** `contact_attachments`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `contact_id` | UUID | Contacto propietario (FK) |
| `company_id` | UUID | Tenant/Empresa (FK) |
| `file_url` | String | URL del archivo en MinIO |
| `file_name` | String | Nombre original del archivo |
| `file_size` | Integer | Tamaño en bytes |
| `content_type` | String | Tipo MIME |
| `description` | String | Descripción del documento |
| `uploaded_by` | UUID | Usuario que subió (FK) |
| `created_at` | DateTime | Fecha de subida |

## API Endpoints

### CRUD Principal
- `POST /contacts/` - Crear contacto
- `GET /contacts/` - Listar con filtros y paginación
- `GET /contacts/{id}` - Obtener por ID
- `PUT /contacts/{id}` - Actualizar contacto
- `DELETE /contacts/{id}` - Soft delete
- `POST /contacts/{id}/restore` - Restaurar eliminado

### Estadísticas
- `GET /contacts/stats/summary` - Estadísticas generales

### Integración con Otros Módulos
- `GET /contacts/clients/for-invoices` - Clientes para facturas
- `GET /contacts/providers/for-bills` - Proveedores para compras

### Gestión de Adjuntos
- `POST /contacts/{id}/attachments` - Subir documento
- `DELETE /contacts/attachments/{id}` - Eliminar adjunto

### Acciones Masivas
- `POST /contacts/bulk/activate` - Activar múltiples
- `POST /contacts/bulk/deactivate` - Desactivar múltiples

## Validaciones Específicas

### NIT Colombiano
```python
# Cálculo automático del dígito verificador
nit = "900123456"
dv = calculate_nit_dv(nit)  # Retorna: 8

# Validación completa
is_valid = validate_nit_with_dv("900123456", 8)  # True
```

### Responsabilidades Fiscales
Valores permitidos para Colombia:
- `"O-13"` - Gran Contribuyente
- `"O-15"` - Autorretenedor
- `"O-23"` - Agente de Retención IVA
- `"O-47"` - Régimen Simple de Tributación
- `"R-99-PN"` - Responsable del IVA

### Direcciones
Formato JSON estructurado:
```json
{
  "address": "Calle 123 #45-67",
  "city": "Bogotá",
  "state": "Cundinamarca", 
  "country": "Colombia",
  "postal_code": "110111"
}
```

## Integración con Otros Módulos

### Módulo Invoices (Facturas)
- Reemplaza endpoints `/api/v1/customers/`
- Usar `/api/v1/contacts/clients/for-invoices`
- Campo `customer_id` en facturas apunta a `contacts.id`

### Módulo Bills (Compras)
- Reemplaza endpoints `/api/v1/suppliers/`
- Usar `/api/v1/contacts/providers/for-bills`
- Campo `supplier_id` en compras apunta a `contacts.id`

### Módulo Files
- Adjuntos se almacenan en MinIO con prefijo:
- `ally360/{company_id}/contacts/{yyyy}/{mm}/{dd}/{uuid}`

## Ejemplos de Uso

### Crear Cliente
```python
contact_data = ContactCreate(
    name="Empresa ABC S.A.S",
    type=["client"],
    email="facturacion@empresa.com",
    id_type=IdType.NIT,
    id_number="900123456",
    person_type=PersonType.JURIDICA,
    fiscal_responsibilities=["O-13", "O-15"],
    payment_terms_days=30,
    credit_limit=Decimal("5000000.00"),
    billing_address={
        "address": "Calle 123 #45-67",
        "city": "Bogotá",
        "state": "Cundinamarca",
        "country": "Colombia",
        "postal_code": "110111"
    }
)
```

### Buscar Contactos
```python
# Búsqueda por texto
GET /contacts/?search=empresa&limit=20&offset=0

# Filtrar solo clientes activos
GET /contacts/?type=client&is_active=true

# Filtrar por vendedor
GET /contacts/?seller_id=uuid-del-vendedor
```

### Obtener para Facturas
```python
# Solo clientes activos para dropdown de facturas
GET /contacts/clients/for-invoices?search=empresa
```

## Consideraciones de Rendimiento

### Índices de Base de Datos
- `(company_id, id_number)` - Unique constraint
- `(company_id, deleted_at)` - Para listados activos
- `(company_id, type)` - Para filtros por tipo
- `(company_id, seller_id)` - Para filtros por vendedor

### Paginación
- Máximo 500 registros por consulta
- Usar `limit` y `offset` para paginar
- Ordenamiento por defecto: `name ASC`

### Cache (Futuro)
- Redis cache para listados frecuentes
- Invalidación automática en updates

## Migración desde Customer/Supplier

Si tienes datos existentes en tablas separadas:

1. **Crear script de migración**
2. **Mapear customers → contacts con type=["client"]**
3. **Mapear suppliers → contacts con type=["provider"]**
4. **Actualizar foreign keys en invoices/bills**
5. **Eliminar tablas obsoletas**

## Testing

### Pruebas Unitarias
```bash
pytest app/modules/contacts/tests.py -v
```

### Casos de Prueba Principales
- ✅ Creación con validación NIT
- ✅ Soft delete y restore
- ✅ Multi-tenancy isolation
- ✅ Búsqueda y filtros
- ✅ Integración con invoices/bills
- ✅ Gestión de adjuntos

## Roadmap Futuro

### v1.1
- [ ] Cache Redis para performance
- [ ] Webhooks para cambios
- [ ] Exportación masiva (Excel/CSV)

### v1.2
- [ ] Integración con CRM externo
- [ ] Scoring de clientes
- [ ] Análisis de comportamiento
