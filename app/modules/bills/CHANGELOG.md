# Changelog - Módulo de Gastos (Bills)

Todos los cambios notables en este módulo serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Implementación completa de DebitNoteService
- Endpoints de anulación para Bills y PurchaseOrders
- Sistema de adjuntos para facturas
- Reportes avanzados de compras
- Integración con módulo de contabilidad

## [1.0.0] - 2025-09-28

### Added - Implementación Inicial

#### 🏗️ Modelos de Datos
- **Supplier**: Gestión de proveedores con validación de documentos únicos
- **PurchaseOrder**: Órdenes de compra con estados controlados
- **POItem**: Ítems de órdenes de compra con cálculos automáticos
- **Bill**: Facturas de proveedor con integración de inventario
- **BillLineItem**: Líneas de factura con impuestos calculados
- **BillPayment**: Pagos con control automático de estados
- **DebitNote**: Notas débito con diferentes tipos de ajuste
- **DebitNoteItem**: Ítems de notas débito con razones específicas

#### 📋 Esquemas Pydantic
- Validación completa para todas las entidades
- Esquemas de creación, actualización y respuesta
- Validaciones de negocio específicas (fechas, montos, estados)
- Esquemas para conversión de órdenes a facturas

#### 🚀 Servicios de Negocio
- **SupplierService**: CRUD completo con búsqueda y validaciones
- **PurchaseOrderService**: Gestión de órdenes con conversión a facturas
- **BillService**: Facturas con integración automática de inventario
- **BillPaymentService**: Pagos con actualización automática de estados

#### 🌐 API Endpoints
- **Suppliers**: CRUD completo (`/suppliers`)
- **Purchase Orders**: Gestión y conversión (`/purchase-orders`)
- **Bills**: Facturas con pagos (`/bills`)
- **Bill Payments**: Gestión de pagos (`/bill-payments`)
- **Debit Notes**: Placeholders para notas débito (`/debit-notes`)

#### 🔧 Integraciones
- **Inventario**: Actualización automática de stock al confirmar facturas
- **Taxes**: Cálculo de impuestos por línea (preparado)
- **Auth**: Validación de roles y context multi-tenant
- **PDV**: Validación de pertenencia por empresa

#### 🔒 Seguridad
- Arquitectura multi-tenant con `company_id` en todas las tablas
- Control de acceso basado en roles (owner, admin, seller, accountant, viewer)
- Validación de pertenencia de entidades relacionadas
- Auditoría con `created_by` y timestamps

#### 📊 Funcionalidades Clave
- **Estados automáticos**: Facturas cambian de estado según pagos
- **Integración de inventario**: Bills open incrementan stock automáticamente
- **Conversión PO→Bill**: Un clic para convertir órdenes en facturas
- **Pagos parciales**: Control automático de saldos y estados
- **Búsqueda avanzada**: Filtros por múltiples criterios

### Technical Details

#### Database Schema
```sql
-- 8 nuevas tablas creadas:
- suppliers (proveedores)
- purchase_orders (órdenes de compra)  
- po_items (ítems de órdenes)
- bills (facturas de proveedor)
- bill_line_items (ítems de facturas)
- bill_payments (pagos)
- debit_notes (notas débito)
- debit_note_items (ítems de notas débito)
```

#### API Coverage
- **27 endpoints** definidos
- **5 entidades principales** con CRUD
- **Filtros avanzados** en listados
- **Paginación obligatoria** en todas las listas

#### Business Logic
- **5 estados de PurchaseOrder**: draft, sent, approved, closed, void
- **5 estados de Bill**: draft, open, paid, partial, void
- **4 métodos de pago**: cash, transfer, card, other
- **3 tipos de DebitNote**: price_adjustment, quantity_adjustment, service

### Known Limitations

#### MVP Constraints
- **Anulaciones**: No revierten inventario automáticamente
- **Impuestos**: Cálculo preparado pero no implementado completamente
- **Adjuntos**: Sistema preparado pero no implementado
- **Reportes**: Solo endpoints básicos de listado

#### Performance Considerations
- Índices optimizados para queries multi-tenant
- Paginación por defecto: 100 elementos máximo
- Transacciones atómicas para operaciones críticas

### Migration Required
```bash
# Crear migración para nuevas tablas:
alembic revision --autogenerate -m "Add bills module tables"
alembic upgrade head
```

### Configuration Changes
```python
# Agregar en main.py:
from app.modules.bills.router import bills_router
app.include_router(bills_router, tags=["Bills"])

# Importar modelos:
import app.modules.bills.models
```

*Mantenido por el equipo de desarrollo Ally360*