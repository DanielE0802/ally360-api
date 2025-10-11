"""
Modelos SQLAlchemy para el módulo POS (Point of Sale)

Este módulo maneja las operaciones de punto de venta:
- CashRegister: Cajas registradoras con apertura/cierre
- CashMovement: Movimientos de caja (ventas, depósitos, retiros, etc.)
- Seller: Vendedores asociados a ventas POS
- Extensión de Invoice para type=pos

Integración con inventario:
- Ventas POS → descuentan stock automáticamente
- Movimientos de caja se registran con cada venta

Arquitectura multi-tenant: Todas las tablas incluyen company_id
"""

from app.database.database import Base
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin
import enum


# ===== ENUMS =====

class CashRegisterStatus(enum.Enum):
    """Estados de caja registradora"""
    OPEN = "open"       # Caja abierta
    CLOSED = "closed"   # Caja cerrada


class MovementType(enum.Enum):
    """Tipos de movimiento de caja"""
    SALE = "sale"               # Venta (ingreso automático)
    DEPOSIT = "deposit"         # Depósito (ingreso manual)
    WITHDRAWAL = "withdrawal"   # Retiro (egreso manual)
    EXPENSE = "expense"         # Gasto (egreso manual)
    ADJUSTMENT = "adjustment"   # Ajuste (puede ser + o -)


# ===== MODELOS =====

class CashRegister(Base, TenantMixin, TimestampMixin):
    """
    Cajas registradoras del punto de venta
    
    Maneja la apertura/cierre de cajas con arqueo automático.
    Solo puede existir una caja abierta por PDV simultáneamente.
    """
    __tablename__ = "cash_registers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pdv_id = Column(UUID(as_uuid=True), ForeignKey("pdvs.id"), nullable=False, index=True)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    status = Column(Enum(CashRegisterStatus), nullable=False, default=CashRegisterStatus.CLOSED, index=True)
    
    # Balances
    opening_balance = Column(Numeric(15, 2), nullable=False, default=0)
    closing_balance = Column(Numeric(15, 2), nullable=True)  # Solo se llena al cerrar
    
    # Control de apertura/cierre
    opened_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    closed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Notas opcionales
    opening_notes = Column(Text, nullable=True)
    closing_notes = Column(Text, nullable=True)

    # Relationships
    pdv = relationship("PDV")
    seller = relationship("Seller", foreign_keys=[seller_id])
    opened_by_user = relationship("User", foreign_keys=[opened_by])
    closed_by_user = relationship("User", foreign_keys=[closed_by])
    movements = relationship("CashMovement", back_populates="cash_register", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "pdv_id", "name", name="uq_cash_register_tenant_pdv_name"),
    )

    @property
    def calculated_balance(self):
        """Calcular balance actual basado en movimientos"""
        if not self.movements:
            return self.opening_balance
        
        total_movements = sum(
            movement.amount if movement.type in [MovementType.SALE, MovementType.DEPOSIT] 
            else -abs(movement.amount) if movement.type in [MovementType.WITHDRAWAL, MovementType.EXPENSE]
            else movement.amount  # ADJUSTMENT puede ser + o -
            for movement in self.movements
        )
        
        return self.opening_balance + total_movements

    @property
    def difference(self):
        """Diferencia entre balance calculado y closing_balance"""
        if self.status == CashRegisterStatus.CLOSED and self.closing_balance is not None:
            return self.closing_balance - self.calculated_balance
        return None


class CashMovement(Base, TenantMixin, TimestampMixin):
    """
    Movimientos de caja registradora
    
    Registra todos los movimientos de efectivo:
    - SALE: Generado automáticamente con ventas POS
    - DEPOSIT: Ingreso manual de efectivo
    - WITHDRAWAL: Retiro manual de efectivo
    - EXPENSE: Gasto pagado desde caja
    - ADJUSTMENT: Ajuste por diferencias de arqueo
    """
    __tablename__ = "cash_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cash_register_id = Column(UUID(as_uuid=True), ForeignKey("cash_registers.id"), nullable=False, index=True)
    type = Column(Enum(MovementType), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)  # Siempre el valor absoluto
    reference = Column(String(100), nullable=True)  # Referencia opcional
    notes = Column(Text, nullable=True)
    
    # Relación con factura (solo para type=SALE)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True, index=True)
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    cash_register = relationship("CashRegister", back_populates="movements")
    invoice = relationship("Invoice")
    created_by_user = relationship("User")

    __table_args__ = ()

    @property
    def signed_amount(self):
        """Monto con signo según el tipo de movimiento"""
        if self.type in [MovementType.SALE, MovementType.DEPOSIT]:
            return abs(self.amount)  # Ingresos positivos
        elif self.type in [MovementType.WITHDRAWAL, MovementType.EXPENSE]:
            return -abs(self.amount)  # Egresos negativos
        else:  # ADJUSTMENT
            return self.amount  # Puede ser positivo o negativo


class Seller(Base, TenantMixin, TimestampMixin):
    """
    Vendedores asociados a ventas POS
    
    Los vendedores se asocian a facturas type=pos para reportes
    y control de ventas por persona.
    """
    __tablename__ = "sellers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(200), nullable=False, index=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    document = Column(String(50), nullable=True)  # Cédula/ID opcional
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Configuración de comisiones (futuro)
    commission_rate = Column(Numeric(5, 4), nullable=True)  # Ej: 0.05 = 5%
    base_salary = Column(Numeric(15, 2), nullable=True)
    
    # Notas adicionales
    notes = Column(Text, nullable=True)

    # Relationships
    # Relación inversa con Invoice se define en invoices/models.py
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_seller_tenant_email"),
        UniqueConstraint("tenant_id", "document", name="uq_seller_tenant_document"),
    )