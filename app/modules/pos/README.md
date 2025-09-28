# 🏪 POS Module - Ally360 ERP SaaS

> **Sistema completo de Punto de Venta** con gestión de cajas, vendedores y ventas integradas con inventario y pagos.

---

## 🎯 **DESCRIPCIÓN GENERAL**

El módulo **POS (Point of Sale)** proporciona un sistema completo de punto de venta dentro del ERP SaaS **Ally360**. Implementa:

- **🏦 Cajas registradoras**: Apertura/cierre con arqueo automático
- **💰 Movimientos de caja**: Control completo de efectivo
- **👥 Vendedores**: Gestión de personal de ventas
- **🛒 Ventas POS**: Integración completa con inventario y pagos
- **📊 Control de turnos**: Seguimiento por vendedor y caja

### **Casos de Uso Principales**
- **Ventas directas**: Proceso completo de venta en punto físico
- **Control de efectivo**: Arqueo y diferencias de caja
- **Gestión de vendedores**: Comisiones y performance de ventas
- **Integración ERP**: Sincronización automática con inventario y contabilidad

---

## 🏗️ **ARQUITECTURA Y DISEÑO**

### **🔧 Patrón Service Layer**
```
[Router Layer] → [Service Layer] → [Models Layer] → [Database]
     ↓               ↓                ↓               ↓
- Endpoints     - Lógica de      - SQLAlchemy    - PostgreSQL
- Validación      negocio         models          tablas
- Auth/RBAC     - Transacciones  - Relationships - Índices
- HTTP codes    - Integración    - Properties    - Constraints
```

### **🎭 Service Classes Architecture**
```python
# Gestión de cajas registradoras
class CashRegisterService:
    def open_cash_register() -> CashRegister
    def close_cash_register() -> CashRegister
    def get_cash_registers() -> List[CashRegister]

# Movimientos de efectivo
class CashMovementService:
    def create_movement() -> CashMovement
    def get_movements() -> List[CashMovement]

# Gestión de vendedores
class SellerService:
    def create_seller() -> Seller
    def update_seller() -> Seller
    def get_sellers() -> List[Seller]

# Ventas POS integradas
class POSInvoiceService:
    def create_pos_sale() -> Invoice
    def get_pos_sales() -> List[Invoice]
```

### **⚡ Integración con Módulos Existentes**
```python
# Invoices: Extensión con type=POS
Invoice.type = Enum["SALE", "POS"]
Invoice.seller_id = FK(sellers.id)

# Inventory: Descuento automático
stock.quantity -= sale_item.quantity
InventoryMovement(type="OUT", reference="POS-001")

# Payments: Pagos obligatorios
Payment(invoice_id, amount, method="CASH")
CashMovement(type="SALE", amount, cash_register_id)
```

---

## 📊 **MODELO DE DATOS**

### **🏦 Tabla: `cash_registers`**
```sql
CREATE TABLE cash_registers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,                    -- Multi-tenant isolation
    pdv_id UUID NOT NULL REFERENCES pdvs(id),   -- PDV asociado
    name VARCHAR(100) NOT NULL,                  -- Nombre de la caja
    status VARCHAR(20) NOT NULL DEFAULT 'closed', -- open/closed
    opening_balance DECIMAL(15,2) NOT NULL DEFAULT 0,
    closing_balance DECIMAL(15,2),               -- Solo al cerrar
    opened_by UUID NOT NULL REFERENCES users(id),
    closed_by UUID REFERENCES users(id),
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    opening_notes TEXT,
    closing_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT uq_cash_register_tenant_pdv_name UNIQUE (tenant_id, pdv_id, name)
);
```

