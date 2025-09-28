"""
Servicios de negocio para el módulo de Gastos (Bills)

Implementa toda la lógica de negocio para:
- Gestión de proveedores (CRUD)
- Órdenes de compra con cálculos de impuestos
- Facturas de proveedor con integración de inventario
- Pagos con control de estados automático
- Notas débito con diferentes tipos de ajuste

Integración con otros módulos:
- Inventory: Actualizaciones de stock y movimientos
- Taxes: Cálculo automático de impuestos
- Auth: Validación de permisos y context de usuario
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, func
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime

from app.modules.bills.models import (
    PurchaseOrder, POItem, Bill, BillLineItem, 
    BillPayment, DebitNote, DebitNoteItem,
    PurchaseOrderStatus, BillStatus, DebitNoteStatus, DebitNoteReasonType
)
from app.modules.bills.schemas import (
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderList, PurchaseOrderDetail,
    BillCreate, BillUpdate, BillList, BillDetail,
    BillPaymentCreate, BillPaymentList,
    DebitNoteCreate, DebitNoteUpdate, DebitNoteList, DebitNoteDetail,
    ConvertPOToBillRequest
)

from app.modules.contacts.models import Contact, ContactType
from app.modules.contacts.schemas import ContactForBill


class ProviderValidator:
    """Helper to validate that a contact is a provider for current tenant"""
    def __init__(self, db: Session):
        self.db = db

    def require_provider(self, contact_id: UUID, tenant_id: UUID) -> Contact:
        contact = self.db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.tenant_id == tenant_id,
            Contact.deleted_at.is_(None),
            Contact.is_active == True
        ).first()
        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proveedor (contacto) no encontrado")
        if ContactType.PROVIDER.value not in (contact.type or []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El contacto no es un proveedor")
        return contact


class PurchaseOrderService:
    """Servicio para gestión de órdenes de compra"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_purchase_order(
        self,
        po_data: PurchaseOrderCreate,
        tenant_id: UUID,
        user_id: UUID
    ) -> PurchaseOrder:
        """Crear nueva orden de compra"""
        try:
            # Verificar que el proveedor existe
            # Validate supplier as a Contact of type provider
            ProviderValidator(self.db).require_provider(po_data.supplier_id, tenant_id)

            # Verificar que el PDV existe
            from app.modules.pdv.models import PDV
            pdv = self.db.query(PDV).filter(
                PDV.id == po_data.pdv_id,
                PDV.tenant_id == tenant_id
            ).first()
            
            if not pdv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDV no encontrado"
                )

            # Crear la orden
            purchase_order = PurchaseOrder(
                supplier_id=po_data.supplier_id,
                pdv_id=po_data.pdv_id,
                issue_date=po_data.issue_date,
                currency=po_data.currency,
                notes=po_data.notes,
                tenant_id=tenant_id,
                created_by=user_id
            )
            
            self.db.add(purchase_order)
            self.db.flush()  # Para obtener el ID
            
            # Procesar ítems y calcular totales
            subtotal = Decimal('0')
            taxes_total = Decimal('0')
            
            for item_data in po_data.items:
                # Verificar que el producto existe
                from app.modules.products.models import Product
                product = self.db.query(Product).filter(
                    Product.id == item_data.product_id,
                    Product.tenant_id == tenant_id
                ).first()
                
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Producto {item_data.product_id} no encontrado"
                    )
                
                # Calcular línea
                line_subtotal = item_data.quantity * item_data.unit_price
                
                # TODO: Calcular impuestos (integración con módulo taxes)
                line_taxes = {}
                line_taxes_amount = Decimal('0')
                
                line_total = line_subtotal + line_taxes_amount
                
                # Crear ítem
                po_item = POItem(
                    purchase_order_id=purchase_order.id,
                    product_id=item_data.product_id,
                    name=product.name,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price,
                    line_subtotal=line_subtotal,
                    line_taxes=line_taxes,
                    line_total=line_total
                )
                
                self.db.add(po_item)
                
                subtotal += line_subtotal
                taxes_total += line_taxes_amount
            
            # Actualizar totales
            purchase_order.subtotal = subtotal
            purchase_order.taxes_total = taxes_total
            purchase_order.total_amount = subtotal + taxes_total
            
            self.db.commit()
            self.db.refresh(purchase_order)
            
            return purchase_order
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando orden de compra: {str(e)}"
            )

    def get_purchase_orders(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[PurchaseOrderStatus] = None,
        supplier_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None
    ) -> PurchaseOrderList:
        """Listar órdenes de compra con filtros"""
        try:
            query = self.db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant_id)
            
            if status:
                query = query.filter(PurchaseOrder.status == status)
            if supplier_id:
                query = query.filter(PurchaseOrder.supplier_id == supplier_id)
            if pdv_id:
                query = query.filter(PurchaseOrder.pdv_id == pdv_id)
            
            total = query.count()
            purchase_orders = query.order_by(PurchaseOrder.created_at.desc()).offset(offset).limit(limit).all()
            
            return PurchaseOrderList(
                items=purchase_orders,
                total=total,
                limit=limit,
                offset=offset
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando órdenes de compra: {str(e)}"
            )

    def get_purchase_order_by_id(self, po_id: UUID, tenant_id: UUID) -> PurchaseOrder:
        """Obtener orden de compra por ID con detalles"""
        po = self.db.query(PurchaseOrder).filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == tenant_id
        ).first()
        
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Orden de compra no encontrada"
            )
        
        return po

    def convert_po_to_bill(
        self,
        po_id: UUID,
        conversion_data: ConvertPOToBillRequest,
        tenant_id: UUID,
        user_id: UUID
    ) -> Bill:
        """Convertir orden de compra a factura"""
        try:
            # Obtener orden de compra
            po = self.get_purchase_order_by_id(po_id, tenant_id)
            
            if po.status not in [PurchaseOrderStatus.SENT, PurchaseOrderStatus.APPROVED]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solo se pueden convertir órdenes enviadas o aprobadas"
                )
            
            # Crear factura basada en la orden
            bill_service = BillService(self.db)
            
            # Preparar datos de la factura
            bill_items = []
            for po_item in po.items:
                bill_items.append({
                    "product_id": po_item.product_id,
                    "quantity": po_item.quantity,
                    "unit_price": po_item.unit_price
                })
            
            from app.modules.bills.schemas import BillCreate, BillLineItemCreate
            bill_data = BillCreate(
                supplier_id=po.supplier_id,
                pdv_id=po.pdv_id,
                number=conversion_data.bill_number,
                issue_date=conversion_data.issue_date,
                due_date=conversion_data.due_date,
                currency=po.currency,
                notes=f"Convertida desde Orden de Compra #{po.id}. {conversion_data.notes or ''}".strip(),
                status=conversion_data.status,
                line_items=[BillLineItemCreate(**item) for item in bill_items]
            )
            
            bill = bill_service.create_bill(bill_data, tenant_id, user_id)
            
            # Marcar orden como cerrada
            po.status = PurchaseOrderStatus.CLOSED
            self.db.commit()
            
            return bill
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error convirtiendo orden a factura: {str(e)}"
            )

    def void_purchase_order(self, po_id: UUID, reason: Optional[str], tenant_id: UUID) -> PurchaseOrder:
        """Anular una orden de compra"""
        try:
            po = self.get_purchase_order_by_id(po_id, tenant_id)
            if po.status == PurchaseOrderStatus.VOID:
                return po
            if po.status == PurchaseOrderStatus.CLOSED:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede anular una orden cerrada")
            po.status = PurchaseOrderStatus.VOID
            if reason:
                note = (po.notes or "").strip()
                po.notes = f"{note}\n[VOID] {reason}".strip()
            self.db.commit()
            self.db.refresh(po)
            return po
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error anulando orden de compra: {str(e)}")


