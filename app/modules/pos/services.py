"""
Servicios de negocio para el módulo POS (Point of Sale)

Implementa toda la lógica de negocio para:
- CashRegisterService: Apertura/cierre de cajas y arqueo
- CashMovementService: Registro de movimientos de caja
- SellerService: Gestión de vendedores
- POSInvoiceService: Ventas POS integradas con inventario y pagos

Integración con otros módulos:
- Invoices: Extensión con type=pos y seller_id
- Inventory: Descuento automático de stock
- Payments: Pagos obligatorios en ventas POS
- Auth: Validación de permisos y contexto de usuario
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, func, desc
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime

from app.modules.pos.models import (
    CashRegister, CashMovement, Seller,
    CashRegisterStatus, MovementType
)
from app.modules.pos.schemas import (
    CashRegisterCreate, CashRegisterOpen, CashRegisterClose,
    CashMovementCreate, SellerCreate, SellerUpdate,
    POSInvoiceCreate
)
from app.modules.invoices.models import Invoice, InvoiceLineItem, Payment, InvoiceType, InvoiceStatus
from app.modules.invoices.schemas import PaymentMethod
from app.modules.pdv.models import PDV
from app.modules.contacts.models import Contact
from app.modules.products.models import Product, Stock, InventoryMovement


class CashRegisterService:
    """Servicio para gestión de cajas registradoras"""

    def __init__(self, db: Session):
        self.db = db

    def open_cash_register(self, register_data: CashRegisterOpen, pdv_id: UUID, 
                          tenant_id: UUID, user_id: UUID) -> CashRegister:
        """Abrir caja registradora"""
        try:
            # Validar que el PDV existe y pertenece al tenant
            pdv = self.db.query(PDV).filter(
                PDV.id == pdv_id,
                PDV.tenant_id == tenant_id
            ).first()
            
            if not pdv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDV no encontrado"
                )
            
            # Validar seller_id si se proporciona
            seller = None
            if register_data.seller_id:
                seller = self.db.query(Seller).filter(
                    Seller.id == register_data.seller_id,
                    Seller.tenant_id == tenant_id,
                    Seller.is_active == True
                ).first()
                
                if not seller:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Vendedor no encontrado o inactivo"
                    )
            
            # Verificar que no hay otra caja abierta en el mismo PDV
            existing_open = self.db.query(CashRegister).filter(
                CashRegister.tenant_id == tenant_id,
                CashRegister.pdv_id == pdv_id,
                CashRegister.status == CashRegisterStatus.OPEN
            ).first()
            
            if existing_open:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una caja abierta en el PDV '{pdv.name}'"
                )
            
            # Crear nueva caja con nombre automático si no se especifica
            seller_name = f" - {seller.name}" if seller else ""
            register_name = f"Caja {pdv.name}{seller_name} - {datetime.now().strftime('%Y%m%d')}"
            
            new_register = CashRegister(
                tenant_id=tenant_id,
                pdv_id=pdv_id,
                seller_id=register_data.seller_id,
                name=register_name,
                status=CashRegisterStatus.OPEN,
                opening_balance=register_data.opening_balance,
                opened_by=user_id,
                opened_at=datetime.utcnow(),
                opening_notes=register_data.opening_notes
            )
            
            self.db.add(new_register)
            self.db.commit()
            self.db.refresh(new_register)
            
            return new_register
            
        except HTTPException:
            raise
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Error de integridad al crear la caja"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_current_cash_register(self, tenant_id: UUID, pdv_id: UUID) -> Optional[CashRegister]:
        """
        Obtener la caja abierta actual para un PDV específico.

        Retorna None si no existe caja abierta para ese PDV.
        """
        register = self.db.query(CashRegister).filter(
            and_(
                CashRegister.tenant_id == tenant_id,
                CashRegister.pdv_id == pdv_id,
                CashRegister.status == CashRegisterStatus.OPEN
            )
        ).first()
        return register

    def close_cash_register(self, register_id: UUID, close_data: CashRegisterClose,
                           tenant_id: UUID, user_id: UUID) -> CashRegister:
        """Cerrar caja registradora con arqueo"""
        try:
            # Obtener caja registradora
            register = self.db.query(CashRegister).filter(
                CashRegister.id == register_id,
                CashRegister.tenant_id == tenant_id
            ).first()
            
            if not register:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Caja registradora no encontrada"
                )
            
            if register.status == CashRegisterStatus.CLOSED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La caja ya está cerrada"
                )
            
            # Calcular balance real basado en movimientos
            calculated_balance = register.calculated_balance
            declared_balance = close_data.closing_balance
            difference = declared_balance - calculated_balance
            
            # Si hay diferencia, crear movimiento de ajuste
            if difference != 0:
                adjustment = CashMovement(
                    tenant_id=tenant_id,
                    cash_register_id=register_id,
                    type=MovementType.ADJUSTMENT,
                    amount=abs(difference),
                    reference="ARQUEO",
                    notes=f"Ajuste por diferencia en arqueo: {'Sobrante' if difference > 0 else 'Faltante'} de ${abs(difference)}",
                    created_by=user_id
                )
                self.db.add(adjustment)
            
            # Cerrar caja
            register.status = CashRegisterStatus.CLOSED
            register.closing_balance = close_data.closing_balance
            register.closed_by = user_id
            register.closed_at = datetime.utcnow()
            register.closing_notes = close_data.closing_notes
            
            self.db.commit()
            self.db.refresh(register)
            
            return register
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_cash_registers(self, tenant_id: UUID, pdv_id: Optional[UUID] = None,
                          status: Optional[CashRegisterStatus] = None,
                          limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Obtener lista de cajas registradoras"""
        try:
            query = self.db.query(CashRegister).filter(
                CashRegister.tenant_id == tenant_id
            )
            
            if pdv_id:
                query = query.filter(CashRegister.pdv_id == pdv_id)
            
            if status:
                query = query.filter(CashRegister.status == status)
            
            # Ordenar por fecha de apertura descendente
            query = query.order_by(desc(CashRegister.opened_at))
            
            total = query.count()
            registers = query.offset(offset).limit(limit).all()
            
            return {
                "cash_registers": registers,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_cash_register_detail(self, register_id: UUID, tenant_id: UUID) -> CashRegister:
        """Obtener detalle de caja registradora con movimientos"""
        try:
            register = self.db.query(CashRegister).options(
                selectinload(CashRegister.movements),
                selectinload(CashRegister.seller),
                selectinload(CashRegister.pdv),
                selectinload(CashRegister.opened_by_user),
                selectinload(CashRegister.closed_by_user)
            ).filter(
                CashRegister.id == register_id,
                CashRegister.tenant_id == tenant_id
            ).first()
            
            if not register:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Caja registradora no encontrada"
                )
            
            return register
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )


