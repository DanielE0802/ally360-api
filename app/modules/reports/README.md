# Reports Module - Ally360 ERP SaaS

> Sistema completo de reportes para análisis de ventas, compras, inventario, caja POS y estados financieros básicos.

---

## DESCRIPCIÓN GENERAL

El módulo **Reports** proporciona un sistema completo de reportes ejecutivos y operacionales dentro del ERP SaaS **Ally360**. Este módulo NO crea nuevas tablas, sino que genera consultas optimizadas sobre las tablas existentes de otros módulos.

### Funcionalidades Principales
- **Reportes de ventas**: Totales, por producto, por vendedor, por cliente
- **Reportes de compras**: Por proveedor, por categoría de producto  
- **Reportes de inventario**: Stock actual, kardex, productos con stock bajo
- **Reportes de caja POS**: Arqueo, movimientos, diferencias de caja
- **Reportes financieros**: Ingresos vs egresos, cuentas por cobrar/pagar
- **Exportación CSV**: Todos los reportes exportables a CSV
- **Filtros avanzados**: Rangos de fechas, PDV, categorías, etc.

### Casos de Uso Principales
- **Análisis de ventas**: Identificar productos más vendidos y mejores vendedores
- **Control de compras**: Monitorear gastos por proveedor y categoría
- **Gestión de inventario**: Alertas de stock bajo y seguimiento kardex
- **Control de caja**: Arqueos diarios y seguimiento de diferencias
- **Estados financieros**: Balance entre ingresos y egresos, cartera

---

## ARQUITECTURA Y DISEÑO

### Patrón Service Layer
```
[Router Layer] → [Service Layer] → [Database Models] → [Database]
     ↓               ↓                     ↓               ↓
- Endpoints     - Queries SQL      - SQLAlchemy       - PostgreSQL
- Validación    - Agregaciones     - Relationships    - Índices
- CSV Export    - Filtros          - Joins            - Constraints
- Pagination    - Cálculos         - Properties       - Views
```

### Arquitectura de Servicios
```python
# Servicio base con funcionalidades comunes
class BaseReportService:
    def __init__(db: Session, tenant_id: UUID, pdv_id: UUID)
    def _get_base_invoice_query() -> Query
    def _apply_date_filter() -> Query
    def _validate_pdv_ownership() -> bool

# Servicios especializados por categoría
class SalesReportService(BaseReportService):
    def get_sales_summary() -> Dict
    def get_sales_by_product() -> Dict
    def get_sales_by_seller() -> Dict
    def get_top_customers() -> Dict

class InventoryReportService(BaseReportService):
    def get_inventory_stock() -> Dict
    def get_kardex() -> Dict
    def get_low_stock_items() -> Dict
```

### Integración con Módulos Existentes
```python
# Usa consultas sobre tablas existentes
- invoices + invoice_line_items (ventas)
- bills + bill_line_items (compras)  
- products + stocks + inventory_movements (inventario)
- cash_registers + cash_movements (caja POS)
- payments (financieros)
- contacts (clientes/proveedores)
```

---

## ENDPOINTS API

### Resumen de Endpoints
| Categoría | Endpoint | Descripción | Exportable |
|-----------|----------|-------------|------------|
| **Ventas** | `GET /reports/sales/summary` | Resumen de ventas por período | CSV |
| | `GET /reports/sales/by-product` | Ventas agregadas por producto | CSV |
| | `GET /reports/sales/by-seller` | Ventas por vendedor con comisiones | CSV |
| | `GET /reports/sales/top-customers` | Ranking de mejores clientes | CSV |
| **Compras** | `GET /reports/purchases/by-supplier` | Compras agregadas por proveedor | CSV |
| | `GET /reports/purchases/by-category` | Compras por categoría de producto | CSV |
| **Inventario** | `GET /reports/inventory/stock` | Stock actual por producto y PDV | CSV |
| | `GET /reports/inventory/kardex` | Movimientos y saldos de producto | CSV |
| | `GET /reports/inventory/low-stock` | Productos con stock bajo | CSV |
| **Caja POS** | `GET /reports/cash-registers/summary` | Resumen de cajas y arqueos | CSV |
| | `GET /reports/cash-registers/{id}/movements` | Detalle de movimientos de caja | CSV |
| **Financieros** | `GET /reports/financial/income-vs-expenses` | Ingresos vs egresos del período | CSV |
| | `GET /reports/financial/accounts-receivable` | Cuentas por cobrar (cartera) | CSV |
| | `GET /reports/financial/accounts-payable` | Cuentas por pagar | CSV |

