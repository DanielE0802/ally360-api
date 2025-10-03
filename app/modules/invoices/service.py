from app.modules.invoices.schemas import TopProduct, TopProductsResponse, SalesComparison, PDVSales, PDVSalesResponse
from sqlalchemy import select, func, cast, String, and_
from datetime import date, timedelta
async def get_top_products(db, tenant_id: str, period: str = "month") -> TopProductsResponse:
    """Return top-selling products for the tenant in the given period."""
    # Example: group by product, sum quantity and amount
    from app.modules.invoices.models import Invoice, InvoiceItem
    from app.modules.products.models import Product
    today = date.today()
    if period == "day":
        start = today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
    else:
        start = today.replace(day=1)
    query = (
        select(
            Product.id,
            Product.name,
            Product.sku,
            func.sum(InvoiceItem.quantity).label("total_quantity"),
            func.sum(InvoiceItem.total).label("total_amount")
        )
        .join(InvoiceItem, InvoiceItem.product_id == Product.id)
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.date >= start,
            Invoice.date <= today
        )
        .group_by(Product.id, Product.name, Product.sku)
        .order_by(func.sum(InvoiceItem.quantity).desc())
        .limit(10)
    )
    result = await db.execute(query)
    products = []
    for pid, name, sku, qty, amount in result.fetchall():
        products.append(TopProduct(
            product_id=str(pid),
            product_name=name,
            sku=sku,
            total_quantity=qty,
            total_amount=str(amount)
        ))
    return TopProductsResponse(products=products, period=period)

async def get_sales_comparison(db, tenant_id: str) -> SalesComparison:
    """Return sales comparison today vs yesterday for the tenant."""
    from app.modules.invoices.models import Invoice
    today = date.today()
    yesterday = today - timedelta(days=1)
    # Sum total for today
    q_today = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.tenant_id == tenant_id,
        Invoice.date == today
    )
    # Sum total for yesterday
    q_yesterday = select(func.coalesce(func.sum(Invoice.total), 0)).where(
        Invoice.tenant_id == tenant_id,
        Invoice.date == yesterday
    )
    res_today = await db.execute(q_today)
    res_yesterday = await db.execute(q_yesterday)
    total_today = res_today.scalar()
    total_yesterday = res_yesterday.scalar()
    pct = ((total_today - total_yesterday) / total_yesterday * 100) if total_yesterday else 100.0 if total_today else 0.0
    amt = total_today - total_yesterday
    return SalesComparison(
        today={"date": str(today), "total": str(total_today)},
        yesterday={"date": str(yesterday), "total": str(total_yesterday)},
        percentage_change=pct,
        amount_change=str(amt)
    )

async def get_sales_by_pdv(db, tenant_id: str, period: str = "month") -> PDVSalesResponse:
    """Return sales grouped by PDV (point of sale) for chart comparison."""
    from app.modules.invoices.models import Invoice
    from app.modules.pdv.models import PDV
    today = date.today()
    if period == "day":
        start = today
    elif period == "week":
        start = today - timedelta(days=today.weekday())
    else:
        start = today.replace(day=1)
    
    query = (
        select(
            PDV.id,
            PDV.name,
            func.coalesce(func.sum(Invoice.total), 0).label("total_sales"),
            func.count(Invoice.id).label("total_invoices")
        )
        .outerjoin(Invoice, and_(Invoice.pdv_id == PDV.id, Invoice.date >= start, Invoice.date <= today, Invoice.tenant_id == tenant_id))
        .where(PDV.tenant_id == tenant_id)
        .group_by(PDV.id, PDV.name)
        .order_by(func.sum(Invoice.total).desc())
    )
    result = await db.execute(query)
    sales_by_pdv = []
    total_amount = 0
    for pdv_id, pdv_name, total_sales, total_invoices in result.fetchall():
        sales_by_pdv.append(PDVSales(
            pdv_id=str(pdv_id),
            pdv_name=pdv_name,
            total_sales=str(total_sales),
            total_invoices=total_invoices or 0
        ))
        total_amount += total_sales or 0
    
    return PDVSalesResponse(
        sales_by_pdv=sales_by_pdv,
        period=period,
        total_amount=str(total_amount)
    )
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, desc, func
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime
import logging