class CashMovementService:
    """Servicio para gestión de movimientos de caja"""

    def __init__(self, db: Session):
        self.db = db

    def create_movement(self, movement_data: CashMovementCreate, 
                       tenant_id: UUID, user_id: UUID) -> CashMovement:
        """Crear movimiento de caja"""
        try:
            # Validar que la caja registradora existe y está abierta
            register = self.db.query(CashRegister).filter(
                CashRegister.id == movement_data.cash_register_id,
                CashRegister.tenant_id == tenant_id
            ).first()
            
            if not register:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Caja registradora no encontrada"
                )
            
            if register.status != CashRegisterStatus.OPEN:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La caja debe estar abierta para registrar movimientos"
                )
            
            # Crear movimiento
            new_movement = CashMovement(
                tenant_id=tenant_id,
                cash_register_id=movement_data.cash_register_id,
                type=movement_data.type,
                amount=abs(movement_data.amount),  # Siempre valor absoluto
                reference=movement_data.reference,
                notes=movement_data.notes,
                created_by=user_id
            )
            
            self.db.add(new_movement)
            self.db.commit()
            self.db.refresh(new_movement)
            
            return new_movement
            
        except HTTPException:
            raise
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Error de integridad al crear el movimiento"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_movements(self, cash_register_id: Optional[UUID] = None,
                     tenant_id: UUID = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Obtener lista de movimientos de caja"""
        try:
            query = self.db.query(CashMovement).filter(
                CashMovement.tenant_id == tenant_id
            )
            
            if cash_register_id:
                query = query.filter(CashMovement.cash_register_id == cash_register_id)
            
            # Ordenar por fecha de creación descendente
            query = query.order_by(desc(CashMovement.created_at))
            
            total = query.count()
            movements = query.offset(offset).limit(limit).all()
            
            # Calcular resumen
            summary = self._calculate_movements_summary(movements)
            
            return {
                "movements": movements,
                "summary": summary,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def _calculate_movements_summary(self, movements: List[CashMovement]) -> Dict[str, Decimal]:
        """Calcular resumen de movimientos"""
        summary = {
            "total_sales": Decimal("0"),
            "total_deposits": Decimal("0"),
            "total_withdrawals": Decimal("0"),
            "total_expenses": Decimal("0"),
            "total_adjustments": Decimal("0")
        }
        
        for movement in movements:
            if movement.type == MovementType.SALE:
                summary["total_sales"] += movement.amount
            elif movement.type == MovementType.DEPOSIT:
                summary["total_deposits"] += movement.amount
            elif movement.type == MovementType.WITHDRAWAL:
                summary["total_withdrawals"] += movement.amount
            elif movement.type == MovementType.EXPENSE:
                summary["total_expenses"] += movement.amount
            elif movement.type == MovementType.ADJUSTMENT:
                summary["total_adjustments"] += movement.signed_amount
        
        return summary


class SellerService:
    """Servicio para gestión de vendedores"""

    def __init__(self, db: Session):
        self.db = db

    def create_seller(self, seller_data: SellerCreate, tenant_id: UUID, user_id: UUID) -> Seller:
        """Crear vendedor"""
        try:
            # Validar unicidad de email y documento si se proporcionan
            if seller_data.email:
                existing_email = self.db.query(Seller).filter(
                    Seller.tenant_id == tenant_id,
                    Seller.email == seller_data.email,
                    Seller.deleted_at.is_(None)
                ).first()
                
                if existing_email:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya existe un vendedor con este email"
                    )
            
            if seller_data.document:
                existing_document = self.db.query(Seller).filter(
                    Seller.tenant_id == tenant_id,
                    Seller.document == seller_data.document,
                    Seller.deleted_at.is_(None)
                ).first()
                
                if existing_document:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya existe un vendedor con este documento"
                    )
            
            # Crear vendedor
            new_seller = Seller(
                tenant_id=tenant_id,
                name=seller_data.name,
                email=seller_data.email,
                phone=seller_data.phone,
                document=seller_data.document,
                commission_rate=seller_data.commission_rate,
                base_salary=seller_data.base_salary,
                notes=seller_data.notes,
                is_active=True
            )
            
            self.db.add(new_seller)
            self.db.commit()
            self.db.refresh(new_seller)
            
            return new_seller
            
        except HTTPException:
            raise
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Error de integridad al crear el vendedor"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def update_seller(self, seller_id: UUID, seller_data: SellerUpdate,
                     tenant_id: UUID, user_id: UUID) -> Seller:
        """Actualizar vendedor"""
        try:
            seller = self.db.query(Seller).filter(
                Seller.id == seller_id,
                Seller.tenant_id == tenant_id,
                Seller.deleted_at.is_(None)
            ).first()
            
            if not seller:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vendedor no encontrado"
                )
            
            # Actualizar campos proporcionados
            update_data = seller_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(seller, field, value)
            
            self.db.commit()
            self.db.refresh(seller)
            
            return seller
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_sellers(self, tenant_id: UUID, active_only: bool = False,
                   limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Obtener lista de vendedores"""
        try:
            query = self.db.query(Seller).filter(
                Seller.tenant_id == tenant_id,
                Seller.deleted_at.is_(None)
            )
            
            if active_only:
                query = query.filter(Seller.is_active == True)
            
            query = query.order_by(Seller.name)
            
            total = query.count()
            sellers = query.offset(offset).limit(limit).all()
            
            return {
                "sellers": sellers,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_seller_by_id(self, seller_id: UUID, tenant_id: UUID) -> Seller:
        """Obtener vendedor por ID"""
        try:
            seller = self.db.query(Seller).filter(
                Seller.id == seller_id,
                Seller.tenant_id == tenant_id,
                Seller.deleted_at.is_(None)
            ).first()
            
            if not seller:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vendedor no encontrado"
                )
            
            return seller
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete_seller(self, seller_id: UUID, tenant_id: UUID, user_id: UUID) -> bool:
        """Desactivar vendedor (soft delete)"""
        try:
            seller = self.db.query(Seller).filter(
                Seller.id == seller_id,
                Seller.tenant_id == tenant_id,
                Seller.deleted_at.is_(None)
            ).first()
            
            if not seller:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vendedor no encontrado"
                )
            
            # Soft delete
            seller.is_active = False
            seller.deleted_at = datetime.utcnow()
            
            self.db.commit()
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )


