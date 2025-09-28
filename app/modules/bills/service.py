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
    Supplier, PurchaseOrder, POItem, Bill, BillLineItem, 
    BillPayment, DebitNote, DebitNoteItem,
    PurchaseOrderStatus, BillStatus, DebitNoteStatus, DebitNoteReasonType
)
from app.modules.bills.schemas import (
    SupplierCreate, SupplierUpdate, SupplierList,
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderList, PurchaseOrderDetail,
    BillCreate, BillUpdate, BillList, BillDetail,
    BillPaymentCreate, BillPaymentList,
    DebitNoteCreate, DebitNoteUpdate, DebitNoteList, DebitNoteDetail,
    ConvertPOToBillRequest
)


class SupplierService:
    """Servicio para gestión de proveedores"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_supplier(self, supplier_data: SupplierCreate, company_id: UUID) -> Supplier:
        """Crear un nuevo proveedor"""
        try:
            # Verificar documento único si se proporciona
            if supplier_data.document:
                existing = self.db.query(Supplier).filter(
                    Supplier.company_id == company_id,
                    Supplier.document == supplier_data.document
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya existe un proveedor con este documento"
                    )

            supplier = Supplier(
                **supplier_data.dict(),
                company_id=company_id
            )
            
            self.db.add(supplier)
            self.db.commit()
            self.db.refresh(supplier)
            
            return supplier
            
        except HTTPException:
            raise
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Error de integridad: documento duplicado"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando proveedor: {str(e)}"
            )

    def get_suppliers(
        self, 
        company_id: UUID, 
        limit: int = 100, 
        offset: int = 0,
        search: Optional[str] = None
    ) -> SupplierList:
        """Listar proveedores con búsqueda opcional"""
        try:
            query = self.db.query(Supplier).filter(Supplier.company_id == company_id)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Supplier.name.ilike(search_term),
                        Supplier.document.ilike(search_term),
                        Supplier.email.ilike(search_term)
                    )
                )
            
            total = query.count()
            suppliers = query.offset(offset).limit(limit).all()
            
            return SupplierList(
                items=suppliers,
                total=total,
                limit=limit,
                offset=offset
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando proveedores: {str(e)}"
            )

    def get_supplier_by_id(self, supplier_id: UUID, company_id: UUID) -> Supplier:
        """Obtener proveedor por ID"""
        supplier = self.db.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.company_id == company_id
        ).first()
        
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proveedor no encontrado"
            )
        
        return supplier

    def update_supplier(
        self, 
        supplier_id: UUID, 
        supplier_update: SupplierUpdate, 
        company_id: UUID
    ) -> Supplier:
        """Actualizar proveedor"""
        try:
            supplier = self.get_supplier_by_id(supplier_id, company_id)
            
            # Verificar documento único si se actualiza
            if supplier_update.document and supplier_update.document != supplier.document:
                existing = self.db.query(Supplier).filter(
                    Supplier.company_id == company_id,
                    Supplier.document == supplier_update.document,
                    Supplier.id != supplier_id
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya existe otro proveedor con este documento"
                    )
            
            # Actualizar campos
            update_data = supplier_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(supplier, field, value)
            
            self.db.commit()
            self.db.refresh(supplier)
            
            return supplier
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error actualizando proveedor: {str(e)}"
            )

    def delete_supplier(self, supplier_id: UUID, company_id: UUID) -> Dict[str, str]:
        """Eliminar proveedor si no tiene facturas asociadas"""
        try:
            supplier = self.get_supplier_by_id(supplier_id, company_id)
            
            # Verificar que no tenga facturas
            bill_count = self.db.query(Bill).filter(Bill.supplier_id == supplier_id).count()
            if bill_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede eliminar el proveedor porque tiene {bill_count} factura(s) asociada(s)"
                )
            
            # Verificar que no tenga órdenes de compra
            po_count = self.db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == supplier_id).count()
            if po_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede eliminar el proveedor porque tiene {po_count} orden(es) de compra"
                )
            
            self.db.delete(supplier)
            self.db.commit()
            
            return {"message": "Proveedor eliminado exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error eliminando proveedor: {str(e)}"
            )


class PurchaseOrderService:
    """Servicio para gestión de órdenes de compra"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_purchase_order(
        self, 
        po_data: PurchaseOrderCreate, 
        company_id: UUID, 
        user_id: UUID
    ) -> PurchaseOrder:
        """Crear nueva orden de compra"""
        try:
            # Verificar que el proveedor existe
            supplier = self.db.query(Supplier).filter(
                Supplier.id == po_data.supplier_id,
                Supplier.company_id == company_id
            ).first()
            
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Proveedor no encontrado"
                )

            # Verificar que el PDV existe
            from app.modules.pdv.models import PDV
            pdv = self.db.query(PDV).filter(
                PDV.id == po_data.pdv_id,
                PDV.tenant_id == company_id
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
                company_id=company_id,
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
                    Product.tenant_id == company_id
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
        company_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[PurchaseOrderStatus] = None,
        supplier_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None
    ) -> PurchaseOrderList:
        """Listar órdenes de compra con filtros"""
        try:
            query = self.db.query(PurchaseOrder).filter(PurchaseOrder.company_id == company_id)
            
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

    def get_purchase_order_by_id(self, po_id: UUID, company_id: UUID) -> PurchaseOrder:
        """Obtener orden de compra por ID con detalles"""
        po = self.db.query(PurchaseOrder).filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.company_id == company_id
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
        company_id: UUID,
        user_id: UUID
    ) -> Bill:
        """Convertir orden de compra a factura"""
        try:
            # Obtener orden de compra
            po = self.get_purchase_order_by_id(po_id, company_id)
            
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
            
            bill = bill_service.create_bill(bill_data, company_id, user_id)
            
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


