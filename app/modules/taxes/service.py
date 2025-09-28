from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from app.modules.products.models import Tax, ProductTax, Product, TaxType
from app.modules.taxes.schemas import (
    TaxCreate, TaxUpdate, TaxOut, ProductTaxCreate, TaxCalculation
)


class TaxService:
    def __init__(self, db: Session):
        self.db = db

    def create_local_tax(self, tax_data: TaxCreate, company_id: str) -> Tax:
        """Crear un impuesto local para la empresa"""
        try:
            # Verificar que no exista un impuesto con el mismo nombre en la empresa
            existing = self.db.query(Tax).filter(
                Tax.company_id == company_id,
                Tax.name == tax_data.name
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un impuesto con el nombre '{tax_data.name}' en esta empresa"
                )

            # Crear el impuesto local
            tax = Tax(
                **tax_data.model_dump(),
                company_id=company_id,
                is_editable=True
            )
            
            self.db.add(tax)
            self.db.commit()
            self.db.refresh(tax)
            return tax
            
        except IntegrityError as e:
            self.db.rollback()
            if "uq_tax_company_name" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un impuesto con el nombre '{tax_data.name}' en esta empresa"
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

    def get_available_taxes(self, company_id: str, limit: int = 100, offset: int = 0) -> dict:
        """Obtener impuestos disponibles (globales + locales de la empresa)"""
        try:
            # Impuestos globales (company_id es NULL) + impuestos locales de la empresa
            query = self.db.query(Tax).filter(
                (Tax.company_id == company_id) | (Tax.company_id.is_(None))
            )
            
            total = query.count()
            taxes = query.offset(offset).limit(limit).all()
            
            return {
                "taxes": taxes,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener impuestos: {str(e)}"
            )

    def get_tax_by_id(self, tax_id: UUID, company_id: str) -> Tax:
        """Obtener un impuesto específico"""
        tax = self.db.query(Tax).filter(
            Tax.id == tax_id,
            (Tax.company_id == company_id) | (Tax.company_id.is_(None))
        ).first()
        
        if not tax:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Impuesto no encontrado"
            )
        return tax

    def update_local_tax(self, tax_id: UUID, tax_update: TaxUpdate, company_id: str) -> Tax:
        """Actualizar un impuesto local (solo si es editable)"""
        try:
            tax = self.db.query(Tax).filter(
                Tax.id == tax_id,
                Tax.company_id == company_id
            ).first()
            
            if not tax:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Impuesto no encontrado"
                )
            
            if not tax.is_editable:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No se pueden editar impuestos globales"
                )
            
            # Actualizar campos
            for field, value in tax_update.model_dump(exclude_unset=True).items():
                if value is not None:
                    setattr(tax, field, value)
            
            self.db.commit()
            self.db.refresh(tax)
            return tax
            
        except HTTPException:
            raise
        except IntegrityError as e:
            self.db.rollback()
            if "uq_tax_company_name" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe un impuesto con ese nombre en esta empresa"
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

    def delete_local_tax(self, tax_id: UUID, company_id: str) -> dict:
        """Eliminar un impuesto local si no está en uso"""
        try:
            tax = self.db.query(Tax).filter(
                Tax.id == tax_id,
                Tax.company_id == company_id
            ).first()
            
            if not tax:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Impuesto no encontrado"
                )
            
            if not tax.is_editable:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No se pueden eliminar impuestos globales"
                )
            
            # Verificar si está en uso
            product_tax_count = self.db.query(ProductTax).filter(
                ProductTax.tax_id == tax_id
            ).count()
            
            if product_tax_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se puede eliminar el impuesto porque está asignado a {product_tax_count} producto(s)"
                )
            
            self.db.delete(tax)
            self.db.commit()
            return {"message": "Impuesto eliminado exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def assign_taxes_to_product(self, product_id: UUID, tax_ids: List[UUID], company_id: str) -> List[ProductTax]:
        """Asignar impuestos a un producto"""
        try:
            # Verificar que el producto existe y pertenece a la empresa
            product = self.db.query(Product).filter(
                Product.id == product_id,
                Product.tenant_id == company_id
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Producto no encontrado"
                )
            
            # Verificar que todos los impuestos existen y están disponibles para la empresa
            taxes = self.db.query(Tax).filter(
                Tax.id.in_(tax_ids),
                (Tax.company_id == company_id) | (Tax.company_id.is_(None))
            ).all()
            
            if len(taxes) != len(tax_ids):
                found_ids = {tax.id for tax in taxes}
                missing_ids = set(tax_ids) - found_ids
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Impuestos no encontrados: {list(missing_ids)}"
                )
            
            # Eliminar asignaciones existentes
            self.db.query(ProductTax).filter(
                ProductTax.product_id == product_id,
                ProductTax.tenant_id == company_id
            ).delete()
            
            # Crear nuevas asignaciones
            product_taxes = []
            for tax_id in tax_ids:
                product_tax = ProductTax(
                    product_id=product_id,
                    tax_id=tax_id,
                    tenant_id=company_id
                )
                self.db.add(product_tax)
                product_taxes.append(product_tax)
            
            self.db.commit()
            
            # Refrescar y retornar
            for pt in product_taxes:
                self.db.refresh(pt)
            
            return product_taxes
            
        except HTTPException:
            raise
        except IntegrityError as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Error de integridad al asignar impuestos"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno del servidor: {str(e)}"
            )

    def get_product_taxes(self, product_id: UUID, company_id: str) -> List[ProductTax]:
        """Obtener los impuestos asignados a un producto"""
        try:
            product_taxes = self.db.query(ProductTax).filter(
                ProductTax.product_id == product_id,
                ProductTax.tenant_id == company_id
            ).all()
            
            return product_taxes
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al obtener impuestos del producto: {str(e)}"
            )

    def calculate_taxes(self, base_amount: Decimal, tax_ids: List[UUID], company_id: str) -> List[TaxCalculation]:
        """Calcular impuestos para una base gravable"""
        try:
            taxes = self.db.query(Tax).filter(
                Tax.id.in_(tax_ids),
                (Tax.company_id == company_id) | (Tax.company_id.is_(None))
            ).all()
            
            calculations = []
            for tax in taxes:
                tax_amount = base_amount * tax.rate
                calculations.append(TaxCalculation(
                    tax_id=tax.id,
                    tax_name=tax.name,
                    tax_rate=tax.rate,
                    base_amount=base_amount,
                    tax_amount=tax_amount
                ))
            
            return calculations
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al calcular impuestos: {str(e)}"
            )


# Función helper para crear impuestos globales DIAN (usar en seeds/migraciones)
def create_global_taxes(db: Session):
    """Crear impuestos globales de la DIAN si no existen"""
    global_taxes = [
        {"name": "IVA 19%", "code": "01", "rate": Decimal("0.19"), "type": TaxType.VAT},
        {"name": "IVA 5%", "code": "01", "rate": Decimal("0.05"), "type": TaxType.VAT},
        {"name": "IVA 0%", "code": "01", "rate": Decimal("0.00"), "type": TaxType.VAT},
        {"name": "INC 8%", "code": "04", "rate": Decimal("0.08"), "type": TaxType.INC},
        {"name": "INC 16%", "code": "04", "rate": Decimal("0.16"), "type": TaxType.INC},
    ]
    
    for tax_data in global_taxes:
        existing = db.query(Tax).filter(
            Tax.name == tax_data["name"],
            Tax.company_id.is_(None)
        ).first()
        
        if not existing:
            tax = Tax(
                **tax_data,
                company_id=None,
                is_editable=False
            )
            db.add(tax)
    
    db.commit()