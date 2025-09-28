from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from uuid import UUID
from typing import Dict, Any

from app.modules.categories.models import Category
from app.modules.categories.schemas import CategoryCreate, CategoryUpdate


class CategoryService:
    """Servicio para gestión de categorías"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_category(self, data: CategoryCreate, tenant_id: UUID, user_id: UUID) -> Category:
        """
        Crear nueva categoría
        
        Args:
            data: Datos de la categoría
            tenant_id: ID de la empresa
            user_id: ID del usuario que crea
            
        Returns:
            Category: Categoría creada
        """
        try:
            # Verificar unicidad por tenant
            existing = self.db.query(Category).filter(
                Category.name == data.name,
                Category.tenant_id == tenant_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una categoría con el nombre '{data.name}' en esta empresa"
                )

            category = Category(
                name=data.name,
                description=data.description,
                tenant_id=tenant_id
            )
            
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
            return category
            
        except HTTPException:
            raise
        except IntegrityError:
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

    def get_all_categories(self, tenant_id: UUID, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Listar categorías con paginación"""
        try:
            query = self.db.query(Category).filter(Category.tenant_id == tenant_id)
            total = query.count()
            categories = query.offset(offset).limit(limit).all()
            
            return {
                "categories": categories,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error listando categorías: {str(e)}"
            )

    def get_category_by_id(self, category_id: UUID, tenant_id: UUID) -> Category:
        """Obtener categoría por ID"""
        category = self.db.query(Category).filter(
            Category.id == category_id,
            Category.tenant_id == tenant_id
        ).first()
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría no encontrada"
            )
        return category

    def update_category(self, category_id: UUID, data: CategoryUpdate, tenant_id: UUID, user_id: UUID) -> Category:
        """Actualizar categoría"""
        try:
            category = self.get_category_by_id(category_id, tenant_id)
            
            # Verificar unicidad del nombre si se actualiza
            if data.name and data.name != category.name:
                existing = self.db.query(Category).filter(
                    Category.name == data.name,
                    Category.tenant_id == tenant_id,
                    Category.id != category_id
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe otra categoría con el nombre '{data.name}'"
                    )
            
            update_dict = data.model_dump(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(category, field, value)
            
            self.db.commit()
            self.db.refresh(category)
            return category
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error actualizando categoría: {str(e)}"
            )

    def delete_category(self, category_id: UUID, tenant_id: UUID) -> Dict[str, str]:
        """Eliminar categoría"""
        try:
            category = self.get_category_by_id(category_id, tenant_id)
            
            # TODO: Verificar si tiene productos asociados
            
            self.db.delete(category)
            self.db.commit()
            return {"message": "Categoría eliminada exitosamente"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error eliminando categoría: {str(e)}"
            )