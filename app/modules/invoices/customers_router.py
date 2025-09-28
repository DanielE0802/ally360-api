from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.invoices.service import CustomerService
from app.modules.invoices.schemas import (
    CustomerCreate, CustomerUpdate, CustomerOut, CustomerList
)

customers_router = APIRouter(prefix="/customers", tags=["Customers"])


@customers_router.post("/", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Crear un nuevo cliente
    
    Solo propietarios, administradores y vendedores pueden crear clientes.
    El documento debe ser único por empresa.
    """
    service = CustomerService(db)
    return service.create_customer(customer_data, auth_context.tenant_id)


@customers_router.get("/", response_model=CustomerList)
def list_customers(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Buscar por nombre, email o documento"),
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Listar clientes con búsqueda opcional
    
    Permite buscar por nombre, email o documento.
    Todos los roles pueden ver los clientes.
    """
    service = CustomerService(db)
    return service.get_customers(auth_context.tenant_id, limit, offset, search)


@customers_router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller", "accountant", "viewer"]))
):
    """
    Obtener detalles de un cliente específico
    """
    service = CustomerService(db)
    return service.get_customer_by_id(customer_id, auth_context.tenant_id)


@customers_router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: UUID,
    customer_update: CustomerUpdate,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin", "seller"]))
):
    """
    Actualizar información de un cliente
    
    Solo propietarios, administradores y vendedores pueden actualizar clientes.
    """
    service = CustomerService(db)
    return service.update_customer(customer_id, customer_update, auth_context.tenant_id)


@customers_router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    auth_context = Depends(AuthDependencies.require_role(["owner", "admin"]))
):
    """
    Eliminar un cliente
    
    Solo propietarios y administradores pueden eliminar clientes.
    No se puede eliminar si el cliente tiene facturas asociadas.
    """
    service = CustomerService(db)
    service.delete_customer(customer_id, auth_context.tenant_id)