### **💰 Tabla: `cash_movements`**
```sql
CREATE TABLE cash_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,                    -- Multi-tenant isolation
    cash_register_id UUID NOT NULL REFERENCES cash_registers(id),
    type VARCHAR(20) NOT NULL,                   -- sale/deposit/withdrawal/expense/adjustment
    amount DECIMAL(15,2) NOT NULL,               -- Siempre valor absoluto
    reference VARCHAR(100),                      -- Referencia opcional
    notes TEXT,                                  -- Notas del movimiento
    invoice_id UUID REFERENCES invoices(id),     -- Solo para type=SALE
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### **👥 Tabla: `sellers`**
```sql
CREATE TABLE sellers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,                    -- Multi-tenant isolation
    name VARCHAR(200) NOT NULL,                  -- Nombre completo
    email VARCHAR(100),                          -- Email único
    phone VARCHAR(50),                           -- Teléfono
    document VARCHAR(50),                        -- Documento único
    is_active BOOLEAN NOT NULL DEFAULT true,
    commission_rate DECIMAL(5,4),                -- Tasa de comisión (0.05 = 5%)
    base_salary DECIMAL(15,2),                   -- Salario base
    notes TEXT,                                  -- Notas adicionales
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,                        -- Soft delete
    
    -- Constraints
    CONSTRAINT uq_seller_tenant_email UNIQUE (tenant_id, email),
    CONSTRAINT uq_seller_tenant_document UNIQUE (tenant_id, document)
);
```

### **🧾 Extensión de `invoices`**
```sql
-- Agregar campos POS a tabla existente
ALTER TABLE invoices 
ADD COLUMN seller_id UUID REFERENCES sellers(id);

-- Modificar enum type
ALTER TYPE invoicetype ADD VALUE 'pos';
```

### **🔍 Índices Optimizados**
```sql
-- Performance indexes para POS
CREATE INDEX idx_cash_registers_tenant_pdv_status ON cash_registers(tenant_id, pdv_id, status);
CREATE INDEX idx_cash_movements_register_type ON cash_movements(cash_register_id, type);
CREATE INDEX idx_cash_movements_created_at ON cash_movements(tenant_id, created_at DESC);
CREATE INDEX idx_sellers_tenant_active ON sellers(tenant_id, is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_invoices_pos_seller ON invoices(tenant_id, seller_id) WHERE type = 'pos';
```

---

## 📝 **ESQUEMAS PYDANTIC**

### **🏦 CashRegister Schemas**
```python
class CashRegisterOpen(BaseModel):
    opening_balance: Decimal = Field(ge=0, description="Saldo inicial")
    opening_notes: Optional[str] = Field(None, max_length=500)

class CashRegisterClose(BaseModel):
    closing_balance: Decimal = Field(ge=0, description="Saldo final declarado")
    closing_notes: Optional[str] = Field(None, max_length=500)

class CashRegisterOut(BaseModel):
    id: UUID
    pdv_id: UUID
    name: str
    status: CashRegisterStatus
    opening_balance: Decimal
    closing_balance: Optional[Decimal]
    opened_by: UUID
    closed_by: Optional[UUID]
    opened_at: datetime
    closed_at: Optional[datetime]
    # Propiedades calculadas
    calculated_balance: Decimal
    difference: Optional[Decimal]
```

### **💰 CashMovement Schemas**
```python
class CashMovementCreate(BaseModel):
    cash_register_id: UUID
    type: MovementType = Field(description="sale/deposit/withdrawal/expense/adjustment")
    amount: Decimal = Field(gt=0, description="Monto (siempre positivo)")
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)

class CashMovementOut(BaseModel):
    id: UUID
    cash_register_id: UUID
    type: MovementType
    amount: Decimal
    signed_amount: Decimal  # Con signo según tipo
    reference: Optional[str]
    notes: Optional[str]
    invoice_id: Optional[UUID]
    created_by: UUID
    created_at: datetime
```

### **👥 Seller Schemas**
```python
class SellerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    document: Optional[str] = Field(None, max_length=50)
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    base_salary: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=500)

class SellerOut(BaseModel):
    id: UUID
    name: str
    email: Optional[str]
    phone: Optional[str]
    document: Optional[str]
    is_active: bool
    commission_rate: Optional[Decimal]
    base_salary: Optional[Decimal]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
```

### **🛒 POS Invoice Schemas**
```python
class POSLineItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Optional[Decimal] = Field(None, gt=0)  # Del producto si no se especifica

class POSPaymentCreate(BaseModel):
    method: PaymentMethod = Field(description="cash/transfer/card/other")
    amount: Decimal = Field(gt=0)
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=200)

class POSInvoiceCreate(BaseModel):
    customer_id: UUID
    seller_id: UUID
    items: List[POSLineItemCreate] = Field(min_length=1)
    payments: List[POSPaymentCreate] = Field(min_length=1)
    notes: Optional[str] = Field(None, max_length=500)
    
    @field_validator('payments')
    def validate_payments_cover_total(cls, v):
        if not v:
            raise ValueError('Debe incluir al menos un pago')
        return v