from app.modules.invoices.models import (
    Invoice, InvoiceLineItem, Payment, InvoiceSequence,
    InvoiceStatus, InvoiceType, PaymentMethod
)
from app.modules.invoices.schemas import (
    InvoiceCreate, InvoiceUpdate, PaymentCreate,
    InvoiceFilters, StockValidation, InvoiceValidation, InvoiceTaxSummary, InvoiceTotals,
    InvoicesMonthlySummary, MonthlyStatusMetrics
)
from app.modules.products.models import Product, Stock, InventoryMovement, ProductTax, Tax
from app.modules.pdv.models import PDV

logger = logging.getLogger(__name__)


## CustomerService removed in favor of Contacts module


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
            
            # Validar Cliente (Contact con tipo client)
            from app.modules.contacts.models import Contact
            customer = self.db.query(Contact).filter(
                Contact.id == invoice_data.customer_id,
                Contact.tenant_id == company_id,
                Contact.deleted_at.is_(None)
            ).first()

            if not customer or (customer.type and 'client' not in customer.type):
                errors.append("El cliente especificado no existe, no pertenece a esta empresa o no es de tipo 'client'")
            
            # Ahora los enums coinciden, podemos usar directamente el valor
            incoming_status = invoice_data.status

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
                if incoming_status == InvoiceStatus.OPEN:
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
        taxes_total = Decimal('0.00')
        taxes_summary: Dict[str, InvoiceTaxSummary] = {}

        for item in items:
            # Asegurar que los campos requeridos estén presentes
            if item.line_subtotal is None:
                try:
                    item.line_subtotal = Decimal(item.quantity) * Decimal(item.unit_price)
                except Exception:
                    item.line_subtotal = Decimal('0.00')

            # Si no hay impuestos definidos, line_total = line_subtotal
            line_taxes_amount = Decimal('0.00')
            if item.line_taxes:
                try:
                    for t in item.line_taxes:
                        # t puede venir como dict con llaves: tax_id, tax_name, tax_rate, tax_amount
                        tax_amount = Decimal(str(t.get("tax_amount", 0)))
                        line_taxes_amount += tax_amount

                        tax_key = str(t.get("tax_id") or t.get("tax_name"))
                        if tax_key not in taxes_summary:
                            taxes_summary[tax_key] = InvoiceTaxSummary(
                                tax_id=t.get("tax_id"),
                                tax_name=t.get("tax_name"),
                                tax_rate=Decimal(str(t.get("tax_rate", 0))),
                                taxable_amount=Decimal('0.00'),
                                tax_amount=Decimal('0.00')
                            )
                        taxes_summary[tax_key].taxable_amount += Decimal(item.line_subtotal)
                        taxes_summary[tax_key].tax_amount += tax_amount
                except Exception:
                    # Si hay problemas con el JSON de impuestos, ignoramos para no romper la creación
                    line_taxes_amount = Decimal('0.00')

            if item.line_total is None:
                item.line_total = Decimal(item.line_subtotal) + line_taxes_amount

            subtotal += Decimal(item.line_subtotal)
            taxes_total += line_taxes_amount

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
            
            # Mapear status del schema (string) al Enum del modelo  
            if invoice_data.status is not None:
                # invoice_data.status es un string Enum de Pydantic, necesitamos el Enum SQLAlchemy
                if hasattr(invoice_data.status, 'value'):
                    # Si es un Pydantic Enum, obtener el valor
                    status_str = invoice_data.status.value
                else:
                    # Si es un string directo
                    status_str = str(invoice_data.status)
                
                # Mapear al enum del modelo
                status_value = InvoiceStatus(status_str)
            else:
                status_value = InvoiceStatus.DRAFT

            # Crear factura
            invoice = Invoice(
                tenant_id=company_id,
                pdv_id=invoice_data.pdv_id,
                customer_id=invoice_data.customer_id,
                created_by=user_id,
                number=invoice_number,
                type=InvoiceType.SALE,
                status=status_value,
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
                
                # Calcular subtotales antes de agregar para cumplir NOT NULL
                try:
                    item_subtotal = Decimal(item_data.quantity) * Decimal(item_data.unit_price)
                except Exception:
                    item_subtotal = Decimal('0.00')

                line_item = InvoiceLineItem(
                    invoice_id=invoice.id,
                    product_id=item_data.product_id,
                    name=product.name,
                    sku=product.sku,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price,
                    line_subtotal=item_subtotal,
                    line_total=item_subtotal,  # Sin impuestos por ahora
                    line_taxes=[]  # Se puede poblar en el futuro con ProductTax
                )
                line_items.append(line_item)
                self.db.add(line_item)
            
            
            # Calcular totales
            totals = self.calculate_invoice_totals(line_items, company_id)
            invoice.subtotal = totals.subtotal
            invoice.taxes_total = totals.taxes_total
            invoice.total_amount = totals.total_amount
            
            # Debug: log del status actual
            logger.info(f"Invoice status before inventory check: {invoice.status} (type: {type(invoice.status)})")
            logger.info(f"InvoiceStatus.OPEN value: {InvoiceStatus.OPEN} (type: {type(InvoiceStatus.OPEN)})")
            logger.info(f"Status comparison result: {invoice.status == InvoiceStatus.OPEN}")
            
            # Si la factura está abierta, afectar inventario
            if invoice.status == InvoiceStatus.OPEN:
                logger.info(f"Creating inventory movements for invoice {invoice.number}")
                self._update_inventory_for_invoice(invoice, line_items, company_id, user_id)
            else:
                logger.info(f"Skipping inventory movements - invoice status is {invoice.status}")
            
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
        logger.info(f"Starting inventory update for invoice {invoice.number} with {len(line_items)} line items")
        
        for line_item in line_items:
            logger.info(f"Processing line item: product_id={line_item.product_id}, quantity={line_item.quantity}")
            
            # Actualizar stock
            stock = self.db.query(Stock).filter(
                Stock.product_id == line_item.product_id,
                Stock.pdv_id == invoice.pdv_id,
                Stock.tenant_id == company_id
            ).first()
            
            if stock:
                old_quantity = stock.quantity
                stock.quantity -= line_item.quantity
                logger.info(f"Updated stock for product {line_item.product_id}: {old_quantity} -> {stock.quantity}")
            else:
                # Crear stock negativo si no existe
                stock = Stock(
                    product_id=line_item.product_id,
                    pdv_id=invoice.pdv_id,
                    tenant_id=company_id,
                    quantity=-line_item.quantity
                )
                self.db.add(stock)
                logger.info(f"Created new stock entry for product {line_item.product_id}: quantity={-line_item.quantity}")
            
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
            logger.info(f"Created inventory movement: product_id={line_item.product_id}, quantity={-line_item.quantity}")
            
        logger.info(f"Completed inventory update for invoice {invoice.number}")

    def get_invoices(self, company_id: str, filters: InvoiceFilters, limit: int = 100, offset: int = 0) -> dict:
        """Obtener lista de facturas con filtros"""
        try:
            query = self.db.query(Invoice).options(
                selectinload(Invoice.pdv),
                selectinload(Invoice.customer)
            ).filter(Invoice.tenant_id == company_id)
            
            # Aplicar filtros
            if filters.status:
                # Ahora los enums coinciden, podemos usar directamente el valor
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

            # Enriquecer con customer_name para las respuestas
            for inv in invoices:
                try:
                    # setattr para que Pydantic lo mapee como atributo calculado
                    cust = getattr(inv, 'customer', None)
                    if cust is not None and getattr(cust, 'name', None):
                        setattr(inv, 'customer_name', cust.name)
                    if cust is not None and getattr(cust, 'email', None):
                        setattr(inv, 'customer_email', cust.email)
                except Exception:
                    pass

            # Conteos por estado basados en los mismos filtros (excepto el estado específico si ya está aplicado)
            counts_by_status = []
            from app.modules.invoices.schemas import InvoiceStatus as InvoiceStatusSchema
            status_values = [InvoiceStatus.DRAFT, InvoiceStatus.OPEN, InvoiceStatus.PAID, InvoiceStatus.VOID]
            for st in status_values:
                q_status = query
                if filters.status and filters.status != st:
                    # Si ya filtramos por estado distinto, este conteo no aplica al conjunto actual
                    count = 0
                else:
                    # Volvemos a aplicar todos los filtros excepto el estado (lo fijamos al de iteración)
                    base_q = self.db.query(Invoice).filter(Invoice.tenant_id == company_id)
                    if filters.customer_id:
                        base_q = base_q.filter(Invoice.customer_id == filters.customer_id)
                    if filters.pdv_id:
                        base_q = base_q.filter(Invoice.pdv_id == filters.pdv_id)
                    if filters.date_from:
                        base_q = base_q.filter(Invoice.issue_date >= filters.date_from)
                    if filters.date_to:
                        base_q = base_q.filter(Invoice.issue_date <= filters.date_to)
                    if filters.search:
                        base_q = base_q.filter(or_(
                            Invoice.number.ilike(f"%{filters.search}%"),
                            Invoice.notes.ilike(f"%{filters.search}%")
                        ))
                    count = base_q.filter(Invoice.status == st).count()
                counts_by_status.append({"status": st, "count": count})

            return {
                "invoices": invoices,
                "total": total,
                "limit": limit,
                "offset": offset,
                "applied_filters": filters,
                "counts_by_status": counts_by_status
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error obteniendo facturas: {str(e)}"
            )

    def get_invoice_by_id(self, invoice_id: UUID, company_id: str) -> Invoice:
        """Obtener factura por ID con detalles completos"""
        invoice = self.db.query(Invoice).options(
            selectinload(Invoice.pdv),
            selectinload(Invoice.customer),
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

    def add_payment(self, invoice_id: UUID, payment_data: PaymentCreate, company_id: str, user_id: UUID) -> Payment:
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
            # Mapear datos de pago y convertir enum si es necesario
            payment_dict = payment_data.model_dump()
            logger.info(f"Original payment data: {payment_dict}")
            
            # Convertir PaymentMethod string a enum SQLAlchemy si es necesario
            if 'method' in payment_dict:
                method_value = payment_dict['method']
                logger.info(f"Payment method before conversion: {method_value} (type: {type(method_value)})")
                
                if hasattr(method_value, 'value'):
                    # Si es un Pydantic Enum, obtener el valor string
                    method_str = method_value.value
                else:
                    # Si es un string directo
                    method_str = str(method_value)
                
                # Convertir a enum SQLAlchemy
                from app.modules.invoices.models import PaymentMethod as ModelPaymentMethod
                payment_dict['method'] = ModelPaymentMethod(method_str)
                logger.info(f"Payment method after conversion: {payment_dict['method']} (type: {type(payment_dict['method'])})")
            
            payment = Payment(
                invoice_id=invoice_id,
                tenant_id=company_id,
                created_by=user_id,
                **payment_dict
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

    def cancel_invoice(self, invoice_id: UUID, reason: str, company_id: str) -> Invoice:
        """
        Cancelar factura con reversión completa de inventario
        
        Args:
            invoice_id: ID de la factura a cancelar
            reason: Motivo de la cancelación  
            company_id: ID de la empresa
            
        Returns:
            Invoice cancelada
        """
        try:
            invoice = self.get_invoice_by_id(invoice_id, company_id)
            
            # Validar que no esté pagada
            if invoice.status == InvoiceStatus.PAID:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se pueden cancelar facturas que ya están pagadas"
                )
            
            # Validar que no esté ya anulada/cancelada
            if invoice.status == InvoiceStatus.VOID:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La factura ya está cancelada"
                )
            
            logger.info(f"Canceling invoice {invoice.number} - Reason: {reason}")
            
            # Si la factura estaba abierta (OPEN), revertir movimientos de inventario
            if invoice.status == InvoiceStatus.OPEN:
                logger.info(f"Reverting inventory movements for invoice {invoice.number}")
                self._revert_inventory_for_invoice(invoice, company_id)
            
            # Cambiar estado a anulada/cancelada
            old_status = invoice.status
            invoice.status = InvoiceStatus.VOID
            
            # Agregar nota de cancelación
            if invoice.notes:
                invoice.notes += f"\n\n[CANCELADA] {reason}"
            else:
                invoice.notes = f"[CANCELADA] {reason}"
            
            logger.info(f"Invoice {invoice.number} status changed from {old_status} to {invoice.status}")
            
            self.db.commit()
            self.db.refresh(invoice)
            
            return invoice
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error canceling invoice {invoice_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error cancelando factura: {str(e)}"
            )

    def _revert_inventory_for_invoice(self, invoice: Invoice, company_id: str):
        """
        Revertir movimientos de inventario para una factura cancelada
        
        Args:
            invoice: Factura a revertir
            company_id: ID de la empresa
        """
        logger.info(f"Starting inventory reversion for invoice {invoice.number}")
        
        for line_item in invoice.line_items:
            logger.info(f"Reverting inventory for product {line_item.product_id}, quantity: {line_item.quantity}")
            
            # Encontrar y actualizar stock
            stock = self.db.query(Stock).filter(
                Stock.product_id == line_item.product_id,
                Stock.pdv_id == invoice.pdv_id,
                Stock.tenant_id == company_id
            ).first()
            
            if stock:
                old_quantity = stock.quantity
                stock.quantity += line_item.quantity  # Sumar de vuelta (revertir la resta)
                logger.info(f"Reverted stock for product {line_item.product_id}: {old_quantity} -> {stock.quantity}")
            else:
                # Si no existe stock, crear entrada positiva
                stock = Stock(
                    product_id=line_item.product_id,
                    pdv_id=invoice.pdv_id,
                    tenant_id=company_id,
                    quantity=line_item.quantity
                )
                self.db.add(stock)
                logger.info(f"Created new stock entry for product {line_item.product_id}: quantity={line_item.quantity}")
            
            # Crear movimiento de inventario de reversión
            movement = InventoryMovement(
                product_id=line_item.product_id,
                pdv_id=invoice.pdv_id,
                tenant_id=company_id,
                quantity=line_item.quantity,  # Positivo porque es entrada (reversión)
                movement_type="IN",  # Entrada
                reference=f"Cancelación Factura {invoice.number}",
                notes=f"Reversión de venta - Factura {invoice.number} cancelada",
                created_by=invoice.created_by
            )
            self.db.add(movement)
            logger.info(f"Created reversal inventory movement: product_id={line_item.product_id}, quantity={line_item.quantity}")
        
        logger.info(f"Completed inventory reversion for invoice {invoice.number}")

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

    # keep single get_invoices implementation above

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
    # 'func' is already imported at module level; 'extract' not used
        
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
            total_tax = sum(inv.taxes_total for inv in invoices)
            
            # Agrupar por estado
            pending_amount = sum(inv.total_amount for inv in invoices if inv.status == InvoiceStatus.OPEN)
            paid_amount = sum(inv.total_amount for inv in invoices if inv.status == InvoiceStatus.PAID)
            cancelled_amount = sum(inv.total_amount for inv in invoices if inv.status == InvoiceStatus.VOID)
            
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

    def send_invoice_email(
        self, 
        invoice_id: UUID, 
        to_email: str, 
        pdf_content: bytes, 
        pdf_filename: str,
        company_id: str,
        custom_message: Optional[str] = None,
        subject: Optional[str] = None
    ) -> dict:
        """
        Enviar factura por email con PDF adjunto usando Celery.
        
        Args:
            invoice_id: ID de la factura
            to_email: Email del destinatario  
            pdf_content: Contenido del PDF en bytes
            pdf_filename: Nombre del archivo PDF
            company_id: ID de la empresa
            custom_message: Mensaje personalizado opcional
            subject: Asunto personalizado opcional
            
        Returns:
            dict con información del envío
        """
        try:
            # Obtener datos de la factura
            invoice = self.get_invoice_by_id(invoice_id, company_id)
            
            # Obtener datos de la empresa
            from app.modules.company.models import Company
            company = self.db.query(Company).filter(Company.id == company_id).first()
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Empresa no encontrada"
                )
            
            # Preparar datos para el template
            invoice_data = {
                "number": invoice.number,
                "issue_date": invoice.issue_date.strftime("%d/%m/%Y") if invoice.issue_date else "",
                "due_date": invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else None,
                "total_amount": float(invoice.total_amount),
                "balance_due": float(invoice.balance_due),
                "customer_name": getattr(invoice.customer, 'name', 'Cliente') if invoice.customer else 'Cliente',
                "payment_url": None  # Se puede implementar luego para ver factura online
            }
            
            company_data = {
                "name": company.name,
                "phone": getattr(company, 'phone_number', None),
                "email": None  # El modelo Company no tiene email por ahora
            }
            
            # Importar y lanzar tarea de Celery
            from app.modules.email.tasks import send_invoice_email_task
            import base64
            
            # Convertir bytes a base64 para serialización JSON
            pdf_content_b64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # Enviar de forma asíncrona
            task = send_invoice_email_task.delay(
                to_email=to_email,
                invoice_data=invoice_data,
                company_data=company_data,
                pdf_content_b64=pdf_content_b64,
                pdf_filename=pdf_filename,
                custom_message=custom_message,
                subject=subject
            )
            
            return {
                "status": "queued",
                "task_id": task.id,
                "message": f"Email de factura {invoice.number} programado para envío a {to_email}"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error enviando email: {str(e)}"
            )

    def get_monthly_status_summary(self, tenant_id: UUID, year: int, month: int) -> InvoicesMonthlySummary:
        """
        Resumen mensual por estado: total, open, paid, void.
        Retorna conteo de facturas y recaudado (suma de total_amount).
        """
        try:
            # Rango de fechas del mes
            from datetime import date
            if month < 1 or month > 12:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes inválido. Debe estar entre 1 y 12")
            month_start = date(year, month, 1)
            # calcular fin de mes: primer día del mes siguiente
            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)
            month_end = next_month

            # Base query por tenant y rango
            base_q = self.db.query(Invoice).filter(
                Invoice.tenant_id == tenant_id,
                Invoice.issue_date >= month_start,
                Invoice.issue_date < month_end
            )

            # Total (todas las facturas)
            total_count = base_q.count()
            total_amount = self.db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).filter(
                Invoice.tenant_id == tenant_id,
                Invoice.issue_date >= month_start,
                Invoice.issue_date < month_end
            ).scalar() or 0

            def status_metrics(status_value: InvoiceStatus) -> MonthlyStatusMetrics:
                q = base_q.filter(Invoice.status == status_value)
                count = q.count()
                amount = self.db.query(func.coalesce(func.sum(Invoice.total_amount), 0)).filter(
                    Invoice.tenant_id == tenant_id,
                    Invoice.issue_date >= month_start,
                    Invoice.issue_date < month_end,
                    Invoice.status == status_value
                ).scalar() or 0
                return MonthlyStatusMetrics(count=count, recaudado=amount)

            return InvoicesMonthlySummary(
                year=year,
                month=month,
                total=MonthlyStatusMetrics(count=total_count, recaudado=total_amount),
                open=status_metrics(InvoiceStatus.OPEN),
                paid=status_metrics(InvoiceStatus.PAID),
                void=status_metrics(InvoiceStatus.VOID)
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando resumen mensual: {str(e)}"
            )