# CHANGELOG - Reports Module

Todos los cambios notables del **módulo Reports** serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere al [Versionado Semántico](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Próximas Funcionalidades

### Planned
- Reportes comparativos (mismo período año anterior)
- Dashboards interactivos con widgets configurables
- Alertas automáticas por email para métricas críticas
- Vistas materializadas para optimización de performance
- Integración con Power BI y Excel Online
- Análisis ABC de productos y segmentación RFM de clientes

---

## [1.0.0] - 2025-09-28 - Initial Release

### Added - Funcionalidades Nuevas

#### Reportes de Ventas
- **Resumen de ventas**: Total de ventas, monto, ticket promedio por período
- **Ventas por producto**: Ranking de productos más vendidos con categoría y marca
- **Ventas por vendedor**: Performance de vendedores con cálculo de comisiones
- **Top clientes**: Ranking de mejores clientes por monto de compras
- **Filtros avanzados**: Por fecha, cliente, vendedor, PDV
- **Exportación CSV**: Todos los reportes exportables con headers en español

#### Reportes de Compras
- **Compras por proveedor**: Ranking de proveedores por monto de compras
- **Compras por categoría**: Análisis de gastos por categoría de producto
- **Estadísticas agregadas**: Total de facturas, monto promedio, última compra
- **Filtros por período**: Rango de fechas configurable
- **Información de contacto**: Email y teléfono de proveedores incluidos

#### Reportes de Inventario
- **Stock actual**: Estado actual de inventario por producto y PDV
- **Kardex detallado**: Movimientos de inventario con saldo corrido
- **Alertas de stock bajo**: Productos por debajo del mínimo configurado
- **Filtros por categoría/marca**: Segmentación de productos
- **Costos unitarios**: Tracking de costos en movimientos de inventario
- **Última actividad**: Fecha del último movimiento por producto

#### Reportes de Caja POS
- **Resumen de cajas**: Arqueos con saldos de apertura, cierre y calculado
- **Detalle de movimientos**: Todos los movimientos de caja específica
- **Cálculo de diferencias**: Diferencias entre saldo declarado y calculado
- **Desglose por tipo**: Ventas, depósitos, retiros, gastos, ajustes
- **Referencias cruzadas**: Link con facturas POS para movimientos de venta
- **Información de usuarios**: Quién abrió/cerró cada caja

#### Reportes Financieros
- **Ingresos vs egresos**: Estado de resultados básico por período
- **Cuentas por cobrar**: Cartera de clientes con aging de vencimientos
- **Cuentas por pagar**: Obligaciones con proveedores y fechas de vencimiento
- **Desglose por método de pago**: Efectivo, tarjeta, transferencia, otros
- **Indicadores de liquidez**: Análisis de flujo de caja
- **Alertas de vencimiento**: Identificación de facturas/bills vencidas

#### Arquitectura y Diseño Técnico
- **Service Layer Pattern**: Separación clara entre routers, servicios y modelos
- **BaseReportService**: Clase base con funcionalidades comunes multi-tenant
- **Consultas optimizadas**: Agregaciones en base de datos, no en aplicación
- **Índices específicos**: Optimización para consultas de reportes frecuentes
- **Paginación eficiente**: Limit/offset con metadata de paginación
- **Multi-tenant security**: Filtrado automático por tenant_id en todas las consultas

#### Sistema de Exportación CSV
- **Formato estándar**: UTF-8, separador coma, headers en español
- **Nombres descriptivos**: Mapeo de campos técnicos a nombres user-friendly
- **Formateo apropiado**: Decimales, fechas y booleanos legibles
- **Nombres de archivo**: Descriptivos con fechas y contexto del reporte
- **Headers personalizados**: Configuración específica por tipo de reporte
- **Manejo de caracteres especiales**: Escape correcto de comas y comillas

#### Validaciones y Seguridad
- **RBAC implementado**: Control de acceso por roles (Owner, Admin, Accountant, etc.)
- **Filtros de seguridad**: Sellers/Cashiers solo ven sus propios datos
- **Validación de PDV ownership**: Verificación de pertenencia a tenant
- **Rangos de fecha obligatorios**: Prevención de consultas sin límites
- **Límites de paginación**: Máximo 1000 registros por request
- **Validación de parámetros**: Sanitización de inputs con Pydantic

#### Performance y Escalabilidad
- **Consultas agregadas**: Uso de SQL func.sum(), func.count(), func.avg()
- **Joins optimizados**: LEFT JOIN solo cuando necesario
- **Índices compuestos**: Optimización para filtros multi-tenant con fechas
- **Lazy loading**: Cálculos bajo demanda con cache en memoria
- **Query planning**: Consultas diseñadas para uso eficiente de índices
- **Memory management**: Paginación obligatoria para datasets grandes

### Technical Implementation Details

#### Módulos Integrados
- **Invoices + InvoiceLineItems**: Base para reportes de ventas
- **Bills + BillLineItems**: Base para reportes de compras
- **Products + Stocks + InventoryMovements**: Base para reportes de inventario
- **CashRegisters + CashMovements**: Base para reportes de caja POS
- **Payments**: Base para análisis financieros por método de pago
- **Contacts**: Información de clientes y proveedores
- **Auth + Users**: Control de acceso y auditoría

#### Esquemas Pydantic
- **Request schemas**: Validación de filtros y parámetros de entrada
- **Response schemas**: Estructuras tipadas para todas las respuestas
- **Pagination schemas**: Metadata estándar de paginación
- **Export schemas**: Parámetros para exportación CSV
- **Filter schemas**: Validaciones específicas por tipo de reporte
- **Date validation**: Validación de rangos de fechas lógicos

#### Estructura de Servicios
```python
# Jerarquía de servicios implementada
BaseReportService
├── SalesReportService
├── PurchaseReportService  
├── InventoryReportService
├── CashRegisterReportService
└── FinancialReportService

# Routers por categoría
/reports/sales/*
/reports/purchases/*
/reports/inventory/*
/reports/cash-registers/*
/reports/financial/*
```

#### Utilidades Implementadas
- **CSV generation**: Creación de archivos CSV con encoding correcto
- **Data formatting**: Formateo de decimales, fechas y booleanos
- **Header mapping**: Traducción de campos técnicos a nombres de usuario
- **File naming**: Generación automática de nombres descriptivos
- **Response handling**: Manejo de responses HTTP vs CSV apropiadamente

### Database Impact

#### Sin Nuevas Tablas
```sql
-- Este módulo NO crea nuevas tablas
-- Utiliza consultas sobre tablas existentes:

-- Para reportes de ventas
SELECT ... FROM invoices i
JOIN invoice_line_items ili ON i.id = ili.invoice_id
JOIN products p ON ili.product_id = p.id
WHERE i.tenant_id = ? AND i.issue_date BETWEEN ? AND ?

-- Para reportes de inventario  
SELECT ... FROM stocks s
JOIN products p ON s.product_id = p.id
JOIN inventory_movements im ON s.product_id = im.product_id
WHERE s.tenant_id = ? AND s.pdv_id = ?

-- Para reportes financieros
SELECT ... FROM payments pay
JOIN invoices i ON pay.invoice_id = i.id
WHERE i.tenant_id = ? AND pay.payment_date BETWEEN ? AND ?
```

#### Índices Requeridos para Performance
```sql
-- Índices críticos para reportes eficientes
CREATE INDEX idx_invoices_tenant_date_status 
ON invoices(tenant_id, issue_date, status) 
WHERE status IN ('paid', 'partial');

CREATE INDEX idx_bills_tenant_date_status 
ON bills(tenant_id, issue_date, status) 
WHERE status IN ('paid', 'partial');

CREATE INDEX idx_inventory_movements_product_date 
ON inventory_movements(tenant_id, product_id, created_at DESC);

CREATE INDEX idx_cash_movements_register_type_created 
ON cash_movements(cash_register_id, type, created_at DESC);

CREATE INDEX idx_payments_tenant_date_method 
ON payments(tenant_id, payment_date, method);

CREATE INDEX idx_stocks_tenant_pdv_product 
ON stocks(tenant_id, pdv_id, product_id) 
WHERE quantity > 0;
```

### API Endpoints Implementados

#### Sales Reports (5 endpoints)
- `GET /reports/sales/summary` - Resumen ejecutivo de ventas
- `GET /reports/sales/by-product` - Ranking de productos más vendidos  
- `GET /reports/sales/by-seller` - Performance de vendedores
- `GET /reports/sales/top-customers` - Mejores clientes por monto

#### Purchase Reports (2 endpoints)
- `GET /reports/purchases/by-supplier` - Compras agregadas por proveedor
- `GET /reports/purchases/by-category` - Compras por categoría

#### Inventory Reports (3 endpoints)
- `GET /reports/inventory/stock` - Stock actual con alertas
- `GET /reports/inventory/kardex` - Kardex detallado por producto
- `GET /reports/inventory/low-stock` - Productos con stock bajo

#### Cash Register Reports (2 endpoints)
- `GET /reports/cash-registers/summary` - Resumen de arqueos
- `GET /reports/cash-registers/{id}/movements` - Detalle de movimientos

#### Financial Reports (3 endpoints)
- `GET /reports/financial/income-vs-expenses` - Estado de resultados
- `GET /reports/financial/accounts-receivable` - Cuentas por cobrar
- `GET /reports/financial/accounts-payable` - Cuentas por pagar

### Quality Assurance

#### Testing Strategy Implementada
- **Unit tests**: Servicios de reportes con datos mockeados
- **Integration tests**: Endpoints completos con base de datos de prueba
- **Multi-tenant tests**: Verificación de aislamiento de datos
- **Performance tests**: Reportes con datasets grandes (10k+ registros)
- **CSV export tests**: Validación de formato y caracteres especiales
- **Security tests**: Intentos de acceso cruzado entre tenants

#### Error Handling
- **Validation errors**: HTTP 422 con detalles específicos
- **Authorization errors**: HTTP 403 para permisos insuficientes
- **Not found errors**: HTTP 404 para recursos inexistentes
- **Server errors**: HTTP 500 con logging detallado
- **Timeout handling**: Límites de tiempo para consultas complejas
- **Memory limits**: Protección contra consultas que consumen mucha memoria

#### Logging y Monitoreo
- **Query logging**: Log de consultas SQL generadas para debugging
- **Performance metrics**: Tiempo de respuesta por tipo de reporte
- **Usage analytics**: Qué reportes se usan más frecuentemente
- **Error tracking**: Errores categorizados por tipo y frecuencia
- **Export tracking**: Estadísticas de uso de exportación CSV

---

## [0.0.0] - 2025-09-27 - Planning Phase

### Research
- **Análisis de requerimientos**: Definición de tipos de reportes necesarios
- **Estudio de performance**: Identificación de consultas complejas críticas
- **Diseño de arquitectura**: Service layer pattern para reportes
- **Análisis de seguridad**: Multi-tenancy y control de acceso por roles
- **Benchmarking**: Tiempos de respuesta objetivo para diferentes volúmenes

### Planning
- **API Design**: Estructura REST para diferentes categorías de reportes
- **Database optimization**: Estrategia de índices para consultas eficientes
- **CSV Export strategy**: Formato y naming conventions para archivos
- **Pagination strategy**: Límites y metadata para reportes grandes
- **Integration points**: Conexión con módulos existentes del ERP

---

## Future Roadmap

### v1.1.0 - Advanced Analytics (Q4 2025)
- Reportes comparativos con períodos anteriores
- Dashboards interactivos con métricas en tiempo real
- Alertas automáticas configurables por usuario
- Programación de reportes por email
- Gráficos y visualizaciones básicas

### v1.2.0 - Business Intelligence (Q1 2026)
- Análisis ABC de productos por rentabilidad
- Segmentación RFM de clientes
- Forecasting básico basado en tendencias históricas
- Integración con Power BI y Tableau
- Data warehouse para análisis histórico profundo

### v1.3.0 - Advanced Features (Q2 2026)
- Machine learning para detección de anomalías
- Análisis de correlación entre productos
- Optimización automática de inventario
- Reportes específicos por sector (retail, servicios, etc.)
- API webhooks para integración con sistemas externos

### v2.0.0 - Enterprise Features (Q3 2026)
- Multi-currency support en reportes
- Consolidación multi-empresa para grupos empresariales
- Advanced drill-down capabilities
- Custom report builder con drag & drop
- Mobile-first dashboards para ejecutivos

---


**Last Updated**: 28 Septiembre 2025
**Current Version**: 1.0.0
**License**: Proprietary - Ally360 SaaS