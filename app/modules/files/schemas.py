"""
Pydantic schemas for file operations
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class FileUploadRequest(BaseModel):
    """Request to get a presigned upload URL"""
    filename: str = Field(..., description="Original filename with extension")
    content_type: str = Field(..., description="MIME type of the file")
    module: str = Field(..., description="Module context (products, companies, etc.)")
    description: Optional[str] = Field(None, description="Optional file description")
    tags: Optional[List[str]] = Field(None, description="Optional tags for the file")


class FileUploadResponse(BaseModel):
    """Response with presigned upload URL and metadata"""
    file_id: UUID
    upload_url: str
    key: str
    expires_in: int = Field(description="URL expiration time in seconds")


class FileDownloadResponse(BaseModel):
    """Response with presigned download URL"""
    download_url: str
    filename: str
    content_type: str
    size: int
    expires_in: int = Field(description="URL expiration time in seconds")


class FileMetadataOut(BaseModel):
    """File metadata output schema"""
    id: UUID
    original_filename: str
    content_type: str
    size: int
    module: str
    description: Optional[str]
    tags: Optional[List[str]]
    uploaded_by: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Paginated file list response"""
    files: List[FileMetadataOut]
    total: int
    page: int
    page_size: int
    has_next: bool


class FileUpdateRequest(BaseModel):
    """Request to update file metadata"""
    description: Optional[str] = None
    tags: Optional[List[str]] = None