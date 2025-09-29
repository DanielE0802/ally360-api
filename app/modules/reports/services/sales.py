"""
Sales Reports Service

Handles all sales-related reports including summary, by product,
by seller, and top customers reports.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import joinedload

from .base import BaseReportService
from app.modules.invoices.models import Invoice, InvoiceLineItem, InvoiceStatus, InvoiceType
from app.modules.pos.models import Seller
from app.modules.contacts.models import Contact
from app.modules.products.models import Product
from app.modules.categories.models import Category
from app.modules.brands.models import Brand


class SalesReportService(BaseReportService):
    """Service for generating sales reports"""
    
    def get_sales_summary(
        self,
        start_date: date,
        end_date: date,
        customer_id: Optional[UUID] = None,
        seller_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None
    ) -> Dict:
        """
        Generate sales summary report for a date range.
        
        Returns total sales, amount, average ticket, and invoice counts.
        """
        # Base query for paid invoices in date range
        query = self._get_base_invoice_query().filter(
            Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIAL])
        )
        
        # Apply date filter
        query = self._apply_date_filter(query, Invoice.issue_date, start_date, end_date)
        
        # Apply optional filters
        if customer_id:
            query = query.filter(Invoice.customer_id == customer_id)
        
        if seller_id:
            query = query.filter(Invoice.seller_id == seller_id)
        
        if pdv_id:
            query = self._apply_pdv_filter(query, Invoice.pdv_id, pdv_id)
        
        # Get aggregated data
        result = query.with_entities(
            func.count(Invoice.id).label('total_invoices'),
            func.sum(Invoice.total_amount).label('total_amount'),
            func.avg(Invoice.total_amount).label('average_ticket'),
            func.count(func.distinct(Invoice.id)).label('total_sales')
        ).first()
        
        # Count POS sales specifically
        pos_sales_count = query.filter(Invoice.type == InvoiceType.POS).count()
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_sales": result.total_sales or 0,
            "total_amount": result.total_amount or Decimal('0'),
            "average_ticket": result.average_ticket or Decimal('0'),
            "total_invoices": result.total_invoices or 0,
            "total_pos_sales": pos_sales_count
        }
    
    def get_sales_by_product(
        self,
        start_date: date,
        end_date: date,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate sales by product report.
        
        Returns products ranked by sales amount and quantity.
        """
        # Base query joining invoice line items with products
        query = self.db.query(
            InvoiceLineItem.product_id,
            Product.name.label('product_name'),
            Product.sku.label('product_sku'),
            Category.name.label('category_name'),
            Brand.name.label('brand_name'),
            func.sum(InvoiceLineItem.quantity).label('quantity_sold'),
            func.sum(InvoiceLineItem.quantity * InvoiceLineItem.unit_price).label('total_amount'),
            func.avg(InvoiceLineItem.unit_price).label('average_price'),
            func.count(func.distinct(InvoiceLineItem.invoice_id)).label('sales_count')
        ).join(
            Invoice, InvoiceLineItem.invoice_id == Invoice.id
        ).join(
            Product, InvoiceLineItem.product_id == Product.id
        ).outerjoin(
            Category, Product.category_id == Category.id
        ).outerjoin(
            Brand, Product.brand_id == Brand.id
        ).filter(
            Invoice.tenant_id == self.tenant_id,
            Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIAL])
        )
        
        # Apply date filter
        query = self._apply_date_filter(query, Invoice.issue_date, start_date, end_date)
        
        # Apply PDV filter if specified
        if pdv_id:
            query = self._apply_pdv_filter(query, Invoice.pdv_id, pdv_id)
        
        # Group by product and order by total amount
        query = query.group_by(
            InvoiceLineItem.product_id,
            Product.name,
            Product.sku,
            Category.name,
            Brand.name
        ).order_by(desc('total_amount'))
        
        # Get total count for pagination
        total_products = query.count()
        
        # Apply pagination
        products = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries
        products_list = []
        for product in products:
            products_list.append({
                "product_id": product.product_id,
                "product_name": product.product_name,
                "product_sku": product.product_sku,
                "category_name": product.category_name,
                "brand_name": product.brand_name,
                "quantity_sold": product.quantity_sold,
                "total_amount": product.total_amount,
                "average_price": product.average_price,
                "sales_count": product.sales_count
            })
        
        # Get summary for the period
        summary = self.get_sales_summary(start_date, end_date, pdv_id=pdv_id)
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "products": products_list,
            "total_products": total_products,
            "summary": summary
        }
    
    def get_sales_by_seller(
        self,
        start_date: date,
        end_date: date,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate sales by seller report.
        
        Returns sellers ranked by sales performance with commission estimates.
        """
        # Base query joining invoices with sellers
        query = self.db.query(
            Invoice.seller_id,
            Seller.name.label('seller_name'),
            Seller.commission_rate,
            func.count(Invoice.id).label('total_sales'),
            func.sum(Invoice.total_amount).label('total_amount'),
            func.avg(Invoice.total_amount).label('average_ticket')
        ).join(
            Seller, Invoice.seller_id == Seller.id
        ).filter(
            Invoice.tenant_id == self.tenant_id,
            Invoice.seller_id.isnot(None),
            Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIAL]),
            Seller.deleted_at.is_(None)
        )
        
        # Apply date filter
        query = self._apply_date_filter(query, Invoice.issue_date, start_date, end_date)
        
        # Apply PDV filter if specified
        if pdv_id:
            query = self._apply_pdv_filter(query, Invoice.pdv_id, pdv_id)
        
        # Group by seller and order by total amount
        query = query.group_by(
            Invoice.seller_id,
            Seller.name,
            Seller.commission_rate
        ).order_by(desc('total_amount'))
        
        # Get total count for pagination
        total_sellers = query.count()
        
        # Apply pagination
        sellers = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries with commission calculations
        sellers_list = []
        for seller in sellers:
            estimated_commission = None
            if seller.commission_rate and seller.total_amount:
                estimated_commission = seller.total_amount * seller.commission_rate
            
            sellers_list.append({
                "seller_id": seller.seller_id,
                "seller_name": seller.seller_name,
                "total_sales": seller.total_sales,
                "total_amount": seller.total_amount,
                "average_ticket": seller.average_ticket,
                "commission_rate": seller.commission_rate,
                "estimated_commission": estimated_commission
            })
        
        # Get summary for the period
        summary = self.get_sales_summary(start_date, end_date, pdv_id=pdv_id)
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "sellers": sellers_list,
            "total_sellers": total_sellers,
            "summary": summary
        }
    
    def get_top_customers(
        self,
        start_date: date,
        end_date: date,
        pdv_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict:
        """
        Generate top customers report.
        
        Returns customers ranked by total purchases amount.
        """
        # Base query joining invoices with contacts (customers)
        query = self.db.query(
            Invoice.customer_id,
            Contact.name.label('customer_name'),
            Contact.email.label('customer_email'),
            Contact.phone.label('customer_phone'),
            func.count(Invoice.id).label('total_purchases'),
            func.sum(Invoice.total_amount).label('total_amount'),
            func.avg(Invoice.total_amount).label('average_purchase'),
            func.max(Invoice.issue_date).label('last_purchase_date')
        ).join(
            Contact, Invoice.customer_id == Contact.id
        ).filter(
            Invoice.tenant_id == self.tenant_id,
            Invoice.status.in_([InvoiceStatus.PAID, InvoiceStatus.PARTIAL]),
            Contact.deleted_at.is_(None)
        )
        
        # Apply date filter
        query = self._apply_date_filter(query, Invoice.issue_date, start_date, end_date)
        
        # Apply PDV filter if specified
        if pdv_id:
            query = self._apply_pdv_filter(query, Invoice.pdv_id, pdv_id)
        
        # Group by customer and order by total amount
        query = query.group_by(
            Invoice.customer_id,
            Contact.name,
            Contact.email,
            Contact.phone
        ).order_by(desc('total_amount'))
        
        # Get total count for pagination
        total_customers = query.count()
        
        # Apply pagination
        customers = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries
        customers_list = []
        for customer in customers:
            customers_list.append({
                "customer_id": customer.customer_id,
                "customer_name": customer.customer_name,
                "customer_email": customer.customer_email,
                "customer_phone": customer.customer_phone,
                "total_purchases": customer.total_purchases,
                "total_amount": customer.total_amount,
                "average_purchase": customer.average_purchase,
                "last_purchase_date": customer.last_purchase_date
            })
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "customers": customers_list,
            "total_customers": total_customers
        }