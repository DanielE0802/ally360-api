"""
Modelos SQLAlchemy para el módulo de Contactos

Este módulo centraliza la gestión de clientes y proveedores en una única entidad Contact:
- Clasificación por tipo: client, provider, o ambos
- Validaciones fiscales para Colombia (NIT con DV, CC, régimen)
- Integración con Invoices (clientes) y Bills (proveedores)
- Soft delete y restore para auditabilidad
- Adjuntos opcionales para documentos

Arquitectura multi-tenant: Todas las tablas incluyen company_id
Reemplaza las entidades Customer (invoices) y Supplier (bills)
"""

from app.database.database import Base
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Integer, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, ARRAY as PG_ARRAY
from uuid import uuid4
from app.common.mixins import TenantMixin, TimestampMixin
import enum


# ===== ENUMS =====

class ContactType(enum.Enum):
    """Tipos de contacto"""
    CLIENT = "client"      # Cliente (para facturas de venta)
    PROVIDER = "provider"  # Proveedor (para facturas de compra)


class IdType(enum.Enum):
    """Tipos de documento de identidad en Colombia"""
    CC = "CC"           # Cédula de Ciudadanía
    NIT = "NIT"         # Número de Identificación Tributaria
    CE = "CE"           # Cédula de Extranjería
    PASSPORT = "PASSPORT"  # Pasaporte


class PersonType(enum.Enum):
    """Tipo de persona"""
    NATURAL = "natural"    # Persona natural
    JURIDICA = "juridica"  # Persona jurídica


# ===== MODELOS =====

class Contact(Base, TenantMixin, TimestampMixin):
    """
    Contactos unificados (Clientes y Proveedores)
    
    Centraliza la gestión de todos los terceros de la empresa:
    - Clientes: type contiene 'client' 
    - Proveedores: type contiene 'provider'
    - Mixtos: type contiene ambos ['client', 'provider']
    
    Incluye validaciones fiscales específicas para Colombia.
    """
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Información básica
    name = Column(String(200), nullable=False, index=True)
    type = Column(PG_ARRAY(String), nullable=False, index=True)  # ['client'], ['provider'], o ambos
    email = Column(String(100), nullable=True, index=True)
    
    # Teléfonos
    phone_primary = Column(String(50), nullable=True)
    phone_secondary = Column(String(50), nullable=True) 
    mobile = Column(String(50), nullable=True)
    
    # Identificación fiscal
    id_type = Column(String(20), nullable=True)  # CC, NIT, CE, PASSPORT
    id_number = Column(String(50), nullable=True, index=True)
    dv = Column(String(2), nullable=True)  # Dígito de verificación para NIT
    person_type = Column(String(20), nullable=True)  # natural, juridica
    fiscal_responsibilities = Column(PG_ARRAY(String), nullable=True)  # Responsabilidades fiscales DIAN
    
    # Términos comerciales
    payment_terms_days = Column(Integer, nullable=False, default=0)  # Días de plazo de pago
    credit_limit = Column(Numeric(15, 2), nullable=True)  # Límite de crédito
    
    # Referencias a otros módulos
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Vendedor asignado
    price_list_id = Column(UUID(as_uuid=True), nullable=True)  # Lista de precios (futuro)
    
    # Direcciones (JSON flexible)
    billing_address = Column(JSON, nullable=True)   # {line1, city, depto, country}
    shipping_address = Column(JSON, nullable=True)  # {line1, city, depto, country}
    
    # Notas y estado
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)  # Soft delete
    
    # Auditoría
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    seller = relationship("User", foreign_keys=[seller_id])
    created_by_user = relationship("User", foreign_keys=[created_by])
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    attachments = relationship("ContactAttachment", back_populates="contact", cascade="all, delete-orphan")

    __table_args__ = (
        # Documento único por empresa (si se proporciona)
        # UniqueConstraint("tenant_id", "id_number", name="uq_contact_tenant_id_number"),
    )

    def is_client(self) -> bool:
        """Verificar si el contacto es cliente"""
        return ContactType.CLIENT.value in (self.type or [])
    
    def is_provider(self) -> bool:
        """Verificar si el contacto es proveedor"""
        return ContactType.PROVIDER.value in (self.type or [])
    
    def is_active_contact(self) -> bool:
        """Verificar si el contacto está activo (no soft deleted)"""
        return self.is_active and self.deleted_at is None


class ContactAttachment(Base, TenantMixin, TimestampMixin):
    """
    Adjuntos de contactos
    
    Permite asociar archivos a los contactos (RUT, cámaras de comercio, etc.)
    Integra con el módulo de files para el almacenamiento.
    """
    __tablename__ = "contact_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True)
    
    # Información del archivo
    file_url = Column(String(500), nullable=False)  # URL del archivo en MinIO
    file_name = Column(String(200), nullable=False)  # Nombre original del archivo
    file_size = Column(Integer, nullable=True)  # Tamaño en bytes
    content_type = Column(String(100), nullable=True)  # MIME type
    
    # Metadatos
    description = Column(String(500), nullable=True)  # Descripción del adjunto
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    contact = relationship("Contact", back_populates="attachments")
    uploaded_by_user = relationship("User")


# ===== FUNCIONES AUXILIARES =====

def calculate_nit_dv(nit: str) -> str:
    """
    Calcular dígito de verificación para NIT colombiano
    
    Algoritmo oficial de la DIAN para validación de NIT.
    """
    if not nit or not nit.isdigit():
        return ""
    
    # Pesos para el cálculo
    weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    
    # Tomar solo los dígitos del NIT (sin DV)
    nit_digits = nit.replace("-", "").replace(".", "")
    
    if len(nit_digits) > 15:
        return ""
    
    # Calcular suma ponderada
    total = 0
    for i, digit in enumerate(reversed(nit_digits)):
        if i < len(weights):
            total += int(digit) * weights[i]
    
    # Calcular DV
    remainder = total % 11
    if remainder < 2:
        return str(remainder)
    else:
        return str(11 - remainder)


def validate_nit_with_dv(nit: str, dv: str) -> bool:
    """
    Validar NIT con su dígito de verificación
    """
    if not nit or not dv:
        return False
    
    calculated_dv = calculate_nit_dv(nit)
    return calculated_dv == dv.strip()


def is_valid_email(email: str) -> bool:
    """
    Validación básica de email
    """
    if not email:
        return False
    
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))