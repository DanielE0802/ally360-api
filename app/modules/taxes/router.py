from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from app.modules.taxes.service import TaxService
from app.modules.taxes.schemas import (
    TaxCreate, TaxUpdate, TaxOut, TaxList, ProductTaxCreate, TaxCalculation
)

taxes_router = APIRouter(prefix="/taxes", tags=["Taxes"])


@taxes_router.get("/", response_model=TaxList)
def list_available_taxes(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar impuestos disponibles (globales + locales de la empresa)
    
    Retorna todos los impuestos que puede usar la empresa:
    - Impuestos globales (DIAN): IVA 19%, IVA 5%, INC 8%, etc.
    - Impuestos locales: creados específicamente por la empresa
    """
    service = TaxService(db)
    return service.get_available_taxes(auth_context.tenant_id, limit, offset)


@taxes_router.post("/", response_model=TaxOut, status_code=status.HTTP_201_CREATED)
def create_local_tax(
    tax_data: TaxCreate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Crear un impuesto local para la empresa
    
    Solo propietarios y administradores pueden crear impuestos locales.
    Los impuestos globales (DIAN) no se pueden crear desde este endpoint.
    
    Ejemplos de impuestos locales:
    - ReteICA Medellín: 11x1000
    - Sobretasa bomberil: 5%
    - Impuestos municipales específicos
    """
    service = TaxService(db)
    return service.create_local_tax(tax_data, auth_context.tenant_id)


@taxes_router.get("/{tax_id}", response_model=TaxOut)
def get_tax(
    tax_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener detalles de un impuesto específico
    
    Puede ser un impuesto global (DIAN) o local de la empresa.
    """
    service = TaxService(db)
    return service.get_tax_by_id(tax_id, auth_context.tenant_id)


@taxes_router.patch("/{tax_id}", response_model=TaxOut)
def update_local_tax(
    tax_id: UUID,
    tax_update: TaxUpdate,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Actualizar un impuesto local
    
    Solo se pueden actualizar impuestos locales (creados por la empresa).
    Los impuestos globales (DIAN) no son editables.
    
    Restricciones:
    - Solo propietarios y administradores
    - Solo impuestos con is_editable=true
    - Solo impuestos que pertenezcan a la empresa
    """
    service = TaxService(db)
    return service.update_local_tax(tax_id, tax_update, auth_context.tenant_id)


@taxes_router.delete("/{tax_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_local_tax(
    tax_id: UUID,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Eliminar un impuesto local
    
    Solo se pueden eliminar impuestos locales que no estén en uso.
    
    Restricciones:
    - Solo propietarios y administradores
    - Solo impuestos con is_editable=true
    - Solo impuestos que pertenezcan a la empresa
    - El impuesto no debe estar asignado a ningún producto
    """
    service = TaxService(db)
    service.delete_local_tax(tax_id, auth_context.tenant_id)


@taxes_router.post("/calculate", response_model=List[TaxCalculation])
def calculate_taxes(
    base_amount: float = Query(..., ge=0, description="Base gravable"),
    tax_ids: List[UUID] = Query(..., description="IDs de los impuestos a calcular"),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant"]))
):
    """
    Calcular impuestos para una base gravable
    
    Utilidad para calcular el valor de impuestos antes de crear facturas.
    
    Parámetros:
    - base_amount: Valor base sobre el cual calcular los impuestos
    - tax_ids: Lista de IDs de impuestos a aplicar
    
    Retorna:
    - Lista con el cálculo de cada impuesto
    - Incluye base gravable, tasa, y valor del impuesto
    """
    from decimal import Decimal
    service = TaxService(db)
    return service.calculate_taxes(Decimal(str(base_amount)), tax_ids, auth_context.tenant_id)