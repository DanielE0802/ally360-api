from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, func
from fastapi import HTTPException, status

from app.modules.products.models import Stock, Product, ProductVariant, InventoryMovement
from app.modules.pdv.models import PDV
from app.modules.auth.models import User
from app.modules.inventory.schemas import (
    StockOut, StockUpdate, InventoryMovementCreate, InventoryMovementOut,
    TransferMovementCreate, ProductStockSummary, MovementType
)

class InventoryService:
    """Service for inventory management operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_stock_by_product(self, tenant_id: UUID, product_id: UUID) -> List[StockOut]:
        """Get all stock records for a product across PDVs."""
        stocks = self.db.query(Stock).options(
            selectinload(Stock.product),
            selectinload(Stock.pdv),
            selectinload(Stock.variant)
        ).filter(
            and_(
                Stock.tenant_id == tenant_id,
                Stock.product_id == product_id
            )
        ).all()

        return [
            StockOut(
                id=stock.id,
                product_id=stock.product_id,
                pdv_id=stock.pdv_id,
                variant_id=stock.variant_id,
                quantity=stock.quantity,
                product_name=stock.product.name if stock.product else None,
                product_sku=stock.product.sku if stock.product else None,
                pdv_name=stock.pdv.name if stock.pdv else None,
                variant_color=stock.variant.color if stock.variant else None,
                variant_size=stock.variant.size if stock.variant else None
            )
            for stock in stocks
        ]

    def get_stock_by_product_and_pdv(
        self, 
        tenant_id: UUID, 
        product_id: UUID, 
        pdv_id: UUID,
        variant_id: Optional[UUID] = None
    ) -> StockOut:
        """Get stock for specific product/variant at specific PDV."""
        query = self.db.query(Stock).options(
            selectinload(Stock.product),
            selectinload(Stock.pdv),
            selectinload(Stock.variant)
        ).filter(
            and_(
                Stock.tenant_id == tenant_id,
                Stock.product_id == product_id,
                Stock.pdv_id == pdv_id
            )
        )
        
        if variant_id:
            query = query.filter(Stock.variant_id == variant_id)
        else:
            query = query.filter(Stock.variant_id.is_(None))

        stock = query.first()
        if not stock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stock record not found"
            )

        return StockOut(
            id=stock.id,
            product_id=stock.product_id,
            pdv_id=stock.pdv_id,
            variant_id=stock.variant_id,
            quantity=stock.quantity,
            product_name=stock.product.name if stock.product else None,
            product_sku=stock.product.sku if stock.product else None,
            pdv_name=stock.pdv.name if stock.pdv else None,
            variant_color=stock.variant.color if stock.variant else None,
            variant_size=stock.variant.size if stock.variant else None
        )

    def adjust_stock(
        self, 
        tenant_id: UUID, 
        product_id: UUID, 
        pdv_id: UUID,
        stock_data: StockUpdate,
        user_id: UUID,
        variant_id: Optional[UUID] = None
    ) -> StockOut:
        """Manually adjust stock quantity."""
        # Get current stock
        query = self.db.query(Stock).filter(
            and_(
                Stock.tenant_id == tenant_id,
                Stock.product_id == product_id,
                Stock.pdv_id == pdv_id
            )
        )
        
        if variant_id:
            query = query.filter(Stock.variant_id == variant_id)
        else:
            query = query.filter(Stock.variant_id.is_(None))

        stock = query.first()
        if not stock:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stock record not found"
            )

        old_quantity = stock.quantity
        stock.quantity = stock_data.quantity
        
        # Create movement record
        movement = InventoryMovement(
            tenant_id=tenant_id,
            product_id=product_id,
            pdv_id=pdv_id,
            variant_id=variant_id,
            quantity=stock_data.quantity - old_quantity,
            movement_type=MovementType.ADJ.value,
            notes=stock_data.notes,
            created_by=user_id
        )
        
        self.db.add(movement)
        self.db.commit()
        self.db.refresh(stock)

        return self.get_stock_by_product_and_pdv(tenant_id, product_id, pdv_id, variant_id)

    def create_movement(
        self, 
        tenant_id: UUID, 
        movement_data: InventoryMovementCreate,
        user_id: UUID
    ) -> InventoryMovementOut:
        """Create inventory movement and update stock."""
        # Validate product and PDV belong to tenant
        product = self.db.query(Product).filter(
            and_(Product.tenant_id == tenant_id, Product.id == movement_data.product_id)
        ).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El producto especificado no existe o no pertenece a esta empresa"
            )
        
        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El producto '{product.name}' está inactivo y no se pueden realizar movimientos"
            )

        pdv = self.db.query(PDV).filter(
            and_(PDV.tenant_id == tenant_id, PDV.id == movement_data.pdv_id)
        ).first()
        if not pdv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El punto de venta especificado no existe o no pertenece a esta empresa"
            )
        
        if not pdv.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El punto de venta '{pdv.name}' está inactivo y no se pueden realizar movimientos"
            )

        # Validate variant if provided
        if movement_data.variant_id:
            variant = self.db.query(ProductVariant).filter(
                and_(
                    ProductVariant.id == movement_data.variant_id,
                    ProductVariant.product_id == movement_data.product_id,
                    ProductVariant.tenant_id == tenant_id
                )
            ).first()
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La variante especificada no existe o no pertenece a este producto"
                )
            
            if not variant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La variante especificada está inactiva"
                )

        # Get or create stock record
        query = self.db.query(Stock).filter(
            and_(
                Stock.tenant_id == tenant_id,
                Stock.product_id == movement_data.product_id,
                Stock.pdv_id == movement_data.pdv_id
            )
        )
        
        if movement_data.variant_id:
            query = query.filter(Stock.variant_id == movement_data.variant_id)
        else:
            query = query.filter(Stock.variant_id.is_(None))

        stock = query.first()
        if not stock:
            # Create new stock record
            stock = Stock(
                tenant_id=tenant_id,
                product_id=movement_data.product_id,
                pdv_id=movement_data.pdv_id,
                variant_id=movement_data.variant_id,
                quantity=0
            )
            self.db.add(stock)
            self.db.flush()

        # Validate quantity for different movement types
        if movement_data.quantity == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad del movimiento no puede ser cero"
            )

        # Validate stock for OUT movements
        if movement_data.movement_type == MovementType.OUT and stock.quantity < abs(movement_data.quantity):
            variant_info = f" - {variant.color or ''} {variant.size or ''}".strip(' -') if movement_data.variant_id and variant else ""
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para '{product.name}{variant_info}' en '{pdv.name}'. Disponible: {stock.quantity}, Solicitado: {abs(movement_data.quantity)}"
            )
        
        # Validate that final stock won't be negative
        final_quantity = stock.quantity + movement_data.quantity
        if final_quantity < 0:
            variant_info = f" - {variant.color or ''} {variant.size or ''}".strip(' -') if movement_data.variant_id and variant else ""
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El movimiento resultaría en stock negativo para '{product.name}{variant_info}' en '{pdv.name}'. Stock actual: {stock.quantity}, Cambio: {movement_data.quantity}"
            )

        # Update stock
        stock.quantity += movement_data.quantity

        # Create movement
        movement = InventoryMovement(
            tenant_id=tenant_id,
            product_id=movement_data.product_id,
            pdv_id=movement_data.pdv_id,
            variant_id=movement_data.variant_id,
            quantity=movement_data.quantity,
            movement_type=movement_data.movement_type.value,
            reference=movement_data.reference,
            notes=movement_data.notes,
            created_by=user_id
        )

        self.db.add(movement)
        self.db.commit()
        self.db.refresh(movement)

        return self._movement_to_output(movement)

    def transfer_stock(
        self, 
        tenant_id: UUID, 
        transfer_data: TransferMovementCreate,
        user_id: UUID
    ) -> List[InventoryMovementOut]:
        """Transfer stock between PDVs."""
        if transfer_data.from_pdv_id == transfer_data.to_pdv_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede transferir al mismo punto de venta"
            )
        
        if transfer_data.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad a transferir debe ser mayor a cero"
            )
        
        # Validate both PDVs exist and belong to tenant
        from_pdv = self.db.query(PDV).filter(
            and_(PDV.tenant_id == tenant_id, PDV.id == transfer_data.from_pdv_id)
        ).first()
        if not from_pdv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El punto de venta origen no existe o no pertenece a esta empresa"
            )
        
        to_pdv = self.db.query(PDV).filter(
            and_(PDV.tenant_id == tenant_id, PDV.id == transfer_data.to_pdv_id)
        ).first()
        if not to_pdv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El punto de venta destino no existe o no pertenece a esta empresa"
            )

        # Create OUT movement from source PDV
        out_movement = self.create_movement(
            tenant_id=tenant_id,
            movement_data=InventoryMovementCreate(
                product_id=transfer_data.product_id,
                pdv_id=transfer_data.from_pdv_id,
                variant_id=transfer_data.variant_id,
                quantity=-transfer_data.quantity,
                movement_type=MovementType.TRANSFER,
                reference=transfer_data.reference,
                notes=f"Transfer OUT to {transfer_data.to_pdv_id}: {transfer_data.notes or ''}"
            ),
            user_id=user_id
        )

        # Create IN movement to destination PDV
        in_movement = self.create_movement(
            tenant_id=tenant_id,
            movement_data=InventoryMovementCreate(
                product_id=transfer_data.product_id,
                pdv_id=transfer_data.to_pdv_id,
                variant_id=transfer_data.variant_id,
                quantity=transfer_data.quantity,
                movement_type=MovementType.TRANSFER,
                reference=transfer_data.reference,
                notes=f"Transfer IN from {transfer_data.from_pdv_id}: {transfer_data.notes or ''}"
            ),
            user_id=user_id
        )

        return [out_movement, in_movement]

    def get_movements(
        self, 
        tenant_id: UUID,
        product_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None,
        movement_type: Optional[MovementType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[InventoryMovementOut]:
        """Get inventory movements with filters."""
        query = self.db.query(InventoryMovement).options(
            selectinload(InventoryMovement.product),
            selectinload(InventoryMovement.pdv),
            selectinload(InventoryMovement.created_by_user)
        ).filter(InventoryMovement.tenant_id == tenant_id)

        if product_id:
            query = query.filter(InventoryMovement.product_id == product_id)
        if pdv_id:
            query = query.filter(InventoryMovement.pdv_id == pdv_id)
        if movement_type:
            query = query.filter(InventoryMovement.movement_type == movement_type.value)

        movements = query.order_by(InventoryMovement.created_at.desc()).offset(offset).limit(limit).all()

        return [self._movement_to_output(movement) for movement in movements]

    def get_product_stock_summary(self, tenant_id: UUID, product_id: UUID) -> ProductStockSummary:
        """Get complete stock summary for a product."""
        product = self.db.query(Product).filter(
            and_(Product.tenant_id == tenant_id, Product.id == product_id)
        ).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )

        stocks = self.get_stock_by_product(tenant_id, product_id)
        total_quantity = sum(stock.quantity for stock in stocks)

        return ProductStockSummary(
            product_id=product_id,
            product_name=product.name,
            product_sku=product.sku,
            total_quantity=total_quantity,
            pdv_stocks=stocks
        )

    def _movement_to_output(self, movement: InventoryMovement) -> InventoryMovementOut:
        """Convert movement model to output schema."""
        return InventoryMovementOut(
            id=movement.id,
            product_id=movement.product_id,
            pdv_id=movement.pdv_id,
            variant_id=movement.variant_id,
            quantity=movement.quantity,
            movement_type=movement.movement_type,
            reference=movement.reference,
            notes=movement.notes,
            created_by=movement.created_by,
            created_at=movement.created_at,
            tenant_id=movement.tenant_id,
            product_name=movement.product.name if movement.product else None,
            product_sku=movement.product.sku if movement.product else None,
            pdv_name=movement.pdv.name if movement.pdv else None,
            created_by_email=movement.created_by_user.email if movement.created_by_user else None
        )

    def create_stock_for_new_product(self, tenant_id: UUID, product_id: UUID):
        """Create stock records for a new product in all existing PDVs."""
        pdvs = self.db.query(PDV).filter(
            and_(PDV.tenant_id == tenant_id, PDV.is_active == True)
        ).all()

        for pdv in pdvs:
            existing_stock = self.db.query(Stock).filter(
                and_(
                    Stock.tenant_id == tenant_id,
                    Stock.product_id == product_id,
                    Stock.pdv_id == pdv.id,
                    Stock.variant_id.is_(None)
                )
            ).first()

            if not existing_stock:
                stock = Stock(
                    tenant_id=tenant_id,
                    product_id=product_id,
                    pdv_id=pdv.id,
                    quantity=0
                )
                self.db.add(stock)

        self.db.commit()

    def create_stock_for_new_pdv(self, tenant_id: UUID, pdv_id: UUID):
        """Create stock records for a new PDV for all existing products."""
        products = self.db.query(Product).filter(
            and_(Product.tenant_id == tenant_id, Product.is_active == True)
        ).all()

        for product in products:
            existing_stock = self.db.query(Stock).filter(
                and_(
                    Stock.tenant_id == tenant_id,
                    Stock.product_id == product.id,
                    Stock.pdv_id == pdv_id,
                    Stock.variant_id.is_(None)
                )
            ).first()

            if not existing_stock:
                stock = Stock(
                    tenant_id=tenant_id,
                    product_id=product.id,
                    pdv_id=pdv_id,
                    quantity=0
                )
                self.db.add(stock)

        self.db.commit()