"""
Esquemas Pydantic para el módulo de Contactos

Define la validación de datos de entrada y salida para:
- Contact: Entidad unificada de clientes y proveedores
- ContactAttachment: Adjuntos de documentos
- Validaciones fiscales específicas para Colombia (NIT con DV)
- Soft delete y restore
- Integración con otros módulos del ERP

Todas las validaciones respetan la arquitectura multi-tenant.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import date, datetime
from enum import Enum
from app.modules.auth.schemas import UserOut
from app.common.validators import validate_colombia_phone, validate_colombia_cedula, validate_colombia_nit, format_colombia_phone, format_colombia_cedula, format_colombia_nit


# ===== ENUMS =====

class ContactType(str, Enum):
    CLIENT = "client"
    PROVIDER = "provider"


class IdType(str, Enum):
    CC = "CC"
    NIT = "NIT"
    CE = "CE"
    PASSPORT = "PASSPORT"


class PersonType(str, Enum):
    NATURAL = "natural"
    JURIDICA = "juridica"


# ===== ADDRESS SCHEMAS =====

class AddressBase(BaseModel):
    """Esquema base para direcciones (flexible y retrocompatible)

    Soporta tanto el formato simplificado como el anterior:
    - Simplificado: address, city, state, country, postal_code
    - Anterior: line1, line2, city, depto, country, postal_code
    Todos los campos son opcionales para permitir creaciones mínimas.
    """
    # Formato simplificado
    address: Optional[str] = Field(None, max_length=200, description="Dirección (línea completa)")
    state: Optional[str] = Field(None, max_length=100, description="Departamento/Estado")
    # Formato previo (retrocompatibilidad)
    line1: Optional[str] = Field(None, max_length=200, description="Dirección línea 1 (legacy)")
    line2: Optional[str] = Field(None, max_length=200, description="Dirección línea 2 (legacy)")
    depto: Optional[str] = Field(None, max_length=100, description="Departamento (legacy)")
    # Comunes
    city: Optional[str] = Field(None, max_length=100, description="Ciudad")
    country: Optional[str] = Field("CO", min_length=2, max_length=3, description="Código país (ISO)")
    postal_code: Optional[str] = Field(None, max_length=20, description="Código postal")


# ===== CONTACT SCHEMAS =====

class ContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nombre del contacto")
    type: Optional[List[ContactType]] = Field(None, min_items=1, description="Tipo de contacto: client, provider o ambos")
    email: Optional[str] = Field(None, max_length=100, description="Email del contacto")
    
    # Teléfonos
    phone_primary: Optional[str] = Field(None, max_length=50, description="Teléfono principal")
    phone_secondary: Optional[str] = Field(None, max_length=50, description="Teléfono secundario") 
    mobile: Optional[str] = Field(None, max_length=50, description="Celular")
    
    # Identificación fiscal
    id_type: Optional[IdType] = Field(None, description="Tipo de documento")
    id_number: Optional[str] = Field(None, max_length=50, description="Número de documento")
    dv: Optional[str] = Field(None, max_length=2, description="Dígito de verificación (solo NIT)")
    person_type: Optional[PersonType] = Field(None, description="Tipo de persona")
    fiscal_responsibilities: Optional[List[str]] = Field(None, description="Responsabilidades fiscales DIAN")
    
    # Términos comerciales
    payment_terms_days: int = Field(0, ge=0, le=365, description="Días de plazo de pago")
    credit_limit: Optional[Decimal] = Field(None, ge=0, description="Límite de crédito")
    
    # Referencias
    seller_id: Optional[UUID] = Field(None, description="ID del vendedor asignado")
    price_list_id: Optional[UUID] = Field(None, description="ID de lista de precios")
    
    # Direcciones
    billing_address: Optional[AddressBase] = Field(None, description="Dirección de facturación")
    shipping_address: Optional[AddressBase] = Field(None, description="Dirección de envío")
    
    # Notas
    notes: Optional[str] = Field(None, description="Notas adicionales")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and v.strip():
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, v):
                raise ValueError('Email debe tener formato válido')
        return v

    @field_validator('phone_primary')
    @classmethod
    def validate_phone_primary(cls, v):
        if v is None or v.strip() == "":
            return v
        if not validate_colombia_phone(v):
            raise ValueError(
                'Teléfono principal inválido. Use formato colombiano: '
                '+573XXXXXXXXX (móvil) o +571XXXXXXX (fijo), también acepta sin +57'
            )
        return format_colombia_phone(v)

    @field_validator('phone_secondary')
    @classmethod
    def validate_phone_secondary(cls, v):
        if v is None or v.strip() == "":
            return v
        if not validate_colombia_phone(v):
            raise ValueError(
                'Teléfono secundario inválido. Use formato colombiano: '
                '+573XXXXXXXXX (móvil) o +571XXXXXXX (fijo), también acepta sin +57'
            )
        return format_colombia_phone(v)

    @field_validator('mobile')
    @classmethod
    def validate_mobile(cls, v):
        if v is None or v.strip() == "":
            return v
        if not validate_colombia_phone(v):
            raise ValueError(
                'Celular inválido. Use formato colombiano: '
                '+573XXXXXXXXX, también acepta sin +57'
            )
        return format_colombia_phone(v)

    @field_validator('id_number')
    @classmethod
    def validate_id_number(cls, v):
        if v is None or v.strip() == "":
            return v
        
        # Para CC (Cédula de Ciudadanía), validar como cédula colombiana
        # Para NIT, se validará en el model_validator junto con el DV
        v_clean = v.strip()
        
        # Si es solo números y longitud de cédula, validar como cédula
        if v_clean.isdigit() and 7 <= len(v_clean) <= 10:
            if not validate_colombia_cedula(v_clean):
                raise ValueError(
                    'Cédula inválida. Debe ser una cédula colombiana válida '
                    '(7-10 dígitos, no puede empezar con 0)'
                )
            return format_colombia_cedula(v_clean)
        
        # Para NITs con guión, validar completo
        if '-' in v_clean:
            if not validate_colombia_nit(v_clean):
                raise ValueError(
                    'NIT inválido. Debe ser un NIT colombiano válido con dígito de verificación correcto. '
                    'Formato: XXXXXXXXX-X'
                )
            return format_colombia_nit(v_clean)
        
        return v

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        # Si no se especifica, por defecto es cliente (creación mínima)
        if not v or len(v) == 0:
            return [ContactType.CLIENT]
        # Eliminar duplicados manteniendo orden
        seen = set()
        unique_types = []
        for contact_type in v:
            if contact_type not in seen:
                seen.add(contact_type)
                unique_types.append(contact_type)
        return unique_types

    @model_validator(mode='after')
    def validate_nit_requirements(self):
        id_type = self.id_type
        id_number = self.id_number
        dv = self.dv
        person_type = self.person_type

        # Si es NIT, validar solo si se proporciona DV
        if id_type == IdType.NIT:
            if not id_number:
                raise ValueError('id_number es requerido para tipo NIT')
            
            # DV es opcional - solo validar si se proporciona
            if dv:
                # Validar DV calculado
                from app.modules.contacts.models import calculate_nit_dv
                calculated_dv = calculate_nit_dv(id_number)
                if calculated_dv != dv:
                    raise ValueError(f'Dígito de verificación incorrecto. Debería ser: {calculated_dv}')
        
        # Si no es NIT, ignorar DV si viene
        elif dv:
            self.dv = None

        # Validación consistencia person_type vs id_type
        if id_type == IdType.NIT and person_type == PersonType.NATURAL:
            # NIT generalmente es para personas jurídicas, pero permitimos naturales con NIT
            pass
        elif id_type == IdType.CC and person_type == PersonType.JURIDICA:
            raise ValueError('Personas jurídicas no pueden usar Cédula de Ciudadanía')

        # Default de person_type cuando no es NIT y no se especifica
        if id_type != IdType.NIT and person_type is None:
            self.person_type = PersonType.NATURAL

        return self

    @field_validator('person_type', mode='before')
    @classmethod
    def normalize_person_type(cls, v):
        # Aceptar valores en mayúsculas y normalizarlos
        if v is None:
            return v
        if isinstance(v, str):
            lower = v.strip().lower()
            if lower in (PersonType.NATURAL.value, PersonType.JURIDICA.value):
                return PersonType(lower)
        if isinstance(v, PersonType):
            return v
        raise ValueError("Input should be 'natural' or 'juridica'")

    @field_validator('credit_limit')
    @classmethod
    def validate_credit_limit(cls, v):
        if v is not None:
            return v.quantize(Decimal('0.01'))
        return v


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[List[ContactType]] = Field(None, min_items=1)
    email: Optional[str] = Field(None, max_length=100)
    
    # Teléfonos
    phone_primary: Optional[str] = Field(None, max_length=50)
    phone_secondary: Optional[str] = Field(None, max_length=50)
    mobile: Optional[str] = Field(None, max_length=50)
    
    # Identificación fiscal
    id_type: Optional[IdType] = None
    id_number: Optional[str] = Field(None, max_length=50)
    dv: Optional[str] = Field(None, max_length=2)
    person_type: Optional[PersonType] = None
    fiscal_responsibilities: Optional[List[str]] = None
    
    # Términos comerciales
    payment_terms_days: Optional[int] = Field(None, ge=0, le=365)
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    
    # Referencias
    seller_id: Optional[UUID] = None
    price_list_id: Optional[UUID] = None
    
    # Direcciones
    billing_address: Optional[AddressBase] = None
    shipping_address: Optional[AddressBase] = None
    
    # Notas
    notes: Optional[str] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and v.strip():
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, v):
                raise ValueError('Email debe tener formato válido')
        return v

    @model_validator(mode='after')
    def validate_nit_requirements(self):
        # Solo validar si se están actualizando los campos relevantes
        id_type = self.id_type
        id_number = self.id_number
        dv = self.dv

        if id_type == IdType.NIT and id_number is not None:
            # DV es opcional - solo validar si se proporciona
            if dv:
                from app.modules.contacts.models import calculate_nit_dv
                calculated_dv = calculate_nit_dv(id_number)
                if calculated_dv != dv:
                    raise ValueError(f'Dígito de verificación incorrecto. Debería ser: {calculated_dv}')

        return self


class ContactOut(ContactBase):
    # En respuestas, siempre habrá tipo definido
    type: List[ContactType]
    id: UUID
    is_active: bool
    deleted_at: Optional[datetime]
    created_by: UUID
    updated_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactDetail(ContactOut):
    """Esquema detallado con relaciones"""
    seller: Optional[UserOut] = None
    created_by_user: Optional[UserOut] = None
    updated_by_user: Optional[UserOut] = None
    attachments: List['ContactAttachmentOut'] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ContactList(BaseModel):
    items: List[ContactOut]
    total: int
    limit: int
    offset: int


# ===== ATTACHMENT SCHEMAS =====

class ContactAttachmentBase(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=200, description="Nombre del archivo")
    description: Optional[str] = Field(None, max_length=500, description="Descripción del adjunto")


class ContactAttachmentCreate(ContactAttachmentBase):
    file_url: str = Field(..., min_length=1, max_length=500, description="URL del archivo")
    file_size: Optional[int] = Field(None, ge=0, description="Tamaño en bytes")
    content_type: Optional[str] = Field(None, max_length=100, description="Tipo MIME")


class ContactAttachmentOut(ContactAttachmentBase):
    id: UUID
    contact_id: UUID
    file_url: str
    file_size: Optional[int]
    content_type: Optional[str]
    uploaded_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ===== UTILITY SCHEMAS =====

class ContactSearchFilters(BaseModel):
    """Filtros para búsqueda de contactos"""
    search: Optional[str] = Field(None, description="Buscar por nombre, email o documento")
    type: Optional[ContactType] = Field(None, description="Filtrar por tipo")
    is_active: Optional[bool] = Field(None, description="Filtrar por estado activo")
    seller_id: Optional[UUID] = Field(None, description="Filtrar por vendedor")


class ContactRestore(BaseModel):
    """Esquema para restaurar contacto"""
    reason: Optional[str] = Field(None, max_length=500, description="Razón de la restauración")


class ContactBulkAction(BaseModel):
    """Esquema para acciones en lote"""
    contact_ids: List[UUID] = Field(..., min_items=1, description="IDs de contactos")
    action: str = Field(..., description="Acción a realizar: delete, restore, export")
    reason: Optional[str] = Field(None, max_length=500, description="Razón de la acción")


class ContactStats(BaseModel):
    """Estadísticas de contactos"""
    total_contacts: int
    active_contacts: int
    clients: int
    providers: int
    mixed: int  # Contactos que son cliente y proveedor
    deleted_contacts: int


# ===== INTEGRATION SCHEMAS =====

class ContactForInvoice(BaseModel):
    """Esquema simplificado para uso en facturas"""
    id: UUID
    name: str
    email: Optional[str]
    id_type: Optional[str]
    id_number: Optional[str]
    dv: Optional[str]
    payment_terms_days: int
    billing_address: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class ContactForBill(BaseModel):
    """Esquema simplificado para uso en compras"""
    id: UUID
    name: str
    email: Optional[str]
    id_type: Optional[str]
    id_number: Optional[str]
    payment_terms_days: int

    class Config:
        from_attributes = True


# Forward references
ContactDetail.model_rebuild()