```

---

## 🛣️ **ENDPOINTS API**

### **📋 Resumen de Endpoints**
| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| `POST` | `/cash-registers/open` | Abrir caja | Owner, Admin, Seller, Cashier |
| `POST` | `/cash-registers/{id}/close` | Cerrar caja | Owner, Admin, Seller, Cashier |
| `GET` | `/cash-registers` | Listar cajas | Todos (según rol) |
| `GET` | `/cash-registers/{id}` | Detalle de caja | Todos (según rol) |
| `POST` | `/cash-movements` | Crear movimiento | Owner, Admin, Seller, Cashier |
| `GET` | `/cash-movements` | Listar movimientos | Todos (según rol) |
| `POST` | `/sellers` | Crear vendedor | Owner, Admin |
| `GET` | `/sellers` | Listar vendedores | Todos |
| `PATCH` | `/sellers/{id}` | Actualizar vendedor | Owner, Admin |
| `DELETE` | `/sellers/{id}` | Desactivar vendedor | Owner, Admin |
| `POST` | `/pos/sales` | Crear venta POS | Owner, Admin, Seller, Cashier |
| `GET` | `/pos/sales` | Listar ventas POS | Todos (según rol) |

### **🏦 POST `/cash-registers/open` - Abrir Caja**
```python
@router.post("/cash-registers/open", response_model=CashRegisterOut)
async def open_cash_register(
    register_data: CashRegisterOpen,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db)
):
    """
    Abrir caja registradora en el PDV del contexto JWT.
    
    - Valida que no hay otra caja abierta en el PDV
    - Genera nombre automático por fecha
    - Registra usuario y hora de apertura
    - Establece saldo inicial
    """
```

**Ejemplo Request:**
```json
{
    "opening_balance": 100000.00,
    "opening_notes": "Apertura de caja turno mañana"
}
```

**Ejemplo Response (201):**
```json
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "pdv_id": "123e4567-e89b-12d3-a456-426614174001",
    "name": "Caja Principal - 20250928",
    "status": "open",
    "opening_balance": 100000.00,
    "closing_balance": null,
    "opened_by": "123e4567-e89b-12d3-a456-426614174002",
    "closed_by": null,
    "opened_at": "2025-09-28T08:00:00Z",
    "closed_at": null,
    "opening_notes": "Apertura de caja turno mañana",
    "calculated_balance": 100000.00,
    "difference": null
}
```

### **💰 POST `/cash-movements` - Registrar Movimiento**
```python
@router.post("/cash-movements", response_model=CashMovementOut)
async def create_cash_movement(
    movement_data: CashMovementCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db)
):
    """
    Registrar movimiento manual de caja.
    
    Tipos de movimiento:
    - DEPOSIT: Ingreso manual de efectivo
    - WITHDRAWAL: Retiro manual de efectivo
    - EXPENSE: Gasto pagado desde caja
    - ADJUSTMENT: Ajuste por diferencias
    
    Nota: SALE se genera automáticamente con ventas POS
    """
```

**Ejemplo Request:**
```json
{
    "cash_register_id": "123e4567-e89b-12d3-a456-426614174000",
    "type": "expense",
    "amount": 15000.00,
    "reference": "FACT-001",
    "notes": "Pago de servicios públicos"
}
```

### **🛒 POST `/pos/sales` - Crear Venta POS**
```python
@router.post("/pos/sales", response_model=POSInvoiceOut)
async def create_pos_sale(
    sale_data: POSInvoiceCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db)
):
    """
    Crear venta POS completa con proceso automático:
    
    1. Valida caja abierta obligatoria
    2. Crea factura type=POS con seller_id
    3. Descuenta stock automáticamente
    4. Registra pagos obligatorios
    5. Genera movimientos de caja
    6. Maneja vuelto si aplica
    """
