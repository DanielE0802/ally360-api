"""
Common mixins for multi-tenant models
"""
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from uuid import uuid4


class TenantMixin:
    """Mixin for multi-tenant models that adds tenant_id and ensures tenant isolation"""
    
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    @classmethod
    def __declare_last__(cls):
        """Add tenant_id to all unique constraints"""
        if hasattr(cls, '__table_args__'):
            table_args = list(cls.__table_args__)
            # Add index on tenant_id for better query performance
            from sqlalchemy import Index
            table_args.append(Index(f"idx_{cls.__tablename__}_tenant", "tenant_id"))
            cls.__table_args__ = tuple(table_args)


class TimestampMixin:
    """Mixin for models that need timestamp tracking"""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class BaseMixin(TenantMixin, TimestampMixin):
    """Combines tenant and timestamp functionality for most business models"""
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    is_active = Column(Boolean, default=True, nullable=False)


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    def soft_delete(self):
        self.deleted_at = func.now()
        self.is_active = False
    
    def restore(self):
        self.deleted_at = None
        self.is_active = True