### GET `/reports/sales/summary` - Resumen de Ventas
```python
@router.get("/sales/summary")
async def get_sales_summary(
    start_date: date,
    end_date: date,
    customer_id: Optional[UUID] = None,
    seller_id: Optional[UUID] = None,
    pdv_id: Optional[UUID] = None,
    export: Optional[str] = None  # "csv"
):
    """
    Resumen ejecutivo de ventas para un período.
    
    - Total de ventas y monto
    - Ticket promedio
    - Conteo de facturas y ventas POS
    - Filtrable por cliente, vendedor y PDV
    """
```

**Ejemplo Response:**
```json
{
    "period_start": "2025-09-01",
    "period_end": "2025-09-30",
    "total_sales": 1250,
    "total_amount": 45750000.00,
    "average_ticket": 36600.00,
    "total_invoices": 1250,
    "total_pos_sales": 850
}
```

### GET `/reports/sales/by-product` - Ventas por Producto
```python
@router.get("/sales/by-product")
async def get_sales_by_product(
    start_date: date,
    end_date: date,
    pdv_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
    export: Optional[str] = None
):
    """
    Ranking de productos por ventas.
    
    - Cantidad vendida y monto total
    - Precio promedio y número de ventas
    - Información de categoría y marca
    - Ordenado por monto total descendente
    """
```

**Ejemplo Response:**
```json
{
    "period_start": "2025-09-01",
    "period_end": "2025-09-30",
    "products": [
        {
            "product_id": "uuid",
            "product_name": "Smartphone Samsung Galaxy",
            "product_sku": "SAM-GAL-001",
            "category_name": "Electrónicos",
            "brand_name": "Samsung",
            "quantity_sold": 45.0,
            "total_amount": 22500000.00,
            "average_price": 500000.00,
            "sales_count": 45
        }
    ],
    "total_products": 156,
    "summary": {
        "total_sales": 1250,
        "total_amount": 45750000.00
    }
}
```

### GET `/reports/inventory/kardex` - Kardex de Producto
```python
@router.get("/inventory/kardex")
async def get_kardex(
    product_id: UUID,
    pdv_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 1000,
    offset: int = 0
):
    """
    Kardex detallado de un producto específico.
    
    - Todos los movimientos de inventario
    - Saldo corrido (running balance)
    - Entradas, salidas y ajustes
    - Costos unitarios y totales
    """
```

**Ejemplo Response:**
```json
{
    "product_id": "uuid",
    "product_name": "Smartphone Samsung Galaxy",
    "product_sku": "SAM-GAL-001",
    "pdv_name": "Tienda Principal",
    "period_start": "2025-09-01",
    "period_end": "2025-09-30",
    "movements": [
        {
            "movement_date": "2025-09-01T10:00:00Z",
            "movement_type": "IN",
            "quantity": 50,
            "reference": "COMPRA-001",
            "notes": "Compra inicial",
            "running_balance": 50.0,
            "unit_cost": 450000.00,
            "total_cost": 22500000.00
        },
        {
            "movement_date": "2025-09-02T14:30:00Z", 
            "movement_type": "OUT",
            "quantity": -2,
            "reference": "VENTA-001",
            "notes": "Venta POS",
            "running_balance": 48.0,
            "unit_cost": 450000.00,
            "total_cost": 900000.00
        }
    ],
    "initial_balance": 0.0,
    "final_balance": 48.0,
    "total_in": 50.0,
    "total_out": 2.0
}
```

### GET `/reports/financial/income-vs-expenses` - Ingresos vs Egresos
```python
@router.get("/financial/income-vs-expenses")
async def get_income_vs_expenses(
    start_date: date,
    end_date: date,
    include_pending: bool = False,
    pdv_id: Optional[UUID] = None
):
    """
    Estado de resultados básico.
    
    - Total de ingresos (facturas pagadas)
    - Total de egresos (bills pagadas)
    - Ganancia neta del período
    - Desglose por método de pago
    """
```

**Ejemplo Response:**
```json
{
    "period_start": "2025-09-01",
    "period_end": "2025-09-30",
    "total_income": 45750000.00,
    "total_expenses": 28500000.00,
    "net_profit": 17250000.00,
    "paid_invoices_count": 1250,
    "paid_bills_count": 320,
    "pending_invoices_count": 45,
    "pending_bills_count": 12,
    "cash_income": 18300000.00,
    "card_income": 15450000.00,
    "transfer_income": 12000000.00,
    "other_income": 0.00
}
```

---

## SEGURIDAD Y PERMISOS

### Role-Based Access Control (RBAC)
| Operación | Owner | Admin | Accountant | Seller | Cashier | Viewer |
|-----------|-------|-------|------------|--------|---------|--------|
| **Reportes de ventas** | ✅ | ✅ | ✅ | ✅¹ | ✅¹ | ✅ |
| **Reportes de compras** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Reportes de inventario** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Reportes de caja POS** | ✅ | ✅ | ✅ | ✅¹ | ✅¹ | ✅ |
| **Reportes financieros** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅² |

**¹** Solo sus propias ventas/cajas  
**²** Solo lectura, sin detalles sensibles

### Multi-Tenant Security
```python
# Filtro automático por tenant en todos los servicios
class BaseReportService:
    def __init__(self, db: Session, tenant_id: UUID, pdv_id: UUID):
        self.tenant_id = tenant_id  # Del JWT context
        
    def _get_base_invoice_query(self):
        return self.db.query(Invoice).filter(
            Invoice.tenant_id == self.tenant_id  # Siempre incluido
        )
```

### Validaciones de Negocio
```python
# Validación de PDV ownership
def _validate_pdv_ownership(self, pdv_id: UUID) -> bool:
    pdv = self.db.query(PDV).filter(
        PDV.id == pdv_id,
        PDV.tenant_id == self.tenant_id
    ).first()
    return pdv is not None

# Filtros de fecha obligatorios para reportes grandes
if not start_date or not end_date:
    raise HTTPException(422, "Date range is required for this report")

# Límites de paginación
limit = min(limit, 1000)  # Máximo 1000 registros por página
```

---

## EXPORTACIÓN CSV

### Características de Exportación
- **Formato estándar**: UTF-8, separador coma, headers en español
- **Nombres descriptivos**: Columnas con nombres user-friendly
- **Formateo apropiado**: Decimales, fechas, booleanos legibles
- **Nombres de archivo**: Descriptivos con fechas y filtros

### Uso de Exportación CSV
```python
# Agregar parámetro export=csv a cualquier endpoint
GET /reports/sales/summary?start_date=2025-09-01&end_date=2025-09-30&export=csv

# Response será un archivo CSV con headers apropiados
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename=sales_summary_2025-09-01_2025-09-30.csv

"Fecha Inicio","Fecha Fin","Total Ventas","Monto Total","Ticket Promedio"...
"2025-09-01","2025-09-30","1250","45750000.00","36600.00"...
```

### Headers CSV Personalizados
```python
CSV_HEADERS = {
    "sales_summary": {
        "period_start": "Fecha Inicio",
        "period_end": "Fecha Fin", 
        "total_sales": "Total Ventas",
        "total_amount": "Monto Total",
        "average_ticket": "Ticket Promedio"
    },
    "sales_by_product": {
        "product_name": "Producto",
        "product_sku": "SKU",
        "quantity_sold": "Cantidad Vendida",
        "total_amount": "Monto Total"
    }
}
```

---

## PERFORMANCE Y ESCALABILIDAD

### Optimizaciones de Base de Datos
```sql
-- Índices para reportes de ventas
CREATE INDEX idx_invoices_tenant_date_status 
ON invoices(tenant_id, issue_date, status) 
WHERE status IN ('paid', 'partial');

-- Índices para reportes de inventario
CREATE INDEX idx_inventory_movements_product_date 
ON inventory_movements(tenant_id, product_id, created_at DESC);

-- Índices para reportes de caja
CREATE INDEX idx_cash_movements_register_type_created 
ON cash_movements(cash_register_id, type, created_at DESC);

-- Índices para reportes financieros
CREATE INDEX idx_payments_date_method 
ON payments(tenant_id, payment_date, method);
```

### Paginación y Límites
```python
# Paginación obligatoria para reportes grandes
def get_sales_by_product(limit: int = 100, offset: int = 0):
    # Máximo 1000 registros por request
    limit = min(limit, 1000)
    
    # Query optimizada con LIMIT/OFFSET
    query = base_query.offset(offset).limit(limit)
    
    # Count separado para pagination metadata
    total = base_query.count()
    
    return {
        "data": query.all(),
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        }
    }
```

### Optimizaciones de Consultas
```python
# Agregaciones en base de datos, no en Python
sales_summary = db.query(
    func.count(Invoice.id).label('total_sales'),
    func.sum(Invoice.total_amount).label('total_amount'),
    func.avg(Invoice.total_amount).label('average_ticket')
).filter(
    Invoice.tenant_id == tenant_id,
    Invoice.issue_date.between(start_date, end_date)
).first()

# Joins eficientes con select específicos
products_sales = db.query(
    Product.name,
    func.sum(InvoiceLineItem.quantity).label('quantity_sold'),
    func.sum(InvoiceLineItem.quantity * InvoiceLineItem.unit_price).label('total')
).join(InvoiceLineItem).join(Invoice).filter(
    Invoice.tenant_id == tenant_id
).group_by(Product.id, Product.name)
```

---

## CASOS DE USO PRINCIPALES

