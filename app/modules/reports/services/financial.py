"""
Financial Reports Service

Handles all financial reports including income vs expenses,
accounts receivable, and accounts payable reports.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, case

from .base import BaseReportService
from app.modules.invoices.models import Invoice, InvoiceStatus
from app.modules.bills.models import Bill, BillStatus
from app.modules.invoices.models import Payment, PaymentMethod
from app.modules.contacts.models import Contact


class FinancialReportService(BaseReportService):
    """Service for generating financial reports"""
    
    def get_income_vs_expenses(
        self,
        start_date: date,
        end_date: date,
        include_pending: bool = False,
        pdv_id: Optional[UUID] = None
    ) -> Dict:
        """
        Generate income vs expenses report.
        
        Returns total income from paid invoices vs total expenses from paid bills.
        """
        # Income from paid invoices
        income_query = self._get_base_invoice_query()
        
        if not include_pending:
            income_query = income_query.filter(Invoice.status == InvoiceStatus.PAID)
        else:
            income_query = income_query.filter(Invoice.status.in_([
                InvoiceStatus.PAID, InvoiceStatus.PARTIAL, InvoiceStatus.OPEN
            ]))
        
        # Apply date and PDV filters
        income_query = self._apply_date_filter(income_query, Invoice.issue_date, start_date, end_date)
        if pdv_id:
            income_query = self._apply_pdv_filter(income_query, Invoice.pdv_id, pdv_id)
        
        # Get income totals
        income_result = income_query.with_entities(
            func.count(Invoice.id).label('total_invoices'),
            func.sum(Invoice.total_amount).label('total_income')
        ).first()
        
        # Count pending invoices separately
        pending_invoices_query = self._get_base_invoice_query().filter(
            Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PARTIAL])
        )
        pending_invoices_query = self._apply_date_filter(
            pending_invoices_query, Invoice.issue_date, start_date, end_date
        )
        if pdv_id:
            pending_invoices_query = self._apply_pdv_filter(
                pending_invoices_query, Invoice.pdv_id, pdv_id
            )
        pending_invoices_count = pending_invoices_query.count()
        
        # Expenses from paid bills
        expenses_query = self._get_base_bill_query()
        
        if not include_pending:
            expenses_query = expenses_query.filter(Bill.status == BillStatus.PAID)
        else:
            expenses_query = expenses_query.filter(Bill.status.in_([
                BillStatus.PAID, BillStatus.PARTIAL, BillStatus.OPEN
            ]))
        
        # Apply date and PDV filters
        expenses_query = self._apply_date_filter(expenses_query, Bill.issue_date, start_date, end_date)
        if pdv_id:
            expenses_query = self._apply_pdv_filter(expenses_query, Bill.pdv_id, pdv_id)
        
        # Get expenses totals
        expenses_result = expenses_query.with_entities(
            func.count(Bill.id).label('total_bills'),
            func.sum(Bill.total_amount).label('total_expenses')
        ).first()
        
        # Count pending bills separately
        pending_bills_query = self._get_base_bill_query().filter(
            Bill.status.in_([BillStatus.OPEN, BillStatus.PARTIAL])
        )
        pending_bills_query = self._apply_date_filter(
            pending_bills_query, Bill.issue_date, start_date, end_date
        )
        if pdv_id:
            pending_bills_query = self._apply_pdv_filter(
                pending_bills_query, Bill.pdv_id, pdv_id
            )
        pending_bills_count = pending_bills_query.count()
        
        # Get income by payment method (only from payments)
        payment_methods_query = self.db.query(
            Payment.method,
            func.sum(Payment.amount).label('total_amount')
        ).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).filter(
            Invoice.tenant_id == self.tenant_id,
            Payment.payment_date.between(start_date, end_date)
        )
        
        if pdv_id:
            payment_methods_query = payment_methods_query.filter(Invoice.pdv_id == pdv_id)
        
        payment_methods = payment_methods_query.group_by(Payment.method).all()
        
        # Initialize payment method totals
        cash_income = Decimal('0')
        card_income = Decimal('0')
        transfer_income = Decimal('0')
        other_income = Decimal('0')
        
        for method_data in payment_methods:
            if method_data.method == PaymentMethod.CASH:
                cash_income = method_data.total_amount
            elif method_data.method == PaymentMethod.CARD:
                card_income = method_data.total_amount
            elif method_data.method == PaymentMethod.TRANSFER:
                transfer_income = method_data.total_amount
            else:
                other_income += method_data.total_amount
        
        # Calculate totals
        total_income = income_result.total_income or Decimal('0')
        total_expenses = expenses_result.total_expenses or Decimal('0')
        net_profit = total_income - total_expenses
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "paid_invoices_count": income_result.total_invoices or 0,
            "paid_bills_count": expenses_result.total_bills or 0,
            "pending_invoices_count": pending_invoices_count,
            "pending_bills_count": pending_bills_count,
            "cash_income": cash_income,
            "card_income": card_income,
            "transfer_income": transfer_income,
            "other_income": other_income
        }
    
    def get_accounts_receivable(
        self,
        as_of_date: date = None,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate accounts receivable report.
        
        Returns open and partially paid invoices with aging information.
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        # Query for open and partial invoices
        query = self.db.query(
            Invoice.id.label('invoice_id'),
            Invoice.number.label('invoice_number'),
            Invoice.customer_id,
            Contact.name.label('customer_name'),
            Invoice.issue_date,
            Invoice.due_date,
            Invoice.total_amount,
            func.coalesce(
                func.sum(Payment.amount), Decimal('0')
            ).label('paid_amount')
        ).outerjoin(
            Payment, Invoice.id == Payment.invoice_id
        ).join(
            Contact, Invoice.customer_id == Contact.id
        ).filter(
            Invoice.tenant_id == self.tenant_id,
            Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PARTIAL]),
            Invoice.issue_date <= as_of_date,
            Contact.deleted_at.is_(None)
        )
        
        # Apply PDV filter if specified
        if pdv_id:
            query = self._apply_pdv_filter(query, Invoice.pdv_id, pdv_id)
        
        # Group by invoice
        query = query.group_by(
            Invoice.id,
            Invoice.number,
            Invoice.customer_id,
            Contact.name,
            Invoice.issue_date,
            Invoice.due_date,
            Invoice.total_amount
        ).order_by(Invoice.due_date)
        
        # Get total count for pagination
        total_invoices = query.count()
        
        # Apply pagination
        invoices = query.offset(offset).limit(limit).all()
        
        # Convert to list with calculations
        invoices_list = []
        total_pending_amount = Decimal('0')
        overdue_invoices_count = 0
        overdue_amount = Decimal('0')
        current_amount = Decimal('0')
        
        for invoice in invoices:
            pending_amount = invoice.total_amount - invoice.paid_amount
            total_pending_amount += pending_amount
            
            # Calculate days overdue
            days_overdue = self._calculate_days_difference(invoice.due_date, as_of_date)
            is_overdue = days_overdue > 0
            
            if is_overdue:
                overdue_invoices_count += 1
                overdue_amount += pending_amount
            else:
                current_amount += pending_amount
            
            invoices_list.append({
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer_name,
                "issue_date": invoice.issue_date,
                "due_date": invoice.due_date,
                "total_amount": invoice.total_amount,
                "paid_amount": invoice.paid_amount,
                "pending_amount": pending_amount,
                "days_overdue": max(0, days_overdue),
                "is_overdue": is_overdue
            })
        
        return {
            "as_of_date": as_of_date,
            "invoices": invoices_list,
            "total_invoices": total_invoices,
            "total_pending_amount": total_pending_amount,
            "overdue_invoices_count": overdue_invoices_count,
            "overdue_amount": overdue_amount,
            "current_amount": current_amount
        }
    
    def get_accounts_payable(
        self,
        as_of_date: date = None,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate accounts payable report.
        
        Returns open and partially paid bills with aging information.
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        # Query for open and partial bills
        query = self.db.query(
            Bill.id.label('bill_id'),
            Bill.number.label('bill_number'),
            Bill.supplier_id,
            Contact.name.label('supplier_name'),
            Bill.issue_date,
            Bill.due_date,
            Bill.total_amount,
            func.coalesce(
                func.sum(Payment.amount), Decimal('0')
            ).label('paid_amount')
        ).outerjoin(
            Payment, Bill.id == Payment.bill_id
        ).join(
            Contact, Bill.supplier_id == Contact.id
        ).filter(
            Bill.tenant_id == self.tenant_id,
            Bill.status.in_([BillStatus.OPEN, BillStatus.PARTIAL]),
            Bill.issue_date <= as_of_date,
            Contact.deleted_at.is_(None)
        )
        
        # Apply PDV filter if specified
        if pdv_id:
            query = self._apply_pdv_filter(query, Bill.pdv_id, pdv_id)
        
        # Group by bill
        query = query.group_by(
            Bill.id,
            Bill.number,
            Bill.supplier_id,
            Contact.name,
            Bill.issue_date,
            Bill.due_date,
            Bill.total_amount
        ).order_by(Bill.due_date)
        
        # Get total count for pagination
        total_bills = query.count()
        
        # Apply pagination
        bills = query.offset(offset).limit(limit).all()
        
        # Convert to list with calculations
        bills_list = []
        total_pending_amount = Decimal('0')
        overdue_bills_count = 0
        overdue_amount = Decimal('0')
        current_amount = Decimal('0')
        
        for bill in bills:
            pending_amount = bill.total_amount - bill.paid_amount
            total_pending_amount += pending_amount
            
            # Calculate days overdue
            days_overdue = self._calculate_days_difference(bill.due_date, as_of_date)
            is_overdue = days_overdue > 0
            
            if is_overdue:
                overdue_bills_count += 1
                overdue_amount += pending_amount
            else:
                current_amount += pending_amount
            
            bills_list.append({
                "bill_id": bill.bill_id,
                "bill_number": bill.bill_number,
                "supplier_id": bill.supplier_id,
                "supplier_name": bill.supplier_name,
                "issue_date": bill.issue_date,
                "due_date": bill.due_date,
                "total_amount": bill.total_amount,
                "paid_amount": bill.paid_amount,
                "pending_amount": pending_amount,
                "days_overdue": max(0, days_overdue),
                "is_overdue": is_overdue
            })
        
        return {
            "as_of_date": as_of_date,
            "bills": bills_list,
            "total_bills": total_bills,
            "total_pending_amount": total_pending_amount,
            "overdue_bills_count": overdue_bills_count,
            "overdue_amount": overdue_amount,
            "current_amount": current_amount
        }