```

**Ejemplo Request:**
```json
{
    "customer_id": "123e4567-e89b-12d3-a456-426614174003",
    "seller_id": "123e4567-e89b-12d3-a456-426614174004",
    "items": [
        {
            "product_id": "123e4567-e89b-12d3-a456-426614174005",
            "quantity": 2,
            "unit_price": 25000.00
        }
    ],
    "payments": [
        {
            "method": "cash",
            "amount": 50000.00,
            "reference": "EFECTIVO",
            "notes": "Pago en efectivo"
        }
    ],
    "notes": "Venta mostrador"
}
```

---

## 🛡️ **SEGURIDAD Y PERMISOS**

### **🔐 Role-Based Access Control (RBAC)**
| Operación | Owner | Admin | Seller | Cashier | Accountant | Viewer |
|-----------|-------|-------|--------|---------|------------|--------|
| **Abrir/Cerrar caja** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Movimientos de caja** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Ver cajas/movimientos** | ✅ | ✅ | ✅¹ | ✅¹ | ✅ | ✅ |
| **Crear/Editar vendedores** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Ver vendedores** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Ventas POS** | ✅ | ✅ | ✅² | ✅² | ❌ | ❌ |
| **Ver ventas POS** | ✅ | ✅ | ✅² | ✅² | ✅ | ✅ |

**¹** Solo sus propias cajas/movimientos  
**²** Solo sus propias ventas (seller/cashier)

### **🏢 Multi-Tenant Security**
```python
# Automático en cada query
def get_cash_register_detail(register_id: UUID, tenant_id: UUID):
    register = db.query(CashRegister).filter(
        CashRegister.id == register_id,
        CashRegister.tenant_id == tenant_id  # ← Siempre incluido
    ).first()
    
    if not register:
        raise HTTPException(404, "Caja registradora no encontrada")
    
    return register
```

### **✅ Validaciones de Negocio**
```python
class CashRegisterService:
    def open_cash_register(self, pdv_id: UUID, tenant_id: UUID):
        # Validar que no hay otra caja abierta
        existing_open = db.query(CashRegister).filter(
            CashRegister.tenant_id == tenant_id,
            CashRegister.pdv_id == pdv_id,
            CashRegister.status == CashRegisterStatus.OPEN
        ).first()
        
        if existing_open:
            raise HTTPException(409, "Ya existe una caja abierta en este PDV")

class POSInvoiceService:
    def create_pos_sale(self, sale_data: POSInvoiceCreate, pdv_id: UUID):
        # Validar caja abierta obligatoria
        open_register = db.query(CashRegister).filter(
            CashRegister.pdv_id == pdv_id,
            CashRegister.status == CashRegisterStatus.OPEN
        ).first()
        
        if not open_register:
            raise HTTPException(409, "No hay caja abierta. Abra una caja antes de vender.")
```

---

## 📈 **PERFORMANCE Y ESCALABILIDAD**

### **⚡ Optimizaciones de Base de Datos**
```sql
-- Índices compuestos para queries más comunes
CREATE INDEX idx_cash_registers_tenant_pdv_status_opened 
ON cash_registers(tenant_id, pdv_id, status, opened_at DESC) 
WHERE status = 'open';

-- Índice para movimientos por caja
CREATE INDEX idx_cash_movements_register_created 
ON cash_movements(cash_register_id, created_at DESC);

-- Índice para ventas POS por vendedor
CREATE INDEX idx_invoices_pos_seller_date 
ON invoices(tenant_id, seller_id, issue_date DESC) 
WHERE type = 'pos';

-- Índice parcial para vendedores activos
CREATE INDEX idx_sellers_active_name 
ON sellers(tenant_id, name) 
WHERE is_active = true AND deleted_at IS NULL;
```

### **📄 Paginación Eficiente**
```python
def get_cash_movements(self, cash_register_id: UUID, limit: int = 100, offset: int = 0):
    # Query base optimizada
    base_query = self.db.query(CashMovement).filter(
        CashMovement.cash_register_id == cash_register_id
    )
    
    # Count optimizado (sin OFFSET/LIMIT)
    total = base_query.count()
    
    # Datos paginados con ORDER BY optimizado
    movements = base_query.order_by(
        desc(CashMovement.created_at)
    ).offset(offset).limit(limit).all()
    
    return {
        "movements": movements,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }
```

### **🚀 Optimizaciones de Ventas POS**
```python
@property
def calculated_balance(self) -> Decimal:
    """Balance calculado con cache en memoria"""
    if not hasattr(self, '_calculated_balance'):
        self._calculated_balance = self.opening_balance + sum(
            movement.signed_amount for movement in self.movements
        )
    return self._calculated_balance

# Bulk operations para ventas múltiples
def create_bulk_pos_sales(self, sales_data: List[POSInvoiceCreate]):
    """Crear múltiples ventas POS en una transacción"""
    try:
        invoices = []
        for sale_data in sales_data:
            invoice = self._create_single_pos_sale(sale_data)
            invoices.append(invoice)
        
        self.db.commit()
        return invoices
    except Exception:
        self.db.rollback()  
        raise