### 1. Análisis de Ventas Mensual
```python
# 1. Resumen ejecutivo del mes
summary = await get_sales_summary(
    start_date="2025-09-01",
    end_date="2025-09-30"
)

# 2. Productos más vendidos  
top_products = await get_sales_by_product(
    start_date="2025-09-01",
    end_date="2025-09-30",
    limit=20
)

# 3. Performance de vendedores
sellers_performance = await get_sales_by_seller(
    start_date="2025-09-01", 
    end_date="2025-09-30"
)

# 4. Mejores clientes
top_customers = await get_top_customers(
    start_date="2025-09-01",
    end_date="2025-09-30",
    limit=50
)
```

### 2. Control de Inventario Diario
```python
# 1. Stock actual con alertas
current_stock = await get_inventory_stock(
    low_stock_only=False
)

# 2. Productos en stock mínimo
low_stock_alerts = await get_low_stock_items()

# 3. Kardex de producto específico
product_kardex = await get_kardex(
    product_id="uuid-producto",
    start_date="2025-09-01",
    end_date="2025-09-30"
)
```

### 3. Arqueo Diario de Caja
```python
# 1. Resumen de cajas del día
cash_summary = await get_cash_register_summary(
    start_date="2025-09-28",
    end_date="2025-09-28"
)

# 2. Detalle de movimientos de caja específica
cash_movements = await get_cash_movements_detail(
    cash_register_id="uuid-caja"
)

# Resultados incluyen:
# - Saldo apertura vs cierre vs calculado
# - Diferencias y ajustes
# - Desglose por tipo de movimiento
# - Referencias a facturas POS
```

### 4. Estado Financiero Mensual
```python
# 1. Ingresos vs egresos del mes
pnl = await get_income_vs_expenses(
    start_date="2025-09-01",
    end_date="2025-09-30",
    include_pending=False
)

# 2. Cartera de clientes (cuentas por cobrar)
receivables = await get_accounts_receivable()

# 3. Cuentas por pagar a proveedores
payables = await get_accounts_payable()

# Análisis resultante:
# - Liquidez (efectivo vs tarjeta vs transferencia)
# - Rentabilidad (ingresos - egresos)
# - Cartera vencida vs corriente
# - Obligaciones por vencer
```

### 5. Exportación para Contabilidad
```python
# Exportar todos los reportes financieros del mes en CSV
income_csv = await get_income_vs_expenses(
    start_date="2025-09-01",
    end_date="2025-09-30",
    export="csv"
)

receivables_csv = await get_accounts_receivable(
    export="csv"
)

sales_detail_csv = await get_sales_by_product(
    start_date="2025-09-01", 
    end_date="2025-09-30",
    export="csv"
)

# Archivos listos para importar en software contable
```

---

## ROADMAP Y FUTURAS MEJORAS

### Version 1.1.0 - Q4 2025

#### Reportes Avanzados
- **Comparativos**: Mismo período año anterior, mes anterior
- **Tendencias**: Gráficos de evolución temporal
- **Forecasting**: Predicciones basadas en histórico
- **Drill-down**: Navegación desde resumen hasta detalle

#### Dashboards Interactivos  
- **Widgets configurables**: Métricas clave personalizables
- **Alertas automáticas**: Notificaciones por email/SMS
- **Programación**: Reportes automáticos por email
- **Favoritos**: Guardar configuraciones de reportes

#### Optimizaciones de Performance
- **Vistas materializadas**: Para consultas complejas frecuentes
- **Cache Redis**: Resultados de reportes por tiempo limitado
- **Queries asíncronos**: Para reportes muy grandes
- **Streaming CSV**: Exportación sin límites de memoria

### Version 1.2.0 - Q1 2026

#### Análisis Avanzado
- **Segmentación de clientes**: RFM analysis, lifetime value
- **Análisis ABC**: Productos por importancia
- **Estacionalidad**: Patrones de venta por temporada
- **Correlaciones**: Productos que se venden juntos

#### Integración Externa
- **Power BI**: Conectores para Microsoft Power BI
- **Excel Online**: Integración directa con hojas de cálculo
- **APIs terceros**: Envío automático a contadores
- **DIAN Colombia**: Reportes tributarios automáticos

#### Reportes Específicos del Sector
- **Retail**: Rotación de inventario, margin analysis
- **Restaurantes**: Costos de ingredientes, waste tracking
- **Servicios**: Utilización de recursos, billing efficiency
- **E-commerce**: Conversion rates, abandoned carts

### Version 1.3.0 - Q2 2026

#### Business Intelligence
- **Data warehouse**: ETL para análisis histórico
- **Machine learning**: Detección de anomalías, predicciones
- **Real-time analytics**: Dashboards en tiempo real
- **Mobile dashboards**: App móvil para ejecutivos

#### Colaboración y Workflow
- **Comentarios**: Anotaciones en reportes
- **Aprobaciones**: Workflow de validación de reportes
- **Distribución**: Listas de distribución automática
- **Versionado**: Historial de cambios en reportes

---


**Versión actual:** 1.0.0 (Development)  
**Próxima release:** v1.1.0 (Q4 2025)  