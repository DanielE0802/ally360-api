"""
Base service class for Reports module

Provides common functionality for all report services including
database session management, tenant filtering, and common queries.
"""

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.modules.invoices.models import Invoice, InvoiceLineItem, InvoiceStatus, InvoiceType
from app.modules.bills.models import Bill, BillLineItem, BillStatus
from app.modules.products.models import Product, Stock, InventoryMovement
from app.modules.categories.models import Category
from app.modules.brands.models import Brand
from app.modules.pos.models import CashRegister, CashMovement, Seller
from app.modules.contacts.models import Contact
from app.modules.pdv.models import PDV
from app.modules.auth.models import User
from app.modules.invoices.models import Payment, PaymentMethod


class BaseReportService:
    """Base service class for all report services"""
    
    def __init__(self, db: Session, tenant_id: UUID, pdv_id: Optional[UUID] = None):
        self.db = db
        self.tenant_id = tenant_id
        self.pdv_id = pdv_id
    
    def _get_base_invoice_query(self):
        """Get base query for invoices with tenant filtering"""
        return self.db.query(Invoice).filter(
            Invoice.tenant_id == self.tenant_id
        )
    
    def _get_base_bill_query(self):
        """Get base query for bills with tenant filtering"""
        return self.db.query(Bill).filter(
            Bill.tenant_id == self.tenant_id
        )
    
    def _get_base_product_query(self):
        """Get base query for products with tenant filtering"""
        return self.db.query(Product).filter(
            Product.tenant_id == self.tenant_id
        )
    
    def _get_base_stock_query(self):
        """Get base query for stock with tenant filtering"""
        query = self.db.query(Stock).filter(
            Stock.tenant_id == self.tenant_id
        )
        if self.pdv_id:
            query = query.filter(Stock.pdv_id == self.pdv_id)
        return query
    
    def _get_base_inventory_movement_query(self):
        """Get base query for inventory movements with tenant filtering"""
        query = self.db.query(InventoryMovement).filter(
            InventoryMovement.tenant_id == self.tenant_id
        )
        if self.pdv_id:
            query = query.filter(InventoryMovement.pdv_id == self.pdv_id)
        return query
    
    def _get_base_cash_register_query(self):
        """Get base query for cash registers with tenant filtering"""
        query = self.db.query(CashRegister).filter(
            CashRegister.tenant_id == self.tenant_id
        )
        if self.pdv_id:
            query = query.filter(CashRegister.pdv_id == self.pdv_id)
        return query
    
    def _get_base_cash_movement_query(self):
        """Get base query for cash movements with tenant filtering"""
        return self.db.query(CashMovement).filter(
            CashMovement.tenant_id == self.tenant_id
        )
    
    def _get_base_seller_query(self):
        """Get base query for sellers with tenant filtering"""
        return self.db.query(Seller).filter(
            Seller.tenant_id == self.tenant_id,
            Seller.deleted_at.is_(None)
        )
    
    def _get_base_contact_query(self):
        """Get base query for contacts with tenant filtering"""
        return self.db.query(Contact).filter(
            Contact.tenant_id == self.tenant_id,
            Contact.deleted_at.is_(None)
        )
    
    def _get_base_payment_query(self):
        """Get base query for payments with tenant filtering"""
        return self.db.query(Payment).filter(
            Payment.tenant_id == self.tenant_id
        )
    
    def _apply_date_filter(self, query, date_field, start_date: date, end_date: date):
        """Apply date range filter to a query"""
        return query.filter(
            and_(
                date_field >= start_date,
                date_field <= end_date
            )
        )
    
    def _apply_pdv_filter(self, query, pdv_field, pdv_id: Optional[UUID] = None):
        """Apply PDV filter to a query"""
        target_pdv_id = pdv_id or self.pdv_id
        if target_pdv_id:
            return query.filter(pdv_field == target_pdv_id)
        return query
    
    def _calculate_days_difference(self, from_date: date, to_date: date = None) -> int:
        """Calculate days difference between dates"""
        if to_date is None:
            to_date = date.today()
        return (to_date - from_date).days
    
    def _validate_pdv_ownership(self, pdv_id: UUID) -> bool:
        """Validate that PDV belongs to the tenant"""
        pdv = self.db.query(PDV).filter(
            PDV.id == pdv_id,
            PDV.tenant_id == self.tenant_id
        ).first()
        return pdv is not None
    
    def _get_user_name(self, user_id: UUID) -> str:
        """Get user name by ID"""
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.name if user else "Unknown User"
    
    def _get_contact_name(self, contact_id: UUID) -> str:
        """Get contact name by ID"""
        contact = self.db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.tenant_id == self.tenant_id
        ).first()
        return contact.name if contact else "Unknown Contact"
    
    def _get_product_info(self, product_id: UUID) -> Dict:
        """Get product information including category and brand"""
        product = self.db.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == self.tenant_id
        ).first()
        
        if not product:
            return {
                "name": "Unknown Product",
                "sku": "",
                "category_name": None,
                "brand_name": None
            }
        
        category_name = None
        if product.category_id:
            category = self.db.query(Category).filter(
                Category.id == product.category_id
            ).first()
            category_name = category.name if category else None
        
        brand_name = None
        if product.brand_id:
            brand = self.db.query(Brand).filter(
                Brand.id == product.brand_id
            ).first()
            brand_name = brand.name if brand else None
        
        return {
            "name": product.name,
            "sku": product.sku,
            "category_name": category_name,
            "brand_name": brand_name
        }
    
    def _get_pdv_name(self, pdv_id: UUID) -> str:
        """Get PDV name by ID"""
        pdv = self.db.query(PDV).filter(
            PDV.id == pdv_id,
            PDV.tenant_id == self.tenant_id
        ).first()
        return pdv.name if pdv else "Unknown PDV"