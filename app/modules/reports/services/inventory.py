"""
Inventory Reports Service

Handles all inventory-related reports including current stock,
kardex movements, and low stock alerts.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, asc

from .base import BaseReportService
from app.modules.products.models import Product, Stock, InventoryMovement
from app.modules.categories.models import Category
from app.modules.brands.models import Brand
from app.modules.pdv.models import PDV


class InventoryReportService(BaseReportService):
    """Service for generating inventory reports"""
    
    def get_inventory_stock(
        self,
        pdv_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
        low_stock_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate current inventory stock report.
        
        Returns current stock levels for all products by PDV.
        """
        # Base query joining stock with products, categories, and brands
        query = self.db.query(
            Stock.product_id,
            Product.name.label('product_name'),
            Product.sku.label('product_sku'),
            Category.name.label('category_name'),
            Brand.name.label('brand_name'),
            Stock.pdv_id,
            PDV.name.label('pdv_name'),
            Stock.quantity.label('current_stock'),
            Stock.minimum_stock,
            Stock.maximum_stock,
            func.max(InventoryMovement.created_at).label('last_movement_date')
        ).join(
            Product, Stock.product_id == Product.id
        ).join(
            PDV, Stock.pdv_id == PDV.id
        ).outerjoin(
            Category, Product.category_id == Category.id
        ).outerjoin(
            Brand, Product.brand_id == Brand.id
        ).outerjoin(
            InventoryMovement, and_(
                InventoryMovement.product_id == Stock.product_id,
                InventoryMovement.pdv_id == Stock.pdv_id
            )
        ).filter(
            Stock.tenant_id == self.tenant_id
        )
        
        # Apply optional filters
        if pdv_id:
            query = query.filter(Stock.pdv_id == pdv_id)
        
        if category_id:
            query = query.filter(Product.category_id == category_id)
        
        if brand_id:
            query = query.filter(Product.brand_id == brand_id)
        
        if low_stock_only:
            query = query.filter(
                and_(
                    Stock.minimum_stock.isnot(None),
                    Stock.quantity <= Stock.minimum_stock
                )
            )
        
        # Group by stock record
        query = query.group_by(
            Stock.product_id,
            Product.name,
            Product.sku,
            Category.name,
            Brand.name,
            Stock.pdv_id,
            PDV.name,
            Stock.quantity,
            Stock.minimum_stock,
            Stock.maximum_stock
        ).order_by(Product.name, PDV.name)
        
        # Get total count for pagination
        total_items = query.count()
        
        # Apply pagination
        stock_items = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries
        items_list = []
        low_stock_count = 0
        
        for item in stock_items:
            is_low_stock = False
            if item.minimum_stock and item.current_stock <= item.minimum_stock:
                is_low_stock = True
                low_stock_count += 1
            
            items_list.append({
                "product_id": item.product_id,
                "product_name": item.product_name,
                "product_sku": item.product_sku,
                "category_name": item.category_name,
                "brand_name": item.brand_name,
                "pdv_name": item.pdv_name,
                "current_stock": item.current_stock,
                "minimum_stock": item.minimum_stock,
                "maximum_stock": item.maximum_stock,
                "is_low_stock": is_low_stock,
                "last_movement_date": item.last_movement_date
            })
        
        return {
            "as_of_date": datetime.now(),
            "items": items_list,
            "total_items": total_items,
            "low_stock_count": low_stock_count
        }
    
    def get_kardex(
        self,
        product_id: UUID,
        pdv_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> Dict:
        """
        Generate kardex report for a specific product.
        
        Returns all inventory movements with running balance.
        """
        # Get product information
        product_info = self._get_product_info(product_id)
        
        # Base query for inventory movements
        query = self._get_base_inventory_movement_query().filter(
            InventoryMovement.product_id == product_id
        )
        
        # Apply optional filters
        if pdv_id:
            query = query.filter(InventoryMovement.pdv_id == pdv_id)
        
        if start_date:
            query = query.filter(InventoryMovement.created_at >= start_date)
        
        if end_date:
            query = query.filter(InventoryMovement.created_at <= end_date)
        
        # Order by date ascending
        query = query.order_by(asc(InventoryMovement.created_at))
        
        # Apply pagination
        movements = query.offset(offset).limit(limit).all()
        
        # Calculate running balance
        movements_list = []
        running_balance = Decimal('0')
        total_in = Decimal('0')
        total_out = Decimal('0')
        
        # Get initial balance if start_date is specified
        if start_date:
            initial_query = self._get_base_inventory_movement_query().filter(
                InventoryMovement.product_id == product_id,
                InventoryMovement.created_at < start_date
            )
            
            if pdv_id:
                initial_query = initial_query.filter(InventoryMovement.pdv_id == pdv_id)
            
            initial_movements = initial_query.all()
            for mov in initial_movements:
                running_balance += mov.quantity
        
        initial_balance = running_balance
        
        # Process movements
        for movement in movements:
            running_balance += movement.quantity
            
            if movement.quantity > 0:
                total_in += movement.quantity
            else:
                total_out += abs(movement.quantity)
            
            movements_list.append({
                "movement_date": movement.created_at,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "reference": movement.reference,
                "notes": movement.notes,
                "running_balance": running_balance,
                "unit_cost": movement.unit_cost,
                "total_cost": movement.unit_cost * abs(movement.quantity) if movement.unit_cost else None
            })
        
        # Get PDV name if specified
        pdv_name = None
        if pdv_id:
            pdv_name = self._get_pdv_name(pdv_id)
        
        return {
            "product_id": product_id,
            "product_name": product_info["name"],
            "product_sku": product_info["sku"],
            "pdv_name": pdv_name,
            "period_start": start_date,
            "period_end": end_date,
            "movements": movements_list,
            "initial_balance": initial_balance,
            "final_balance": running_balance,
            "total_in": total_in,
            "total_out": total_out
        }
    
    def get_low_stock_items(
        self,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate low stock alert report.
        
        Returns products with stock below minimum level.
        """
        # Use the stock report with low_stock_only filter
        result = self.get_inventory_stock(
            pdv_id=pdv_id,
            low_stock_only=True,
            limit=limit,
            offset=offset
        )
        
        return {
            "as_of_date": result["as_of_date"],
            "items": result["items"],
            "total_low_stock_items": result["total_items"]
        }