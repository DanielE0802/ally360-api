"""
CRUD operations for file metadata
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import json

from app.modules.files.models import FileMetadata
from app.modules.files.schemas import FileUploadRequest, FileUpdateRequest


class FileCRUD:
    """CRUD operations for file metadata"""
    
    async def create_file_metadata(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        file_id: UUID,
        key: str,
        upload_request: FileUploadRequest,
        uploaded_by: UUID,
        file_size: int = 0
    ) -> FileMetadata:
        """Create file metadata record"""
        
        tags_json = None
        if upload_request.tags:
            tags_json = json.dumps(upload_request.tags)
        
        file_metadata = FileMetadata(
            id=file_id,
            tenant_id=tenant_id,
            original_filename=upload_request.filename,
            key=key,
            content_type=upload_request.content_type,
            size=file_size,
            module=upload_request.module,
            description=upload_request.description,
            tags=tags_json,
            uploaded_by=uploaded_by
        )
        
        db.add(file_metadata)
        await db.commit()
        await db.refresh(file_metadata)
        return file_metadata
    
    async def get_file_by_id(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        file_id: UUID
    ) -> Optional[FileMetadata]:
        """Get file metadata by ID (tenant-scoped)"""
        query = select(FileMetadata).where(
            and_(
                FileMetadata.id == file_id,
                FileMetadata.tenant_id == tenant_id,
                FileMetadata.is_active == True
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_files_by_module(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        module: str,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[List[FileMetadata], int]:
        """Get files by module with pagination"""
        
        # Count query
        count_query = select(func.count(FileMetadata.id)).where(
            and_(
                FileMetadata.tenant_id == tenant_id,
                FileMetadata.module == module,
                FileMetadata.is_active == True
            )
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Data query
        query = select(FileMetadata).where(
            and_(
                FileMetadata.tenant_id == tenant_id,
                FileMetadata.module == module,
                FileMetadata.is_active == True
            )
        ).offset(offset).limit(limit).order_by(FileMetadata.created_at.desc())
        
        result = await db.execute(query)
        files = result.scalars().all()
        
        return files, total
    
    async def update_file_metadata(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        file_id: UUID,
        update_data: FileUpdateRequest
    ) -> Optional[FileMetadata]:
        """Update file metadata"""
        
        update_values = {}
        
        if update_data.description is not None:
            update_values['description'] = update_data.description
            
        if update_data.tags is not None:
            update_values['tags'] = json.dumps(update_data.tags)
        
        if not update_values:
            return await self.get_file_by_id(db, tenant_id, file_id)
        
        query = update(FileMetadata).where(
            and_(
                FileMetadata.id == file_id,
                FileMetadata.tenant_id == tenant_id,
                FileMetadata.is_active == True
            )
        ).values(**update_values).returning(FileMetadata)
        
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()
    
    async def soft_delete_file(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        file_id: UUID
    ) -> bool:
        """Soft delete file metadata"""
        query = update(FileMetadata).where(
            and_(
                FileMetadata.id == file_id,
                FileMetadata.tenant_id == tenant_id,
                FileMetadata.is_active == True
            )
        ).values(is_active=False, deleted_at=func.now())
        
        result = await db.execute(query)
        await db.commit()
        return result.rowcount > 0
    
    async def get_tenant_storage_usage(
        self,
        db: AsyncSession,
        tenant_id: UUID
    ) -> dict:
        """Get storage usage statistics for tenant"""
        query = select(
            func.count(FileMetadata.id).label('total_files'),
            func.sum(FileMetadata.size).label('total_size'),
            func.count(FileMetadata.id).filter(FileMetadata.module == 'products').label('product_files'),
            func.count(FileMetadata.id).filter(FileMetadata.module == 'invoices').label('invoice_files')
        ).where(
            and_(
                FileMetadata.tenant_id == tenant_id,
                FileMetadata.is_active == True
            )
        )
        
        result = await db.execute(query)
        stats = result.one()
        
        return {
            'total_files': stats.total_files or 0,
            'total_size': stats.total_size or 0,
            'product_files': stats.product_files or 0,
            'invoice_files': stats.invoice_files or 0
        }


file_crud = FileCRUD()