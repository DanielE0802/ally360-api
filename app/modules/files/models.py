"""
File models for MinIO metadata storage
"""
from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid import uuid4
from app.database.database import Base
from app.common.mixins import BaseMixin


class FileMetadata(Base, BaseMixin):
    """
    Stores metadata for files uploaded to MinIO
    """
    __tablename__ = "files"
    
    # Override id from BaseMixin to use our specific UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    
    # File metadata
    original_filename = Column(String(255), nullable=False)
    key = Column(String(500), nullable=False, unique=True, index=True)  # MinIO object key
    content_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    module = Column(String(50), nullable=False, index=True)  # e.g., 'products', 'companies', 'invoices'
    
    # Optional metadata
    description = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)  # JSON string of tags
    
    # Who uploaded it
    uploaded_by = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    @property
    def file_path(self):
        """Generate the expected MinIO path"""
        return f"{self.tenant_id}/{self.module}/{self.created_at.year}/{self.created_at.month:02d}/{self.created_at.day:02d}/{self.id}-{self.original_filename}"
    
    def __repr__(self):
        return f"<FileMetadata(id={self.id}, filename={self.original_filename}, size={self.size})>"