```

---

## 🔗 **INTEGRACIONES ERP**

### **🧾 Integración con Módulo Invoices**
```python
# Extensión del modelo Invoice existente
class Invoice(Base, TenantMixin, TimestampMixin):
    # Campos existentes...
    seller_id = Column(UUID, ForeignKey('sellers.id'), nullable=True)
    
    # Nueva relationship
    seller = relationship("Seller")

# Enum extendido
class InvoiceType(enum.Enum):
    SALE = "sale"    # Facturas regulares
    POS = "pos"      # Ventas POS ← NUEVO

# Query para ventas POS
pos_sales = db.query(Invoice).filter(
    Invoice.type == InvoiceType.POS,
    Invoice.tenant_id == tenant_id
).all()
```

### **📦 Integración con Módulo Inventory** 
```python
# Descuento automático en ventas POS
def _update_inventory_for_pos_sale(self, invoice: Invoice, items: List[POSLineItem]):
    for item in items:
        # 1. Reducir stock
        stock = self.db.query(Stock).filter(
            Stock.product_id == item.product_id,
            Stock.pdv_id == invoice.pdv_id,
            Stock.tenant_id == invoice.tenant_id
        ).first()
        
        stock.quantity -= item.quantity
        
        # 2. Crear movimiento OUT
        movement = InventoryMovement(
            tenant_id=invoice.tenant_id,
            product_id=item.product_id,
            pdv_id=invoice.pdv_id,
            quantity=-int(item.quantity),  # Negativo = salida
            movement_type="OUT",
            reference=f"POS-{invoice.number}",
            notes=f"Venta POS - Vendedor: {invoice.seller.name}",
            created_by=invoice.created_by
        )
        self.db.add(movement)
```

### **💳 Integración con Módulo Payments**
```python
# Pagos automáticos en ventas POS
def _create_pos_payments(self, invoice: Invoice, payments_data: List[POSPaymentCreate]):
    for payment_data in payments_data:
        # 1. Crear Payment record
        payment = Payment(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            amount=payment_data.amount,
            method=payment_data.method,
            reference=payment_data.reference,
            payment_date=date.today(),
            notes=payment_data.notes
        )
        self.db.add(payment)
        
        # 2. Crear CashMovement si es efectivo
        if payment_data.method == PaymentMethod.CASH:
            cash_movement = CashMovement(
                tenant_id=invoice.tenant_id,
                cash_register_id=self.open_register.id,
                type=MovementType.SALE,
                amount=payment_data.amount,
                reference=f"POS-{invoice.number}",
                invoice_id=invoice.id,
                created_by=invoice.created_by
            )
            self.db.add(cash_movement)
```

### **📊 Integración con Reportes (Futuro)**
```python
# Queries optimizadas para reportes POS
class POSReportQueries:
    @staticmethod
    def sales_by_seller(tenant_id: UUID, start_date: date, end_date: date):
        return db.query(
            Seller.name,
            func.count(Invoice.id).label('total_sales'),
            func.sum(Invoice.total_amount).label('total_amount'),
            func.avg(Invoice.total_amount).label('avg_ticket')
        ).join(
            Invoice, Invoice.seller_id == Seller.id
        ).filter(
            Invoice.tenant_id == tenant_id,
            Invoice.type == InvoiceType.POS,
            Invoice.issue_date.between(start_date, end_date)
        ).group_by(Seller.id, Seller.name).all()
    
    @staticmethod
    def cash_register_summary(register_id: UUID):
        return db.query(
            CashMovement.type,
            func.sum(CashMovement.amount).label('total')
        ).filter(
            CashMovement.cash_register_id == register_id
        ).group_by(CashMovement.type).all()
```

---

## 🧪 **TESTING Y CALIDAD**

### **🎯 Test Coverage Strategy**
```python
# Test de aislamiento multi-tenant (CRÍTICO)
async def test_cash_register_tenant_isolation():
    """Verificar que un tenant no ve cajas de otro"""
    # Abrir caja en tenant A
    register_a = await open_cash_register(tenant_id="tenant-a", pdv_id="pdv-1")
    
    # Buscar desde tenant B
    registers_b = await get_cash_registers(tenant_id="tenant-b")
    
    # Verificar aislamiento
    assert register_a.id not in [r.id for r in registers_b.cash_registers]
    assert len(registers_b.cash_registers) == 0

