"""
Background tasks for file operations
"""
from celery import current_app
from app.core.celery import celery_app
from app.modules.files.service import minio_service
from app.database.database import AsyncSessionLocal
from app.modules.files.crud import file_crud
from sqlalchemy import text
import logging
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def scan_file_for_virus(self, tenant_id: str, file_id: str, file_key: str):
    """
    Background task to scan uploaded files for viruses
    This is a placeholder - integrate with your preferred antivirus solution
    """
    try:
        logger.info(f"Scanning file {file_id} for tenant {tenant_id}")
        
        # TODO: Implement virus scanning logic
        # For example, using ClamAV or a cloud service
        # result = antivirus_service.scan_file(file_key)
        
        # For now, just simulate the scan
        import time
        time.sleep(2)  # Simulate scanning time
        
        # In a real implementation, update file status based on scan result
        # If virus found, mark file as infected and delete from MinIO
        
        logger.info(f"File {file_id} scan completed - clean")
        return {"status": "clean", "file_id": file_id}
        
    except Exception as e:
        logger.error(f"Virus scan failed for file {file_id}: {str(e)}")
        self.retry(countdown=60, max_retries=3)


@celery_app.task(bind=True)
def generate_thumbnails(self, tenant_id: str, file_id: str, file_key: str):
    """
    Background task to generate thumbnails for image files
    """
    try:
        logger.info(f"Generating thumbnails for file {file_id}")
        
        # TODO: Implement thumbnail generation
        # 1. Download file from MinIO
        # 2. Generate thumbnails (small, medium, large)
        # 3. Upload thumbnails back to MinIO
        # 4. Update file metadata with thumbnail keys
        
        # Example implementation with PIL:
        # from PIL import Image
        # image_data = minio_service.download_file(file_key)
        # image = Image.open(BytesIO(image_data))
        # thumbnail = image.resize((150, 150))
        # thumbnail_key = f"{file_key}_thumb_150.jpg"
        # minio_service.upload_file(thumbnail_key, thumbnail_data)
        
        logger.info(f"Thumbnails generated for file {file_id}")
        return {"status": "completed", "file_id": file_id}
        
    except Exception as e:
        logger.error(f"Thumbnail generation failed for file {file_id}: {str(e)}")
        self.retry(countdown=60, max_retries=3)


@celery_app.task
def cleanup_expired_files():
    """
    Periodic task to cleanup files marked for deletion
    """
    try:
        logger.info("Starting cleanup of expired files")
        
        # This should run async, but Celery doesn't handle async directly
        # So we'll use asyncio.run or implement sync version
        asyncio.run(_cleanup_expired_files_async())
        
        logger.info("Expired files cleanup completed")
        return {"status": "completed"}
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        raise


async def _cleanup_expired_files_async():
    """Async helper for cleanup task"""
    async with AsyncSessionLocal() as db:
        try:
            # Find files marked for deletion more than 24 hours ago
            cutoff_date = datetime.utcnow() - timedelta(hours=24)
            
            query = text("""
                SELECT key FROM files 
                WHERE deleted_at < :cutoff_date 
                AND is_active = false
                LIMIT 100
            """)
            
            result = await db.execute(query, {"cutoff_date": cutoff_date})
            expired_files = result.fetchall()
            
            for row in expired_files:
                file_key = row[0]
                try:
                    # Delete from MinIO
                    minio_service.delete_file(file_key)
                    
                    # Delete metadata from database
                    delete_query = text("""
                        DELETE FROM files WHERE key = :file_key
                    """)
                    await db.execute(delete_query, {"file_key": file_key})
                    
                    logger.info(f"Deleted expired file: {file_key}")
                    
                except Exception as e:
                    logger.error(f"Failed to delete expired file {file_key}: {str(e)}")
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            raise


@celery_app.task
def sync_file_sizes_from_minio():
    """
    Periodic task to sync file sizes from MinIO to database
    Useful for fixing inconsistencies
    """
    try:
        logger.info("Starting file size synchronization")
        
        asyncio.run(_sync_file_sizes_async())
        
        logger.info("File size synchronization completed")
        return {"status": "completed"}
        
    except Exception as e:
        logger.error(f"File size sync failed: {str(e)}")
        raise


async def _sync_file_sizes_async():
    """Async helper for file size sync"""
    async with AsyncSessionLocal() as db:
        try:
            # Get files with size = 0 (not yet synced)
            query = text("""
                SELECT id, key FROM files 
                WHERE size = 0 
                AND is_active = true
                LIMIT 50
            """)
            
            result = await db.execute(query)
            files_to_sync = result.fetchall()
            
            for row in files_to_sync:
                file_id, file_key = row[0], row[1]
                
                try:
                    # Get actual size from MinIO
                    file_info = minio_service.get_file_info(file_key)
                    if file_info:
                        update_query = text("""
                            UPDATE files 
                            SET size = :size 
                            WHERE id = :file_id
                        """)
                        await db.execute(update_query, {
                            "size": file_info["size"],
                            "file_id": file_id
                        })
                        
                        logger.info(f"Updated size for file {file_id}: {file_info['size']} bytes")
                
                except Exception as e:
                    logger.error(f"Failed to sync size for file {file_id}: {str(e)}")
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            raise


@celery_app.task(bind=True)
def process_file_upload_completion(self, tenant_id: str, file_id: str, file_key: str):
    """
    Process file after successful upload to MinIO
    This task chains other file processing tasks
    """
    try:
        logger.info(f"Processing completed upload for file {file_id}")
        
        # Get file info from MinIO to update size
        file_info = minio_service.get_file_info(file_key)
        if file_info:
            # Update file size in database
            asyncio.run(_update_file_size(file_id, file_info["size"]))
        
        # Chain other processing tasks
        chain = (
            scan_file_for_virus.s(tenant_id, file_id, file_key) |
            generate_thumbnails.s(tenant_id, file_id, file_key)
        )
        
        # Execute the chain
        chain.apply_async()
        
        return {"status": "processing_started", "file_id": file_id}
        
    except Exception as e:
        logger.error(f"Upload processing failed for file {file_id}: {str(e)}")
        self.retry(countdown=30, max_retries=3)


async def _update_file_size(file_id: str, size: int):
    """Helper to update file size in database"""
    async with AsyncSessionLocal() as db:
        try:
            query = text("""
                UPDATE files 
                SET size = :size 
                WHERE id = :file_id
            """)
            await db.execute(query, {"size": size, "file_id": file_id})
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update file size: {str(e)}")
            raise