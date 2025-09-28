# Changelog - Módulo de Facturas de Venta (Invoices)

Todos los cambios notables en el módulo de Invoices serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-09-28

### 🎉 Funcionalidades Iniciales

#### Gestión de Facturas
- **Creación de facturas** con múltiples ítems
- **Estados de factura**: draft, open, partial, paid, void
- **Numeración automática** por PDV con validación de unicidad
- **Cálculo automático de totales** e impuestos
- **Validación de fechas** (due_date >= issue_date)
- **Integración con módulo Contacts** para clientes

#### Control de Inventario
- **Reducción automática de stock** al confirmar facturas (draft → open)
- **Creación de movimientos** de inventario tipo OUT
- **Validación de stock disponible** antes de confirmar
- **Referencias de factura** en movimientos de inventario

#### Gestión de Pagos
- **Pagos parciales y completos** con múltiples métodos:
  - Efectivo (cash)
  - Transferencia bancaria (transfer)
  - Tarjeta de crédito/débito (card)
  - Cheque (check)
  - Otros (other)
- **Actualización automática de estados** de factura por pagos
- **Validación de montos** de pago
- **Historial completo** de pagos por factura

#### API Endpoints
- `POST /invoices/` - Crear factura
- `GET /invoices/` - Listar facturas con filtros avanzados
- `GET /invoices/{id}` - Obtener detalles de factura
- `PATCH /invoices/{id}` - Actualizar factura (solo draft)
- `POST /invoices/{id}/confirm` - Confirmar factura
- `POST /invoices/{id}/cancel` - Anular factura
- `POST /invoices/{id}/payments` - Registrar pago
- `GET /invoices/{id}/payments` - Obtener pagos de factura
- `GET /invoices/reports/summary` - Resumen de ventas
- `GET /invoices/next-number/{pdv_id}` - Siguiente número de factura

#### Filtros y Búsquedas
- **Filtros por fecha** (start_date, end_date)
- **Filtro por cliente** (customer_id)
- **Filtro por PDV** (pdv_id)
- **Filtro por estado** (status)
- **Búsqueda por texto** en número de factura y notas

#### Seguridad
- **Multi-tenancy** completo con tenant_id
- **Control de acceso basado en roles**:
  - owner: Todos los permisos
  - admin: Todos los permisos
  - seller: Crear, actualizar, confirmar facturas
  - accountant: Ver facturas, registrar pagos
  - viewer: Solo lectura
- **Validación de pertenencia** de entidades al tenant
- **Auditoría completa** con created_by y timestamps

#### Validaciones de Negocio
- Productos y PDVs deben pertenecer al tenant
- Clientes validados como Contacts con tipo 'client'
- Stock suficiente antes de confirmar facturas
- Pagos no pueden ser negativos ni exceder saldo
- Solo facturas draft se pueden editar
- Estados controlados con transiciones válidas

### 🔧 Integraciones

#### Módulo de Contacts
- **Clientes unificados** usando Contact con type='client'
- **Validación automática** de tipo de contacto
- **Términos de pago** heredados del cliente

#### Módulo de Inventario
- **Reducción automática de stock** al confirmar facturas
- **Movimientos de inventario** tipo OUT con referencia
- **Validación de disponibilidad** antes de confirmar

#### Módulo de Taxes
- **Cálculo automático** de impuestos por producto
- **Integración con legislación colombiana** DIAN
- **Impuestos por línea** y totales

#### Módulo de Products
- **Validación de productos** activos y del tenant
- **Precios de referencia** para líneas de factura
- **Información de impuestos** por producto

#### Módulo de PDV
- **Numeración secuencial** por punto de venta
- **Validación de PDV activo** y configurado
- **Resoluciones DIAN** por PDV (futuro)

### 📊 Reportes y Analytics

#### Resumen de Ventas
- **Totales por período** con filtros por PDV
- **Análisis de estados** de facturas
- **Métricas de impuestos** calculados
- **Conteo de facturas** por estado

### 🏗️ Arquitectura

#### Patrones de Diseño
- **Repository Pattern** en InvoiceService
- **Command Pattern** para operaciones complejas
- **Observer Pattern** para actualizaciones de estado
- **Strategy Pattern** para métodos de pago

#### Base de Datos
- **Modelo relacional** con foreign keys
- **Índices optimizados** para consultas frecuentes
- **Constraints de integridad** referencial
- **Soft delete** con timestamps

#### Performance
- **Paginación obligatoria** en listados
- **Eager loading** para relaciones frecuentes
- **Transacciones atómicas** para operaciones críticas
- **Índices compuestos** en campos de filtro

### 📋 Limitaciones Conocidas

#### Funcionalidades Pendientes
- Generación de PDF (placeholder implementado)
- Envío por email (placeholder implementado)
- Reversión de inventario al anular
- Descuentos por línea
- Facturas recurrentes

#### Consideraciones Técnicas
- Los PDFs requieren implementación de plantillas
- El envío de email requiere configuración de Celery
- La reversión de inventario requiere análisis de casos edge
- Los descuentos necesitan reestructuración de cálculos

### 🧪 Testing

#### Casos de Prueba Implementados
- Creación de facturas en diferentes estados
- Validación de multi-tenancy
- Integración con inventario
- Gestión de pagos parciales y completos
- Filtros y búsquedas
- Control de acceso por roles

### 📝 Notas Técnicas

#### Migration Files
- `001_create_invoices_table.py` - Tabla principal de facturas
- `002_create_invoice_line_items_table.py` - Ítems de factura
- `003_create_payments_table.py` - Tabla de pagos
- `004_add_indexes.py` - Índices de performance

#### Configuración
- Límites de paginación: 1-1000 registros
- Precisión decimal: 2 decimales para montos
- Encoding: UTF-8 para caracteres especiales
- Timezone: UTC con conversión local

---

## Planificación de Versiones Futuras

### [1.1.0] - Estimado: Q4 2025
- Generación de PDF con plantillas
- Envío de facturas por email
- Reversión de inventario al anular
- Descuentos por línea y globales

### [1.2.0] - Estimado: Q1 2026
- Facturas recurrentes
- Cotizaciones → Facturas
- Notas crédito
- Integración con pasarelas de pago

### [1.3.0] - Estimado: Q2 2026
- Facturación electrónica DIAN
- Múltiples monedas
- Dashboard avanzado
- Plantillas de email

---

*Changelog mantenido por: Equipo de Desarrollo Ally360*  
*Última actualización: 28 de Septiembre, 2025*