# Test de validación de caja única por PDV
async def test_single_open_register_per_pdv():
    """No permite dos cajas abiertas en el mismo PDV"""
    # Abrir primera caja
    register_1 = await open_cash_register(pdv_id="pdv-1", opening_balance=100000)
    assert register_1.status == "open"
    
    # Intentar abrir segunda caja en mismo PDV
    with pytest.raises(HTTPException) as exc_info:
        await open_cash_register(pdv_id="pdv-1", opening_balance=50000)
    
    assert exc_info.value.status_code == 409
    assert "ya existe una caja abierta" in exc_info.value.detail.lower()

# Test de venta POS completa
async def test_complete_pos_sale():
    """Venta POS completa con todas las integraciones"""
    # 1. Abrir caja
    register = await open_cash_register(opening_balance=100000)
    
    # 2. Crear venta POS
    sale = await create_pos_sale({
        "customer_id": customer_id,
        "seller_id": seller_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 25000}],
        "payments": [{"method": "cash", "amount": 50000}]
    })
    
    # 3. Verificar factura creada
    assert sale.type == "pos"
    assert sale.seller_id == seller_id
    assert sale.total_amount == 50000
    
    # 4. Verificar stock descontado
    stock = await get_stock(product_id, pdv_id)
    assert stock.quantity == original_quantity - 2
    
    # 5. Verificar movimiento de inventario
    movements = await get_inventory_movements(product_id)
    assert movements[-1].movement_type == "OUT"
    assert movements[-1].quantity == -2
    
    # 6. Verificar pago registrado
    payments = await get_invoice_payments(sale.id)
    assert len(payments) == 1
    assert payments[0].amount == 50000
    
    # 7. Verificar movimiento de caja
    cash_movements = await get_cash_movements(register.id)
    sale_movements = [m for m in cash_movements if m.type == "sale"]
    assert len(sale_movements) == 1
    assert sale_movements[0].amount == 50000

# Test de arqueo automático
async def test_cash_register_closing_with_difference():
    """Arqueo con diferencia genera ajuste automático"""
    # Abrir caja con balance inicial
    register = await open_cash_register(opening_balance=100000)
    
    # Registrar algunos movimientos
    await create_cash_movement(register.id, "deposit", 50000)
    await create_cash_movement(register.id, "withdrawal", 20000)
    # Balance calculado: 100000 + 50000 - 20000 = 130000
    
    # Cerrar con diferencia (sobrante)
    closed_register = await close_cash_register(register.id, closing_balance=135000)
    
    # Verificar que se creó ajuste
    movements = await get_cash_movements(register.id)
    adjustments = [m for m in movements if m.type == "adjustment"]
    assert len(adjustments) == 1
    assert adjustments[0].amount == 5000  # Diferencia positiva
    assert "sobrante" in adjustments[0].notes.lower()
