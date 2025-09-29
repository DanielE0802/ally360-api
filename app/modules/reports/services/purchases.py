"""
Purchase Reports Service

Handles all purchase-related reports including by supplier
and by category reports.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func

from .base import BaseReportService
from app.modules.bills.models import Bill, BillLineItem, BillStatus
from app.modules.contacts.models import Contact
from app.modules.products.models import Product
from app.modules.categories.models import Category


class PurchaseReportService(BaseReportService):
    """Service for generating purchase reports"""
    
    def get_purchases_by_supplier(
        self,
        start_date: date,
        end_date: date,
        supplier_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate purchases by supplier report.
        
        Returns suppliers ranked by total purchase amount.
        """
        # Base query joining bills with contacts (suppliers)
        query = self.db.query(
            Bill.supplier_id,
            Contact.name.label('supplier_name'),
            Contact.email.label('supplier_email'),
            Contact.phone.label('supplier_phone'),
            func.count(Bill.id).label('total_bills'),
            func.sum(Bill.total_amount).label('total_amount'),
            func.avg(Bill.total_amount).label('average_bill'),
            func.max(Bill.issue_date).label('last_bill_date')
        ).join(
            Contact, Bill.supplier_id == Contact.id
        ).filter(
            Bill.tenant_id == self.tenant_id,
            Bill.status.in_([BillStatus.PAID, BillStatus.PARTIAL]),
            Contact.deleted_at.is_(None)
        )
        
        # Apply date filter
        query = self._apply_date_filter(query, Bill.issue_date, start_date, end_date)
        
        # Apply optional filters
        if supplier_id:
            query = query.filter(Bill.supplier_id == supplier_id)
        
        if pdv_id:
            query = self._apply_pdv_filter(query, Bill.pdv_id, pdv_id)
        
        # Group by supplier and order by total amount
        query = query.group_by(
            Bill.supplier_id,
            Contact.name,
            Contact.email,
            Contact.phone
        ).order_by(desc('total_amount'))
        
        # Get total count for pagination
        total_suppliers = query.count()
        
        # Apply pagination
        suppliers = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries
        suppliers_list = []
        total_amount_sum = Decimal('0')
        
        for supplier in suppliers:
            total_amount_sum += supplier.total_amount or Decimal('0')
            suppliers_list.append({
                "supplier_id": supplier.supplier_id,
                "supplier_name": supplier.supplier_name,
                "supplier_email": supplier.supplier_email,
                "supplier_phone": supplier.supplier_phone,
                "total_bills": supplier.total_bills,
                "total_amount": supplier.total_amount,
                "average_bill": supplier.average_bill,
                "last_bill_date": supplier.last_bill_date
            })
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "suppliers": suppliers_list,
            "total_suppliers": total_suppliers,
            "total_amount": total_amount_sum
        }
    
    def get_purchases_by_category(
        self,
        start_date: date,
        end_date: date,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate purchases by category report.
        
        Returns product categories ranked by total purchase amount.
        """
        # Base query joining bill line items with products and categories
        query = self.db.query(
            Product.category_id,
            func.coalesce(Category.name, 'Sin Categoría').label('category_name'),
            func.sum(BillLineItem.quantity).label('total_quantity'),
            func.sum(BillLineItem.quantity * BillLineItem.unit_price).label('total_amount'),
            func.avg(BillLineItem.unit_price).label('average_price'),
            func.count(func.distinct(BillLineItem.bill_id)).label('bills_count')
        ).join(
            Bill, BillLineItem.bill_id == Bill.id
        ).join(
            Product, BillLineItem.product_id == Product.id
        ).outerjoin(
            Category, Product.category_id == Category.id
        ).filter(
            Bill.tenant_id == self.tenant_id,
            Bill.status.in_([BillStatus.PAID, BillStatus.PARTIAL])
        )
        
        # Apply date filter
        query = self._apply_date_filter(query, Bill.issue_date, start_date, end_date)
        
        # Apply PDV filter if specified
        if pdv_id:
            query = self._apply_pdv_filter(query, Bill.pdv_id, pdv_id)
        
        # Group by category and order by total amount
        query = query.group_by(
            Product.category_id,
            Category.name
        ).order_by(desc('total_amount'))
        
        # Get total count for pagination
        total_categories = query.count()
        
        # Apply pagination
        categories = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries
        categories_list = []
        total_amount_sum = Decimal('0')
        
        for category in categories:
            total_amount_sum += category.total_amount or Decimal('0')
            categories_list.append({
                "category_id": category.category_id,
                "category_name": category.category_name,
                "total_quantity": category.total_quantity,
                "total_amount": category.total_amount,
                "average_price": category.average_price,
                "bills_count": category.bills_count
            })
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "categories": categories_list,
            "total_categories": total_categories,
            "total_amount": total_amount_sum
        }