class POSInvoiceService:
    """Servicio para ventas POS integradas"""

    def __init__(self, db: Session):
        self.db = db

    def create_pos_sale(self, sale_data: POSInvoiceCreate, pdv_id: UUID,
                       tenant_id: UUID, user_id: UUID) -> Invoice:
        """Crear venta POS completa con pagos y movimientos de caja"""
        try:
            # Validar que hay una caja abierta en el PDV
            open_register = self.db.query(CashRegister).filter(
                CashRegister.tenant_id == tenant_id,
                CashRegister.pdv_id == pdv_id,
                CashRegister.status == CashRegisterStatus.OPEN
            ).first()
            
            if not open_register:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No hay una caja abierta en este PDV. Abra una caja antes de realizar ventas."
                )
            
            # Validar cliente
            customer = self.db.query(Contact).filter(
                Contact.id == sale_data.customer_id,
                Contact.tenant_id == tenant_id,
                Contact.deleted_at.is_(None)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cliente no encontrado"
                )
            
            # Validar vendedor
            seller = self.db.query(Seller).filter(
                Seller.id == sale_data.seller_id,
                Seller.tenant_id == tenant_id,
                Seller.is_active == True,
                Seller.deleted_at.is_(None)
            ).first()
            
            if not seller:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vendedor no encontrado o inactivo"
                )
            
            # Crear factura POS
            from app.modules.invoices.service import InvoiceService
            invoice_service = InvoiceService(self.db)
            
            # Generar número de factura
            invoice_number = invoice_service.generate_invoice_number(pdv_id, tenant_id)
            
            # Crear factura
            invoice = Invoice(
                tenant_id=tenant_id,
                pdv_id=pdv_id,
                customer_id=sale_data.customer_id,
                seller_id=sale_data.seller_id,
                created_by=user_id,
                number=invoice_number,
                type=InvoiceType.POS,
                status=InvoiceStatus.OPEN,  # POS siempre va directo a OPEN
                issue_date=date.today(),
                notes=sale_data.notes,
                currency="COP"
            )
            
            self.db.add(invoice)
            self.db.flush()  # Para obtener el ID
            
            # Crear líneas de factura y validar stock
            total_amount = Decimal("0")
            for item_data in sale_data.items:
                # Validar producto
                product = self.db.query(Product).filter(
                    Product.id == item_data.product_id,
                    Product.tenant_id == tenant_id,
                    Product.deleted_at.is_(None)
                ).first()
                
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Producto no encontrado: {item_data.product_id}"
                    )
                
                # Validar stock disponible
                stock = self.db.query(Stock).filter(
                    Stock.product_id == item_data.product_id,
                    Stock.pdv_id == pdv_id,
                    Stock.tenant_id == tenant_id
                ).first()
                
                if not stock or stock.quantity < item_data.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Stock insuficiente para el producto '{product.name}'. "
                               f"Disponible: {stock.quantity if stock else 0}, Solicitado: {item_data.quantity}"
                    )
                
                # Precio unitario (del producto si no se especifica)
                unit_price = item_data.unit_price or product.price
                line_subtotal = unit_price * item_data.quantity
                
                # Crear línea de factura
                line_item = InvoiceLineItem(
                    invoice_id=invoice.id,
                    product_id=item_data.product_id,
                    name=product.name,
                    sku=product.sku,
                    quantity=item_data.quantity,
                    unit_price=unit_price,
                    line_subtotal=line_subtotal,
                    line_total=line_subtotal  # Por ahora sin impuestos complejos
                )
                
                self.db.add(line_item)
                total_amount += line_subtotal
                
                # Descontar stock
                stock.quantity -= item_data.quantity
                
                # Crear movimiento de inventario
                movement = InventoryMovement(
                    tenant_id=tenant_id,
                    product_id=item_data.product_id,
                    pdv_id=pdv_id,
                    quantity=-int(item_data.quantity),  # Negativo porque es salida
                    movement_type="OUT",
                    reference=f"POS-{invoice_number}",
                    notes=f"Venta POS - Factura {invoice_number}",
                    created_by=user_id
                )
                self.db.add(movement)
            
            # Actualizar totales de factura
            invoice.subtotal = total_amount
            invoice.total_amount = total_amount
            
            # Validar que los pagos cubren el total
            total_payments = sum(payment.amount for payment in sale_data.payments)
            if total_payments < total_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Los pagos (${total_payments}) no cubren el total de la venta (${total_amount})"
                )
            
            # Crear pagos
            for payment_data in sale_data.payments:
                payment = Payment(
                    tenant_id=tenant_id,
                    invoice_id=invoice.id,
                    amount=payment_data.amount,
                    method=payment_data.method,
                    reference=payment_data.reference,
                    payment_date=date.today(),
                    notes=payment_data.notes
                )
                self.db.add(payment)
                
                # Crear movimiento de caja solo para pagos en efectivo
                if payment_data.method == PaymentMethod.CASH:
                    cash_movement = CashMovement(
                        tenant_id=tenant_id,
                        cash_register_id=open_register.id,
                        type=MovementType.SALE,
                        amount=payment_data.amount,
                        reference=f"POS-{invoice_number}",
                        notes=f"Venta POS - {payment_data.method.value}",
                        invoice_id=invoice.id,
                        created_by=user_id
                    )
                    self.db.add(cash_movement)
            
            # Si hay vuelto, registrarlo como egreso
            if total_payments > total_amount:
                change_amount = total_payments - total_amount
                change_movement = CashMovement(
                    tenant_id=tenant_id,
                    cash_register_id=open_register.id,
                    type=MovementType.WITHDRAWAL,
                    amount=change_amount,
                    reference=f"CAMBIO-{invoice_number}",
                    notes=f"Vuelto de venta POS {invoice_number}",
                    invoice_id=invoice.id,
                    created_by=user_id
                )
                self.db.add(change_movement)
            
            # Marcar factura como pagada si los pagos cubren exactamente
            if total_payments >= total_amount:
                invoice.status = InvoiceStatus.PAID
            
            self.db.commit()
            self.db.refresh(invoice)
            
            return invoice
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )