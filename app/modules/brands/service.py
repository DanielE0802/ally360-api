from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from uuid import UUID
from typing import Dict, Any
from app.modules.brands.models import Brand
from app.modules.brands.schemas import BrandCreate, BrandUpdate


class BrandService:
    """Servicio para gestión de marcas"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_brand(self, brand_data: BrandCreate, tenant_id: UUID, user_id: UUID) -> Brand:
        """
        Crear nueva marca
        
        Args:
            brand_data: Datos de la marca
            tenant_id: ID de la empresa
            user_id: ID del usuario que crea
            
        Returns:
            Brand: Marca creada
            
        Raises:
            HTTPException: Si la marca ya existe o hay error de BD
        """
        try:
            # Verificar unicidad por tenant
            existing = self.db.query(Brand).filter(
                Brand.name == brand_data.name,
                Brand.tenant_id == tenant_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una marca con el nombre '{brand_data.name}' en esta empresa"
                )

            brand = Brand(
                name=brand_data.name,
                description=brand_data.description,
                tenant_id=tenant_id
            )
            
            self.db.add(brand)
            self.db.commit()
            self.db.refresh(brand)
            return brand
            
        except HTTPException:
            raise
        except IntegrityError as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Error de integridad en base de datos"
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno: {str(e)}"
            )

    def get_all_brands(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Listar marcas con paginación
        
        Args:
            tenant_id: ID de la empresa
            limit: Límite de resultados
            offset: Desplazamiento
            
        Returns:
            Dict con brands, total, limit, offset
        """
        try:
            query = self.db.query(Brand).filter(Brand.tenant_id == tenant_id)
            total = query.count()
            brands = query.offset(offset).limit(limit).all()
            
            return {
                "brands": brands,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando marcas: {str(e)}"
            )

    def get_brand_by_id(self, brand_id: UUID, tenant_id: UUID) -> Brand:
        """
        Obtener marca por ID
        
        Args:
            brand_id: ID de la marca
            tenant_id: ID de la empresa
            
        Returns:
            Brand: Marca encontrada
            
        Raises:
            HTTPException: Si no se encuentra la marca
        """
        brand = self.db.query(Brand).filter(
            Brand.id == brand_id,
            Brand.tenant_id == tenant_id
        ).first()
        
        if not brand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Marca no encontrada"
            )
        return brand

    def update_brand(self, brand_id: UUID, update_data: BrandUpdate, tenant_id: UUID, user_id: UUID) -> Brand:
        """
        Actualizar marca
        
        Args:
            brand_id: ID de la marca
            update_data: Datos a actualizar
            tenant_id: ID de la empresa
            user_id: ID del usuario que actualiza
            
        Returns:
            Brand: Marca actualizada
        """
        try:
            brand = self.get_brand_by_id(brand_id, tenant_id)
            
            # Verificar unicidad del nombre si se actualiza
            if update_data.name and update_data.name != brand.name:
                existing = self.db.query(Brand).filter(
                    Brand.name == update_data.name,
                    Brand.tenant_id == tenant_id,
                    Brand.id != brand_id
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe otra marca con el nombre '{update_data.name}'"
                    )
            
            update_dict = update_data.model_dump(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(brand, field, value)
            
            self.db.commit()
            self.db.refresh(brand)
            return brand
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error actualizando marca: {str(e)}"
            )

    def delete_brand(self, brand_id: UUID, tenant_id: UUID) -> Dict[str, str]:
        """
        Eliminar marca
        
        Args:
            brand_id: ID de la marca
            tenant_id: ID de la empresa
            
        Returns:
            Dict con mensaje de confirmación
        """
        try:
            brand = self.get_brand_by_id(brand_id, tenant_id)
            
            # TODO: Verificar si tiene productos asociados
            # En el MVP permitimos eliminar aunque tenga productos
            
            self.db.delete(brand)
            self.db.commit()
            return {"message": "Marca eliminada exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error eliminando marca: {str(e)}"
            )