```

### **🔧 Performance Tests**
```python
# Test de concurrencia en ventas POS
async def test_concurrent_pos_sales():
    """Manejo de ventas POS concurrentes"""
    # Abrir caja
    register = await open_cash_register(opening_balance=100000)
    
    # Crear 50 ventas simultáneas
    async def create_concurrent_sale(sale_number: int):
        return await create_pos_sale({
            "customer_id": customer_id,
            "seller_id": seller_id,
            "items": [{"product_id": product_id, "quantity": 1}],
            "payments": [{"method": "cash", "amount": 10000}]
        })
    
    # Ejecutar ventas concurrentes
    tasks = [create_concurrent_sale(i) for i in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Verificar que todas se procesaron correctamente
    successful = [r for r in results if not isinstance(r, Exception)]
    assert len(successful) == 50
    
    # Verificar stock final correcto
    final_stock = await get_stock(product_id, pdv_id)
    assert final_stock.quantity == initial_stock - 50

# Test de performance de arqueo con muchos movimientos
async def test_cash_register_closing_performance():
    """Arqueo eficiente con muchos movimientos"""
    # Abrir caja
    register = await open_cash_register(opening_balance=100000)
    
    # Crear 1000 movimientos
    for i in range(1000):
        await create_cash_movement(register.id, "sale", 1000)
    
    # Medir tiempo de cierre
    start_time = time.time()
    closed_register = await close_cash_register(register.id, closing_balance=1100000)
    end_time = time.time()
    
    # Debe cerrar en menos de 2 segundos
    assert (end_time - start_time) < 2.0
    assert closed_register.calculated_balance == 1100000
```

---

## 📋 **CASOS DE USO PRINCIPALES**

### **1. Flujo Completo de Venta POS**
```python
# 1. Apertura de turno
cash_register = await open_cash_register({
    "opening_balance": 100000.00,
    "opening_notes": "Apertura turno mañana - Vendedor: Juan Pérez"
})

# 2. Venta POS completa
pos_sale = await create_pos_sale({
    "customer_id": "uuid-cliente-generico",
    "seller_id": "uuid-juan-perez", 
    "items": [
        {
            "product_id": "uuid-producto-1",
            "quantity": 2,
            "unit_price": 25000.00
        },
        {
            "product_id": "uuid-producto-2", 
            "quantity": 1,
            "unit_price": 35000.00
        }
    ],
    "payments": [
        {
            "method": "cash",
            "amount": 85000.00,
            "notes": "Pago en efectivo completo"
        }
    ],
    "notes": "Venta mostrador - Cliente habitual"
})

# Resultado automático:
# - Factura creada con type=POS y seller_id
# - Stock descontado: Producto1 (-2), Producto2 (-1)
# - Movimientos inventario tipo OUT creados
# - Pago registrado en payments table
# - CashMovement tipo SALE creado por $85,000
# - Invoice status = PAID (pago completo)

# 3. Movimientos adicionales de caja
expense = await create_cash_movement({
    "cash_register_id": cash_register.id,
    "type": "expense",
    "amount": 15000.00,
    "reference": "SERVICIO-001",
    "notes": "Pago servicios públicos"
})

# 4. Cierre de turno con arqueo
closed_register = await close_cash_register(cash_register.id, {
    "closing_balance": 170000.00,
    "closing_notes": "Cierre turno mañana - Todo conforme"
})

# Balance calculado: 100000 + 85000 - 15000 = 170000
# Diferencia: 170000 - 170000 = 0 (sin ajustes)
```

### **2. Manejo de Vuelto Automático**
```python
# Venta con vuelto
pos_sale_with_change = await create_pos_sale({
    "customer_id": "uuid-cliente",
    "seller_id": "uuid-vendedor",
    "items": [
        {"product_id": "uuid-producto", "quantity": 1, "unit_price": 47000.00}
    ],
    "payments": [
        {"method": "cash", "amount": 50000.00, "notes": "Pago en efectivo"}
    ]
})

# Resultado automático:
# - Invoice total: $47,000
# - Payment: $50,000 (cash)
# - CashMovement SALE: +$50,000
# - CashMovement WITHDRAWAL: -$3,000 (vuelto)
# - Invoice status = PAID
# - Balance neto de caja: +$47,000
```

### **3. Gestión de Vendedores con Comisiones**
```python
# Crear vendedor con configuración de comisiones
seller = await create_seller({
    "name": "María González",
    "email": "maria.gonzalez@empresa.com",
    "phone": "+57 300 123 4567",
    "document": "12345678",
    "commission_rate": 0.05,  # 5% de comisión
    "base_salary": 1000000.00,
    "notes": "Vendedora senior - Especialista en electrónicos"
})

# Consulta de ventas y comisiones (futuro)
sales_report = await get_seller_sales_report(seller.id, "2025-09-01", "2025-09-30")
# Resultado:
# {
#     "seller": seller_info,  
#     "total_sales": 15,
#     "total_amount": 2500000.00,
#     "estimated_commission": 125000.00,  # 5% de 2,500,000
#     "avg_ticket": 166666.67,
#     "best_sale_day": "2025-09-15"
# }
```

### **4. Control de Inventario Integrado**
```python
# Verificar stock antes de venta
stock_check = await validate_pos_sale_stock({
    "items": [
        {"product_id": "uuid-prod-1", "quantity": 5},
        {"product_id": "uuid-prod-2", "quantity": 2}
    ],
    "pdv_id": pdv_id
})

# Si hay stock insuficiente:
# HTTPException(409, "Stock insuficiente para 'Producto ABC'. Disponible: 3, Solicitado: 5")

# Venta exitosa actualiza automáticamente:
# 1. Stock table: quantities reducidas por PDV
# 2. InventoryMovement records: tipo OUT con referencia POS
# 3. Kardex automático: saldo acumulado actualizado
```

---

## 🚀 **ROADMAP Y FUTURAS MEJORAS**

### **📅 Version 1.1.0 - Q4 2025**

#### **📊 Reportes Avanzados POS**
- **Ventas por vendedor**: Performance individual con comisiones
- **Arqueos detallados**: Diferencias históricas y tendencias
- **Análisis de turnos**: Comparación mañana vs tarde vs noche
- **Top productos POS**: Más vendidos en punto de venta

#### **💳 Métodos de Pago Avanzados**
- **Pagos mixtos**: Efectivo + tarjeta en una venta
- **Integración TPV**: Conexión con terminales bancarias
- **Pagos diferidos**: Apartados y pagos a plazos
- **Códigos QR**: Pagos con billeteras digitales

#### **📱 Interfaz Móvil POS**
- **App móvil**: Ventas desde tablet/smartphone
- **Modo offline**: Sincronización diferida
- **Lector códigos**: Escaneo de productos
- **Impresión remota**: Tickets vía WiFi/Bluetooth

### **📅 Version 1.2.0 - Q1 2026**

#### **🏪 Multi-Caja por PDV**
- **Múltiples cajas**: Varias abiertas simultáneamente
- **Turnos solapados**: Cambios de turno sin cerrar
- **Consolidación**: Arqueo conjunto de múltiples cajas
- **Load balancing**: Distribución automática de ventas

#### **🎯 CRM Integrado**
- **Clientes frecuentes**: Identificación automática
- **Programas de puntos**: Acumulación y redención  
- **Promociones POS**: Descuentos automáticos
- **Historial de compras**: Recomendaciones inteligentes

#### **📈 Analytics en Tiempo Real**
- **Dashboard live**: Ventas del día en tiempo real
- **Alertas automáticas**: Stock bajo, metas de venta
- **Comparativas**: Día anterior, semana, mes
- **Predicciones**: ML para forecast de ventas

### **📅 Version 1.3.0 - Q2 2026**

#### **🤖 Inteligencia Artificial**
- **Detección de fraude**: Patrones sospechosos en ventas
- **Optimización de turnos**: Mejores horarios por vendedor
- **Predicción de demanda**: Stock óptimo por PDV
- **Análisis de comportamiento**: Insights de clientes

#### **🌐 E-commerce Integration**
- **Omnichannel**: Inventario unificado online/offline
- **Click & Collect**: Reservas online, retiro en tienda
- **Devoluciones**: Proceso unificado por canal
- **Customer journey**: Seguimiento completo

#### **🔒 Seguridad Avanzada**
- **Autenticación biométrica**: Huella/facial para vendedores
- **Auditoría forense**: Log completo de operaciones
- **Cifrado end-to-end**: Protección de datos sensibles
- **Compliance PCI DSS**: Certificación de seguridad

---

## 📞 **SOPORTE Y DOCUMENTACIÓN**

### **🐛 Reportar Issues**
- **GitHub Issues**: Usar template específico para POS
- **Bug Report**: Incluir logs de caja y contexto de venta
- **Feature Request**: Usar roadmap como referencia  
- **Security Issues**: Canal privado para temas críticos

### **📚 Documentación Adicional**
- **API Reference**: Documentación OpenAPI completa
- **Integration Guide**: Guías de integración con TPV externos
- **Best Practices**: Patrones recomendados de uso
- **Troubleshooting**: Soluciones a problemas comunes

### **🎓 Capacitación**
- **Manual de Usuario**: Guía para cajeros/vendedores
- **Video Tutoriales**: Procesos paso a paso
- **Casos de Uso**: Escenarios reales de negocio
- **Certificación**: Programa de capacitación formal

### **📞 Contacto Técnico**
- **Slack Channel**: #pos-module
- **Email Support**: pos-support@ally360.com
- **Emergency Contact**: +1-xxx-xxx-xxxx (24/7)
- **Documentation Issues**: docs@ally360.com

---

**📋 README actualizado:** 28 Septiembre 2025  
**📦 Versión actual:** 1.0.0 (Development)  
**🚀 Próxima release:** v1.1.0 (Q4 2025)  
**👨‍💻 Mantenedor:** Ally360 Development Team  
**📄 Licencia:** Proprietary - Ally360 SaaS  
**🌐 Documentación:** [docs.ally360.com/pos](https://docs.ally360.com/pos)