from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, desc, func
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime

from app.modules.invoices.models import (
    Invoice, InvoiceLineItem, Customer, Payment, InvoiceSequence,
    InvoiceStatus, InvoiceType, PaymentMethod
)
from app.modules.invoices.schemas import (
    InvoiceCreate, InvoiceUpdate, CustomerCreate, CustomerUpdate, PaymentCreate,
    InvoiceFilters, StockValidation, InvoiceValidation, InvoiceTaxSummary, InvoiceTotals
)
from app.modules.products.models import Product, Stock, InventoryMovement, ProductTax, Tax
from app.modules.pdv.models import PDV


class CustomerService:
    def __init__(self, db: Session):
        self.db = db

    def create_customer(self, customer_data: CustomerCreate, company_id: str) -> Customer:
        """Crear un nuevo cliente"""
        try:
            # Validar documento único si se proporciona
            if customer_data.document:
                existing = self.db.query(Customer).filter(
                    Customer.tenant_id == company_id,
                    Customer.document == customer_data.document
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe un cliente con el documento '{customer_data.document}'"
                    )

            customer = Customer(
                **customer_data.model_dump(),
                tenant_id=company_id
            )
            
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)
            return customer
            
        except IntegrityError as e:
            self.db.rollback()
            if "uq_customer_tenant_document" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un cliente con el documento '{customer_data.document}'"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error de integridad: {str(e)}"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_customers(self, company_id: str, limit: int = 100, offset: int = 0, search: Optional[str] = None) -> dict:
        """Obtener lista de clientes con búsqueda opcional"""
        try:
            query = self.db.query(Customer).filter(Customer.tenant_id == company_id)
            
            if search:
                search_filter = or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.email.ilike(f"%{search}%"),
                    Customer.document.ilike(f"%{search}%")
                )
                query = query.filter(search_filter)
            
            total = query.count()
            customers = query.offset(offset).limit(limit).all()
            
            return {
                "customers": customers,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener clientes: {str(e)}"
            )

    def get_customer_by_id(self, customer_id: UUID, company_id: str) -> Customer:
        """Obtener cliente por ID"""
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == company_id
        ).first()
        
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )
        return customer

    def update_customer(self, customer_id: UUID, customer_update: CustomerUpdate, company_id: str) -> Customer:
        """Actualizar cliente"""
        try:
            customer = self.get_customer_by_id(customer_id, company_id)
            
            # Validar documento único si se está actualizando
            if customer_update.document and customer_update.document != customer.document:
                existing = self.db.query(Customer).filter(
                    Customer.tenant_id == company_id,
                    Customer.document == customer_update.document,
                    Customer.id != customer_id
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe otro cliente con el documento '{customer_update.document}'"
                    )
            
            # Actualizar campos
            for field, value in customer_update.model_dump(exclude_unset=True).items():
                if value is not None:
                    setattr(customer, field, value)
            
            self.db.commit()
            self.db.refresh(customer)
            return customer
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def delete_customer(self, customer_id: UUID, company_id: str) -> dict:
        """Eliminar cliente si no tiene facturas"""
        try:
            customer = self.get_customer_by_id(customer_id, company_id)
            
            # Verificar si tiene facturas
            invoice_count = self.db.query(Invoice).filter(
                Invoice.customer_id == customer_id
            ).count()
            
            if invoice_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede eliminar el cliente porque tiene {invoice_count} factura(s) asociada(s)"
                )
            
            self.db.delete(customer)
            self.db.commit()
            return {"message": "Cliente eliminado exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )


class InvoiceService:
    def __init__(self, db: Session):
        self.db = db

    def validate_invoice_data(self, invoice_data: InvoiceCreate, company_id: str) -> InvoiceValidation:
        """Validar datos de la factura antes de crearla"""
        errors = []
        warnings = []
        stock_validations = []
        
        try:
            # Validar PDV
            pdv = self.db.query(PDV).filter(
                PDV.id == invoice_data.pdv_id,
                PDV.tenant_id == company_id
            ).first()
            
            if not pdv:
                errors.append("El PDV especificado no existe o no pertenece a esta empresa")
            
            # Validar Cliente
            customer = self.db.query(Customer).filter(
                Customer.id == invoice_data.customer_id,
                Customer.tenant_id == company_id
            ).first()
            
            if not customer:
                errors.append("El cliente especificado no existe o no pertenece a esta empresa")
            
            # Validar productos y stock
            for item in invoice_data.items:
                product = self.db.query(Product).filter(
                    Product.id == item.product_id,
                    Product.tenant_id == company_id
                ).first()
                
                if not product:
                    errors.append(f"El producto {item.product_id} no existe o no pertenece a esta empresa")
                    continue
                
                # Validar stock solo si el status será 'open'
                if invoice_data.status == InvoiceStatus.OPEN:
                    stock = self.db.query(Stock).filter(
                        Stock.product_id == item.product_id,
                        Stock.pdv_id == invoice_data.pdv_id,
                        Stock.tenant_id == company_id
                    ).first()
                    
                    available_qty = stock.quantity if stock else 0
                    is_sufficient = available_qty >= item.quantity
                    
                    stock_validations.append(StockValidation(
                        product_id=item.product_id,
                        product_name=product.name,
                        requested_quantity=item.quantity,
                        available_quantity=available_qty,
                        is_sufficient=is_sufficient
                    ))
                    
                    if not is_sufficient:
                        warnings.append(
                            f"Stock insuficiente para {product.name}. "
                            f"Disponible: {available_qty}, Solicitado: {item.quantity}"
                        )
            
            return InvoiceValidation(
                is_valid=len(errors) == 0,
                stock_validations=stock_validations,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return InvoiceValidation(
                is_valid=False,
                stock_validations=[],
                errors=[f"Error en validación: {str(e)}"],
                warnings=[]
            )

    def calculate_invoice_totals(self, items: List[InvoiceLineItem], company_id: str) -> InvoiceTotals:
        """Calcular totales de la factura incluyendo impuestos"""
        subtotal = Decimal('0.00')
        taxes_summary = {}
        
        for item in items:
            # Subtotal
            item_subtotal = item.quantity * item.unit_price
            subtotal += item_subtotal
            item.line_subtotal = item_subtotal
            
            # Calcular impuestos del producto
            product_taxes = self.db.query(ProductTax).filter(
                ProductTax.product_id == item.product_id,
                ProductTax.tenant_id == company_id
            ).all()
            
            item_taxes = []
            for product_tax in product_taxes:
                tax = product_tax.tax
                tax_amount = item_subtotal * tax.rate
                
                item_taxes.append({
                    "tax_id": str(tax.id),
                    "tax_name": tax.name,
                    "tax_rate": float(tax.rate),
                    "taxable_amount": float(item_subtotal),
                    "tax_amount": float(tax_amount)
                })
                
                # Acumular en resumen
                tax_key = str(tax.id)
                if tax_key not in taxes_summary:
                    taxes_summary[tax_key] = InvoiceTaxSummary(
                        tax_id=tax.id,
                        tax_name=tax.name,
                        tax_rate=tax.rate,
                        taxable_amount=Decimal('0.00'),
                        tax_amount=Decimal('0.00')
                    )
                
                taxes_summary[tax_key].taxable_amount += item_subtotal
                taxes_summary[tax_key].tax_amount += tax_amount
            
            item.line_taxes = item_taxes
            item.line_total = item_subtotal + sum(Decimal(str(t["tax_amount"])) for t in item_taxes)
        
        taxes_total = sum(tax.tax_amount for tax in taxes_summary.values())
        
        return InvoiceTotals(
            subtotal=subtotal,
            taxes=list(taxes_summary.values()),
            taxes_total=taxes_total,
            total_amount=subtotal + taxes_total
        )

    def generate_invoice_number(self, pdv_id: UUID, company_id: str) -> str:
        """Generar número de factura secuencial por PDV"""
        try:
            # Buscar o crear secuencia para el PDV
            sequence = self.db.query(InvoiceSequence).filter(
                InvoiceSequence.pdv_id == pdv_id,
                InvoiceSequence.tenant_id == company_id
            ).first()
            
            if not sequence:
                sequence = InvoiceSequence(
                    pdv_id=pdv_id,
                    tenant_id=company_id,
                    current_number=0,
                    prefix="F-"
                )
                self.db.add(sequence)
                self.db.flush()
            
            # Incrementar número
            sequence.current_number += 1
            sequence.updated_at = datetime.utcnow()
            
            # Generar número formateado
            number = f"{sequence.prefix or 'F-'}{sequence.current_number:06d}"
            
            return number
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando número de factura: {str(e)}"
            )

    def create_invoice(self, invoice_data: InvoiceCreate, company_id: str, user_id: UUID) -> Invoice:
        """Crear nueva factura"""
        try:
            # Validar datos
            validation = self.validate_invoice_data(invoice_data, company_id)
            if not validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"errors": validation.errors, "warnings": validation.warnings}
                )
            
            # Generar número de factura
            invoice_number = self.generate_invoice_number(invoice_data.pdv_id, company_id)
            
            # Crear factura
            invoice = Invoice(
                tenant_id=company_id,
                pdv_id=invoice_data.pdv_id,
                customer_id=invoice_data.customer_id,
                created_by=user_id,
                number=invoice_number,
                type=InvoiceType.SALE,
                status=invoice_data.status,
                issue_date=invoice_data.issue_date,
                due_date=invoice_data.due_date,
                notes=invoice_data.notes
            )
            
            self.db.add(invoice)
            self.db.flush()
            
            # Crear line items
            line_items = []
            for item_data in invoice_data.items:
                product = self.db.query(Product).filter(
                    Product.id == item_data.product_id,
                    Product.tenant_id == company_id
                ).first()
                
                line_item = InvoiceLineItem(
                    invoice_id=invoice.id,
                    product_id=item_data.product_id,
                    name=product.name,
                    sku=product.sku,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price
                )
                line_items.append(line_item)
                self.db.add(line_item)
            
            self.db.flush()
            
            # Calcular totales
            totals = self.calculate_invoice_totals(line_items, company_id)
            invoice.subtotal = totals.subtotal
            invoice.taxes_total = totals.taxes_total
            invoice.total_amount = totals.total_amount
            
            # Si la factura está abierta, afectar inventario
            if invoice.status == InvoiceStatus.OPEN:
                self._update_inventory_for_invoice(invoice, line_items, company_id, user_id)
            
            self.db.commit()
            self.db.refresh(invoice)
            
            return invoice
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando factura: {str(e)}"
            )

    def _update_inventory_for_invoice(self, invoice: Invoice, line_items: List[InvoiceLineItem], 
                                    company_id: str, user_id: UUID):
        """Actualizar inventario cuando una factura pasa a estado 'open'"""
        for line_item in line_items:
            # Actualizar stock
            stock = self.db.query(Stock).filter(
                Stock.product_id == line_item.product_id,
                Stock.pdv_id == invoice.pdv_id,
                Stock.tenant_id == company_id
            ).first()
            
            if stock:
                stock.quantity -= line_item.quantity
            else:
                # Crear stock negativo si no existe
                stock = Stock(
                    product_id=line_item.product_id,
                    pdv_id=invoice.pdv_id,
                    tenant_id=company_id,
                    quantity=-line_item.quantity
                )
                self.db.add(stock)
            
            # Crear movimiento de inventario
            movement = InventoryMovement(
                product_id=line_item.product_id,
                pdv_id=invoice.pdv_id,
                tenant_id=company_id,
                quantity=-line_item.quantity,  # Negativo porque es salida
                movement_type="OUT",
                reference=f"Factura {invoice.number}",
                notes=f"Venta - Factura {invoice.number}",
                created_by=user_id
            )
            self.db.add(movement)

    def get_invoices(self, company_id: str, filters: InvoiceFilters, limit: int = 100, offset: int = 0) -> dict:
        """Obtener lista de facturas con filtros"""
        try:
            query = self.db.query(Invoice).options(
                selectinload(Invoice.customer),
                selectinload(Invoice.pdv)
            ).filter(Invoice.tenant_id == company_id)
            
            # Aplicar filtros
            if filters.status:
                query = query.filter(Invoice.status == filters.status)
            
            if filters.customer_id:
                query = query.filter(Invoice.customer_id == filters.customer_id)
            
            if filters.pdv_id:
                query = query.filter(Invoice.pdv_id == filters.pdv_id)
            
            if filters.date_from:
                query = query.filter(Invoice.issue_date >= filters.date_from)
            
            if filters.date_to:
                query = query.filter(Invoice.issue_date <= filters.date_to)
            
            if filters.search:
                search_filter = or_(
                    Invoice.number.ilike(f"%{filters.search}%"),
                    Invoice.notes.ilike(f"%{filters.search}%")
                )
                query = query.filter(search_filter)
            
            # Ordenar por fecha de creación descendente
            query = query.order_by(desc(Invoice.created_at))
            
            total = query.count()
            invoices = query.offset(offset).limit(limit).all()
            
            return {
                "invoices": invoices,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error obteniendo facturas: {str(e)}"
            )

    def get_invoice_by_id(self, invoice_id: UUID, company_id: str) -> Invoice:
        """Obtener factura por ID con detalles completos"""
        invoice = self.db.query(Invoice).options(
            selectinload(Invoice.customer),
            selectinload(Invoice.pdv),
            selectinload(Invoice.line_items),
            selectinload(Invoice.payments),
            selectinload(Invoice.created_by_user)
        ).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == company_id
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Factura no encontrada"
            )
        
        return invoice

    def add_payment(self, invoice_id: UUID, payment_data: PaymentCreate, company_id: str) -> Payment:
        """Agregar pago a una factura"""
        try:
            invoice = self.get_invoice_by_id(invoice_id, company_id)
            
            # Validar que la factura no esté anulada
            if invoice.status == InvoiceStatus.VOID:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pueden agregar pagos a facturas anuladas"
                )
            
            # Validar que no se exceda el saldo pendiente
            current_balance = invoice.balance_due
            if payment_data.amount > current_balance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El pago de ${payment_data.amount} excede el saldo pendiente de ${current_balance}"
                )
            
            # Crear pago
            payment = Payment(
                invoice_id=invoice_id,
                tenant_id=company_id,
                **payment_data.model_dump()
            )
            
            self.db.add(payment)
            
            # Actualizar estado de la factura si está completamente pagada
            new_paid_amount = invoice.paid_amount + payment_data.amount
            if new_paid_amount >= invoice.total_amount:
                invoice.status = InvoiceStatus.PAID
            
            self.db.commit()
            self.db.refresh(payment)
            
            return payment
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error agregando pago: {str(e)}"
            )

    def void_invoice(self, invoice_id: UUID, company_id: str) -> Invoice:
        """Anular factura"""
        try:
            invoice = self.get_invoice_by_id(invoice_id, company_id)
            
            # Validar que no esté pagada
            if invoice.status == InvoiceStatus.PAID:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pueden anular facturas que ya están pagadas"
                )
            
            # Validar que no esté ya anulada
            if invoice.status == InvoiceStatus.VOID:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La factura ya está anulada"
                )
            
            # Cambiar estado
            invoice.status = InvoiceStatus.VOID
            
            # En MVP no revertimos el inventario automáticamente
            # Esto se puede implementar en futuras versiones
            
            self.db.commit()
            self.db.refresh(invoice)
            
            return invoice
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error anulando factura: {str(e)}"
            )

    def get_invoices(
        self,
        tenant_id: UUID,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        customer_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None,
        status: Optional[str] = None,
        invoice_number: Optional[str] = None
    ):
        """Listar facturas con filtros"""
        try:
            from app.modules.invoices.schemas import InvoiceList
            
            query = self.db.query(Invoice).filter(Invoice.tenant_id == tenant_id)
            
            # Aplicar filtros
            if start_date:
                query = query.filter(Invoice.created_at >= start_date)
            if end_date:
                query = query.filter(Invoice.created_at <= end_date)
            if customer_id:
                query = query.filter(Invoice.customer_id == customer_id)
            if pdv_id:
                query = query.filter(Invoice.pdv_id == pdv_id)
            if status:
                query = query.filter(Invoice.status == status)
            if invoice_number:
                query = query.filter(Invoice.invoice_number.ilike(f"%{invoice_number}%"))
            
            # Contar total
            total = query.count()
            
            # Aplicar paginación y ordenar
            invoices = query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit).all()
            
            return InvoiceList(
                items=invoices,
                total=total,
                limit=limit,
                offset=offset
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando facturas: {str(e)}"
            )

    def get_invoice_payments(self, invoice_id: UUID, tenant_id: UUID):
        """Obtener pagos de una factura"""
        # Verificar que la factura existe y pertenece al tenant
        invoice = self.db.query(Invoice).filter(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id
        ).first()
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Factura no encontrada"
            )
        
        return self.db.query(Payment).filter(Payment.invoice_id == invoice_id).all()

    def get_sales_summary(
        self,
        tenant_id: UUID,
        start_date: date,
        end_date: date,
        pdv_id: Optional[UUID] = None
    ):
        """Generar resumen de ventas por período"""
        from app.modules.invoices.schemas import SalesSummary
        from sqlalchemy import func, extract
        
        try:
            query = self.db.query(Invoice).filter(
                Invoice.tenant_id == tenant_id,
                Invoice.created_at >= start_date,
                Invoice.created_at <= end_date
            )
            
            if pdv_id:
                query = query.filter(Invoice.pdv_id == pdv_id)
            
            invoices = query.all()
            
            # Calcular totales
            total_invoices = len(invoices)
            total_amount = sum(inv.total_amount for inv in invoices)
            total_tax = sum(inv.total_tax for inv in invoices)
            
            # Agrupar por estado
            pending_amount = sum(inv.total_amount for inv in invoices if inv.status == "pending")
            paid_amount = sum(inv.total_amount for inv in invoices if inv.status == "paid")
            cancelled_amount = sum(inv.total_amount for inv in invoices if inv.status == "cancelled")
            
            # Ventas diarias (simplificado para MVP)
            daily_sales = []
            current_date = start_date
            while current_date <= end_date:
                daily_invoices = [inv for inv in invoices if inv.created_at.date() == current_date]
                daily_sales.append({
                    "date": current_date.isoformat(),
                    "invoices": len(daily_invoices),
                    "amount": sum(inv.total_amount for inv in daily_invoices)
                })
                current_date = current_date.replace(day=current_date.day + 1)
            
            # Top productos (placeholder para MVP)
            top_products = []
            
            return SalesSummary(
                period_start=start_date,
                period_end=end_date,
                total_invoices=total_invoices,
                total_amount=total_amount,
                total_tax=total_tax,
                pending_amount=pending_amount,
                paid_amount=paid_amount,
                cancelled_amount=cancelled_amount,
                top_products=top_products,
                daily_sales=daily_sales
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando resumen: {str(e)}"
            )

    def get_next_invoice_number(self, pdv_id: UUID, tenant_id: UUID):
        """Obtener el siguiente número de factura para un PDV"""
        from app.modules.invoices.schemas import NextInvoiceNumber
        
        try:
            # Verificar que el PDV existe y pertenece al tenant
            from app.modules.pdv.models import PDV
            pdv = self.db.query(PDV).filter(
                PDV.id == pdv_id,
                PDV.tenant_id == tenant_id
            ).first()
            
            if not pdv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDV no encontrado"
                )
            
            # Obtener secuencia de facturación
            sequence = self.db.query(InvoiceSequence).filter(
                InvoiceSequence.pdv_id == pdv_id,
                InvoiceSequence.tenant_id == tenant_id
            ).first()
            
            if not sequence:
                # Crear nueva secuencia
                sequence = InvoiceSequence(
                    pdv_id=pdv_id,
                    tenant_id=tenant_id,
                    prefix="FV",
                    current_number=0
                )
                self.db.add(sequence)
                self.db.commit()
                self.db.refresh(sequence)
            
            next_number = sequence.current_number + 1
            next_invoice_number = f"{sequence.prefix}{next_number:06d}"
            
            return NextInvoiceNumber(
                next_number=next_invoice_number,
                prefix=sequence.prefix,
                current_sequence=next_number
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error obteniendo siguiente número: {str(e)}"
            )