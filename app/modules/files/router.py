"""
File management router with presigned URLs
"""
from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from typing import List, Annotated
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_async_db
from app.dependencies.companyDependencies import TenantId, TenantContext
from app.modules.files import service, crud
from app.modules.files.schemas import (
    FileUploadRequest, FileUploadResponse, FileDownloadResponse,
    FileMetadataOut, FileListResponse, FileUpdateRequest
)

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload/presign", response_model=FileUploadResponse)
async def get_upload_url(
    upload_request: FileUploadRequest,
    tenant_id: TenantId,
    tenant_context: TenantContext,
    db: Annotated[AsyncSession, Depends(get_async_db)]
):
    """
    Generate a presigned URL for file upload.
    Client should use this URL to upload the file directly to MinIO.
    """
    # Generate presigned URL
    upload_response = service.minio_service.get_presigned_upload_url(
        tenant_id=tenant_id,
        file_request=upload_request
    )
    
    # Create metadata record
    await crud.file_crud.create_file_metadata(
        db=db,
        tenant_id=tenant_id,
        file_id=upload_response.file_id,
        key=upload_response.key,
        upload_request=upload_request,
        uploaded_by=tenant_context["user_id"]
    )
    
    return upload_response


@router.get("/{file_id}/download", response_model=FileDownloadResponse)
async def get_download_url(
    file_id: UUID,
    tenant_id: TenantId,
    db: async_db_dependency
):
    """
    Generate a presigned URL for file download.
    """
    # Get file metadata
    file_metadata = await crud.file_crud.get_file_by_id(db, tenant_id, file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Generate download URL
    download_url = service.minio_service.get_presigned_download_url(file_metadata.key)
    
    return FileDownloadResponse(
        download_url=download_url,
        filename=file_metadata.original_filename,
        content_type=file_metadata.content_type,
        size=file_metadata.size,
        expires_in=3600  # 1 hour
    )


@router.get("/", response_model=FileListResponse)
async def list_files(
    tenant_id: TenantId,
    db: async_db_dependency,
    module: str = None,
    page: int = 1,
    page_size: int = 20
):
    """
    List files for the tenant with optional module filtering.
    """
    if page_size > 100:
        page_size = 100
    
    offset = (page - 1) * page_size
    
    if module:
        files, total = await crud.file_crud.get_files_by_module(
            db, tenant_id, module, page_size, offset
        )
    else:
        # Implement get_all_files method if needed
        files, total = [], 0
    
    return FileListResponse(
        files=files,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total
    )


@router.get("/{file_id}", response_model=FileMetadataOut)
async def get_file_metadata(
    file_id: UUID,
    tenant_id: TenantId,
    db: async_db_dependency
):
    """Get file metadata without generating download URL."""
    file_metadata = await crud.file_crud.get_file_by_id(db, tenant_id, file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return file_metadata


@router.patch("/{file_id}", response_model=FileMetadataOut)
async def update_file_metadata(
    file_id: UUID,
    update_request: FileUpdateRequest,
    tenant_id: TenantId,
    db: async_db_dependency
):
    """Update file metadata (description, tags, etc.)."""
    updated_file = await crud.file_crud.update_file_metadata(
        db, tenant_id, file_id, update_request
    )
    if not updated_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return updated_file


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    tenant_id: TenantId,
    db: async_db_dependency,
    background_tasks: BackgroundTasks
):
    """Delete file (soft delete metadata + background MinIO cleanup)."""
    
    # Get file metadata first
    file_metadata = await crud.file_crud.get_file_by_id(db, tenant_id, file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Soft delete in database
    success = await crud.file_crud.soft_delete_file(db, tenant_id, file_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )
    
    # Schedule MinIO cleanup in background
    background_tasks.add_task(
        service.minio_service.delete_file,
        file_metadata.key
    )
    
    return {"detail": "File deleted successfully"}


@router.get("/stats/usage")
async def get_storage_usage(
    tenant_id: TenantId,
    db: async_db_dependency
):
    """Get storage usage statistics for the tenant."""
    return await crud.file_crud.get_tenant_storage_usage(db, tenant_id)