class BillService:
    """Servicio para gestión de facturas de proveedor"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_bill(self, bill_data: BillCreate, company_id: UUID, user_id: UUID) -> Bill:
        """Crear nueva factura de proveedor"""
        try:
            # Verificar proveedor
            supplier = self.db.query(Supplier).filter(
                Supplier.id == bill_data.supplier_id,
                Supplier.company_id == company_id
            ).first()
            
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Proveedor no encontrado"
                )

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
                company_id=company_id,
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
                    Product.tenant_id == company_id
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
                self._update_inventory_for_bill(bill, "IN")
            
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
                Stock.tenant_id == bill.company_id
            ).first()
            
            if not stock:
                # Crear stock si no existe
                stock = Stock(
                    product_id=item.product_id,
                    pdv_id=bill.pdv_id,
                    tenant_id=bill.company_id,
                    quantity=Decimal('0')
                )
                self.db.add(stock)
                self.db.flush()
            
            # Incrementar stock
            stock.quantity += item.quantity
            
            # Crear movimiento de inventario
            movement = InventoryMovement(
                product_id=item.product_id,
                pdv_id=bill.pdv_id,
                tenant_id=bill.company_id,
                type=movement_type,
                quantity=item.quantity,
                reference_type="bill",
                reference_id=str(bill.id),
                notes=f"Factura de compra #{bill.number}"
            )
            
            self.db.add(movement)

    def get_bills(
        self,
        company_id: UUID,
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
            query = self.db.query(Bill).filter(Bill.company_id == company_id)
            
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

    def get_bill_by_id(self, bill_id: UUID, company_id: UUID) -> Bill:
        """Obtener factura por ID"""
        bill = self.db.query(Bill).filter(
            Bill.id == bill_id,
            Bill.company_id == company_id
        ).first()
        
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Factura no encontrada"
            )
        
        return bill


class BillPaymentService:
    """Servicio para gestión de pagos de facturas"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_payment(
        self, 
        bill_id: UUID, 
        payment_data: BillPaymentCreate, 
        company_id: UUID, 
        user_id: UUID
    ) -> BillPayment:
        """Registrar pago de factura"""
        try:
            # Verificar factura
            bill_service = BillService(self.db)
            bill = bill_service.get_bill_by_id(bill_id, company_id)
            
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
                company_id=company_id,
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