class BillService:
    """Servicio para gestión de facturas de proveedor"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_bill(self, bill_data: BillCreate, tenant_id: UUID, user_id: UUID) -> Bill:
        """Crear nueva factura de proveedor"""
        try:
            # Verificar proveedor
            # Validate supplier as a Contact of type provider
            ProviderValidator(self.db).require_provider(bill_data.supplier_id, tenant_id)

            # Crear factura
            bill = Bill(
                supplier_id=bill_data.supplier_id,
                pdv_id=bill_data.pdv_id,
                number=bill_data.number,
                issue_date=bill_data.issue_date,
                due_date=bill_data.due_date,
                currency=bill_data.currency,
                notes=bill_data.notes,
                status=bill_data.status,
                tenant_id=tenant_id,
                created_by=user_id
            )
            
            self.db.add(bill)
            self.db.flush()
            
            # Procesar ítems
            subtotal = Decimal('0')
            taxes_total = Decimal('0')
            
            for item_data in bill_data.line_items:
                # Verificar producto
                from app.modules.products.models import Product
                product = self.db.query(Product).filter(
                    Product.id == item_data.product_id,
                    Product.tenant_id == tenant_id
                ).first()
                
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Producto {item_data.product_id} no encontrado"
                    )
                
                # Calcular línea
                line_subtotal = item_data.quantity * item_data.unit_price
                line_taxes = {}
                line_taxes_amount = Decimal('0')
                line_total = line_subtotal + line_taxes_amount
                
                # Crear ítem
                bill_item = BillLineItem(
                    bill_id=bill.id,
                    product_id=item_data.product_id,
                    name=product.name,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price,
                    line_subtotal=line_subtotal,
                    line_taxes=line_taxes,
                    line_total=line_total
                )
                
                self.db.add(bill_item)
                
                subtotal += line_subtotal
                taxes_total += line_taxes_amount
            
            # Actualizar totales
            bill.subtotal = subtotal
            bill.taxes_total = taxes_total
            bill.total_amount = subtotal + taxes_total
            
            # Si el estado es OPEN, actualizar inventario
            if bill.status == BillStatus.OPEN:
                self._update_inventory_for_bill(bill, movement_type="IN")
            
            self.db.commit()
            self.db.refresh(bill)
            
            return bill
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando factura: {str(e)}"
            )

    def _update_inventory_for_bill(self, bill: Bill, movement_type: str):
        """Actualizar inventario cuando una factura se vuelve OPEN"""
        from app.modules.products.models import Stock, InventoryMovement
        
        for item in bill.line_items:
            # Actualizar stock
            stock = self.db.query(Stock).filter(
                Stock.product_id == item.product_id,
                Stock.pdv_id == bill.pdv_id,
                Stock.tenant_id == bill.tenant_id
            ).first()
            
            if not stock:
                # Crear stock si no existe
                stock = Stock(
                    product_id=item.product_id,
                    pdv_id=bill.pdv_id,
                    tenant_id=bill.tenant_id,
                    quantity=0
                )
                self.db.add(stock)
                self.db.flush()
            
            # Incrementar stock (Stock.quantity es entero)
            stock.quantity += int(item.quantity)
            
            # Crear movimiento de inventario
            movement = InventoryMovement(
                product_id=item.product_id,
                pdv_id=bill.pdv_id,
                tenant_id=bill.tenant_id,
                movement_type=movement_type,
                quantity=int(item.quantity),
                reference=str(bill.id),
                notes=f"Factura de compra #{bill.number}",
                created_by=bill.created_by
            )
            
            self.db.add(movement)

    def get_bills(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[BillStatus] = None,
        supplier_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> BillList:
        """Listar facturas con filtros"""
        try:
            query = self.db.query(Bill).filter(Bill.tenant_id == tenant_id)
            
            if status:
                query = query.filter(Bill.status == status)
            if supplier_id:
                query = query.filter(Bill.supplier_id == supplier_id)
            if pdv_id:
                query = query.filter(Bill.pdv_id == pdv_id)
            if start_date:
                query = query.filter(Bill.issue_date >= start_date)
            if end_date:
                query = query.filter(Bill.issue_date <= end_date)
            
            total = query.count()
            bills = query.order_by(Bill.created_at.desc()).offset(offset).limit(limit).all()
            
            return BillList(
                items=bills,
                total=total,
                limit=limit,
                offset=offset
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando facturas: {str(e)}"
            )

    def get_bill_by_id(self, bill_id: UUID, tenant_id: UUID) -> Bill:
        """Obtener factura por ID"""
        bill = self.db.query(Bill).filter(
            Bill.id == bill_id,
            Bill.tenant_id == tenant_id
        ).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Factura no encontrada"
            )
        
        return bill

    def update_bill(self, bill_id: UUID, bill_update: BillUpdate, tenant_id: UUID) -> Bill:
        """Actualizar una factura solo si está en estado draft"""
        try:
            bill = self.get_bill_by_id(bill_id, tenant_id)
            if bill.status != BillStatus.DRAFT:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Solo se pueden actualizar facturas en estado borrador")

            # If supplier_id changed, validate provider contact
            if bill_update.supplier_id:
                ProviderValidator(self.db).require_provider(bill_update.supplier_id, tenant_id)
                bill.supplier_id = bill_update.supplier_id
            if bill_update.pdv_id:
                from app.modules.pdv.models import PDV
                pdv = self.db.query(PDV).filter(PDV.id == bill_update.pdv_id, PDV.tenant_id == tenant_id).first()
                if not pdv:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDV no encontrado")
                bill.pdv_id = bill_update.pdv_id
            if bill_update.number is not None:
                bill.number = bill_update.number
            if bill_update.issue_date is not None:
                bill.issue_date = bill_update.issue_date
            if bill_update.due_date is not None:
                base_issue_date = bill_update.issue_date or bill.issue_date
                if base_issue_date and bill_update.due_date < base_issue_date:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La fecha de vencimiento no puede ser anterior a la fecha de emisión")
                bill.due_date = bill_update.due_date
            if bill_update.currency is not None:
                bill.currency = bill_update.currency
            if bill_update.notes is not None:
                bill.notes = bill_update.notes

            # Replace line items if provided
            if bill_update.line_items is not None:
                # Clear existing items
                for li in list(bill.line_items):
                    self.db.delete(li)
                self.db.flush()
                subtotal = Decimal('0')
                taxes_total = Decimal('0')
                from app.modules.products.models import Product
                for item_data in bill_update.line_items:
                    product = self.db.query(Product).filter(Product.id == item_data.product_id, Product.tenant_id == tenant_id).first()
                    if not product:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Producto {item_data.product_id} no encontrado")
                    line_subtotal = item_data.quantity * item_data.unit_price
                    line_taxes = {}
                    line_taxes_amount = Decimal('0')
                    line_total = line_subtotal + line_taxes_amount
                    bill_item = BillLineItem(
                        bill_id=bill.id,
                        product_id=item_data.product_id,
                        name=product.name,
                        quantity=item_data.quantity,
                        unit_price=item_data.unit_price,
                        line_subtotal=line_subtotal,
                        line_taxes=line_taxes,
                        line_total=line_total
                    )
                    self.db.add(bill_item)
                    subtotal += line_subtotal
                    taxes_total += line_taxes_amount
                bill.subtotal = subtotal
                bill.taxes_total = taxes_total
                bill.total_amount = subtotal + taxes_total

            self.db.commit()
            self.db.refresh(bill)
            return bill
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error actualizando factura: {str(e)}")

    def void_bill(self, bill_id: UUID, reason: Optional[str], tenant_id: UUID) -> Bill:
        """Anular una factura. MVP: no revierte inventario"""
        try:
            bill = self.get_bill_by_id(bill_id, tenant_id)
            if bill.status == BillStatus.VOID:
                return bill
            bill.status = BillStatus.VOID
            if reason:
                note = (bill.notes or "").strip()
                bill.notes = f"{note}\n[VOID] {reason}".strip()
            self.db.commit()
            self.db.refresh(bill)
            return bill
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error anulando factura: {str(e)}")


class BillPaymentService:
    """Servicio para gestión de pagos de facturas"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_payment(
        self, 
        bill_id: UUID, 
        payment_data: BillPaymentCreate, 
        tenant_id: UUID, 
        user_id: UUID
    ) -> BillPayment:
        """Registrar pago de factura"""
        try:
            # Verificar factura
            bill_service = BillService(self.db)
            bill = bill_service.get_bill_by_id(bill_id, tenant_id)
            
            if bill.status == BillStatus.VOID:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pueden registrar pagos en facturas anuladas"
                )
            
            # Verificar que no se exceda el saldo
            pending_amount = bill.total_amount - bill.paid_amount
            if payment_data.amount > pending_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El pago ({payment_data.amount}) excede el saldo pendiente ({pending_amount})"
                )
            
            # Crear pago
            payment = BillPayment(
                bill_id=bill_id,
                amount=payment_data.amount,
                method=payment_data.method,
                reference=payment_data.reference,
                payment_date=payment_data.payment_date,
                notes=payment_data.notes,
                tenant_id=tenant_id,
                created_by=user_id
            )
            
            self.db.add(payment)
            
            # Actualizar estado de la factura
            bill.paid_amount += payment_data.amount
            
            if bill.paid_amount >= bill.total_amount:
                bill.status = BillStatus.PAID
            elif bill.paid_amount > 0:
                bill.status = BillStatus.PARTIAL
            
            self.db.commit()
            self.db.refresh(payment)
            
            return payment
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error registrando pago: {str(e)}"
            )

    def list_payments(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        bill_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> BillPaymentList:
        """Listar pagos de facturas con filtros"""
        try:
            query = self.db.query(BillPayment).filter(BillPayment.tenant_id == tenant_id)
            if bill_id:
                # ensure bill belongs to tenant
                bill = self.db.query(Bill).filter(Bill.id == bill_id, Bill.tenant_id == tenant_id).first()
                if not bill:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")
                query = query.filter(BillPayment.bill_id == bill_id)
            if start_date:
                query = query.filter(BillPayment.payment_date >= start_date)
            if end_date:
                query = query.filter(BillPayment.payment_date <= end_date)

            total = query.count()
            payments = query.order_by(BillPayment.created_at.desc()).offset(offset).limit(limit).all()

            return BillPaymentList(items=payments, total=total, limit=limit, offset=offset)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error listando pagos: {str(e)}")


class DebitNoteService:
    """Servicio para gestión de notas débito"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_debit_note(
        self, 
        debit_note_data: DebitNoteCreate, 
        tenant_id: UUID, 
        user_id: UUID
    ) -> DebitNote:
        """Crear nueva nota débito"""
        try:
            # Verificar proveedor
            ProviderValidator(self.db).require_provider(debit_note_data.supplier_id, tenant_id)

            # Si hay bill_id, verificar que pertenezca al tenant y proveedor
            if debit_note_data.bill_id:
                bill = self.db.query(Bill).filter(
                    Bill.id == debit_note_data.bill_id,
                    Bill.tenant_id == tenant_id,
                    Bill.supplier_id == debit_note_data.supplier_id
                ).first()
                if not bill:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Factura no encontrada o no pertenece al proveedor especificado"
                    )

            # Crear nota débito
            debit_note = DebitNote(
                bill_id=debit_note_data.bill_id,
                supplier_id=debit_note_data.supplier_id,
                issue_date=debit_note_data.issue_date,
                notes=debit_note_data.notes,
                tenant_id=tenant_id,
                created_by=user_id
            )
            
            self.db.add(debit_note)
            self.db.flush()
            
            # Procesar ítems
            subtotal = Decimal('0')
            taxes_total = Decimal('0')
            
            for item_data in debit_note_data.items:
                # Si es quantity_adjustment, verificar producto
                if item_data.reason_type == DebitNoteReasonType.QUANTITY_ADJUSTMENT and item_data.product_id:
                    from app.modules.products.models import Product
                    product = self.db.query(Product).filter(
                        Product.id == item_data.product_id,
                        Product.tenant_id == tenant_id
                    ).first()
                    
                    if not product:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Producto {item_data.product_id} no encontrado"
                        )

                # Calcular línea según tipo de ajuste
                if item_data.reason_type == DebitNoteReasonType.QUANTITY_ADJUSTMENT:
                    line_subtotal = (item_data.quantity or Decimal('0')) * (item_data.unit_price or Decimal('0'))
                elif item_data.reason_type == DebitNoteReasonType.PRICE_ADJUSTMENT:
                    line_subtotal = item_data.unit_price or Decimal('0')
                else:  # SERVICE
                    line_subtotal = item_data.unit_price or Decimal('0')
                
                # TODO: Calcular impuestos
                line_taxes = {}
                line_taxes_amount = Decimal('0')
                line_total = line_subtotal + line_taxes_amount
                
                # Crear ítem
                debit_note_item = DebitNoteItem(
                    debit_note_id=debit_note.id,
                    product_id=item_data.product_id,
                    name=item_data.name,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price,
                    reason_type=item_data.reason_type,
                    line_subtotal=line_subtotal,
                    line_taxes=line_taxes,
                    line_total=line_total
                )
                
                self.db.add(debit_note_item)
                
                subtotal += line_subtotal
                taxes_total += line_taxes_amount
            
            # Actualizar totales
            debit_note.subtotal = subtotal
            debit_note.taxes_total = taxes_total
            debit_note.total_amount = subtotal + taxes_total
            
            # Si hay ajustes de cantidad, actualizar inventario
            self._update_inventory_for_debit_note(debit_note)
            
            self.db.commit()
            self.db.refresh(debit_note)
            
            return debit_note
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando nota débito: {str(e)}"
            )

    def _update_inventory_for_debit_note(self, debit_note: DebitNote):
        """Actualizar inventario para ajustes de cantidad en nota débito"""
        from app.modules.products.models import Stock, InventoryMovement
        
        for item in debit_note.items:
            if item.reason_type == DebitNoteReasonType.QUANTITY_ADJUSTMENT and item.product_id and item.quantity:
                # Buscar bill relacionada para obtener PDV
                if debit_note.bill_id:
                    bill = self.db.query(Bill).filter(Bill.id == debit_note.bill_id).first()
                    if bill:
                        pdv_id = bill.pdv_id
                    else:
                        continue  # Skip si no hay bill
                else:
                    # Sin bill asociada, no podemos determinar PDV - skip
                    continue
                
                # Actualizar stock
                stock = self.db.query(Stock).filter(
                    Stock.product_id == item.product_id,
                    Stock.pdv_id == pdv_id,
                    Stock.tenant_id == debit_note.tenant_id
                ).first()
                
                if not stock:
                    # Crear stock si no existe
                    stock = Stock(
                        product_id=item.product_id,
                        pdv_id=pdv_id,
                        tenant_id=debit_note.tenant_id,
                        quantity=0
                    )
                    self.db.add(stock)
                    self.db.flush()
                
                # Incrementar stock (ajuste positivo)
                stock.quantity += int(item.quantity)
                
                # Crear movimiento de inventario
                movement = InventoryMovement(
                    product_id=item.product_id,
                    pdv_id=pdv_id,
                    tenant_id=debit_note.tenant_id,
                    movement_type="IN",
                    quantity=int(item.quantity),
                    reference=str(debit_note.id),
                    notes=f"Nota débito #{debit_note.id} - Ajuste cantidad",
                    created_by=debit_note.created_by
                )
                
                self.db.add(movement)

    def get_debit_notes(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        supplier_id: Optional[UUID] = None,
        bill_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> DebitNoteList:
        """Listar notas débito con filtros"""
        try:
            query = self.db.query(DebitNote).filter(DebitNote.tenant_id == tenant_id)
            
            if supplier_id:
                query = query.filter(DebitNote.supplier_id == supplier_id)
            if bill_id:
                query = query.filter(DebitNote.bill_id == bill_id)
            if start_date:
                query = query.filter(DebitNote.issue_date >= start_date)
            if end_date:
                query = query.filter(DebitNote.issue_date <= end_date)
            
            total = query.count()
            debit_notes = query.order_by(DebitNote.created_at.desc()).offset(offset).limit(limit).all()
            
            return DebitNoteList(
                items=debit_notes,
                total=total,
                limit=limit,
                offset=offset
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando notas débito: {str(e)}"
            )

    def get_debit_note_by_id(self, debit_note_id: UUID, tenant_id: UUID) -> DebitNote:
        """Obtener nota débito por ID"""
        debit_note = self.db.query(DebitNote).filter(
            DebitNote.id == debit_note_id,
            DebitNote.tenant_id == tenant_id
        ).first()
        
        if not debit_note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nota débito no encontrada"
            )
        
        return debit_note

    def void_debit_note(self, debit_note_id: UUID, reason: Optional[str], tenant_id: UUID) -> DebitNote:
        """Anular una nota débito. MVP: no revierte inventario"""
        try:
            debit_note = self.get_debit_note_by_id(debit_note_id, tenant_id)
            if debit_note.status == DebitNoteStatus.VOID:
                return debit_note
            
            debit_note.status = DebitNoteStatus.VOID
            if reason:
                note = (debit_note.notes or "").strip()
                debit_note.notes = f"{note}\n[VOID] {reason}".strip()
            
            self.db.commit()
            self.db.refresh(debit_note)
            return debit_note
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error anulando nota débito: {str(e)}"
            )
