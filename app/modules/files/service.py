"""
MinIO service for file operations with presigned URLs
"""
from minio import Minio
from minio.error import S3Error
from fastapi import HTTPException, status
from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import json
import logging

from app.core.config import settings
from app.modules.files.schemas import FileUploadRequest, FileUploadResponse, FileDownloadResponse

logger = logging.getLogger(__name__)


class MinIOService:
    """Service for handling MinIO operations with presigned URLs"""
    
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create if it doesn't"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
            
            # Set bucket policy for presigned URLs
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetBucketLocation"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}"]
                    }
                ]
            }
            
            self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            
        except S3Error as e:
            logger.error(f"MinIO bucket setup error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File storage service unavailable"
            )
    
    def generate_file_key(self, tenant_id: UUID, module: str, filename: str, file_id: UUID = None) -> str:
        """Generate MinIO object key with proper structure"""
        if not file_id:
            file_id = uuid4()
        
        now = datetime.utcnow()
        year = now.year
        month = f"{now.month:02d}"
        day = f"{now.day:02d}"
        
        # Structure: tenant_id/module/yyyy/mm/dd/file_id-filename
        key = f"{tenant_id}/{module}/{year}/{month}/{day}/{file_id}-{filename}"
        return key
    
    def get_presigned_upload_url(
        self, 
        tenant_id: UUID, 
        file_request: FileUploadRequest,
        expires: timedelta = timedelta(minutes=15)
    ) -> FileUploadResponse:
        """Generate presigned URL for file upload"""
        try:
            file_id = uuid4()
            key = self.generate_file_key(
                tenant_id=tenant_id,
                module=file_request.module,
                filename=file_request.filename,
                file_id=file_id
            )
            
            # Validate file size and type would be done here
            if file_request.content_type not in settings.ALLOWED_FILE_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type {file_request.content_type} not allowed"
                )
            
            upload_url = self.client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=key,
                expires=expires
            )
            
            return FileUploadResponse(
                file_id=file_id,
                upload_url=upload_url,
                key=key,
                expires_in=int(expires.total_seconds())
            )
            
        except S3Error as e:
            logger.error(f"MinIO upload URL generation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate upload URL"
            )
    
    def get_presigned_download_url(
        self, 
        key: str,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """Generate presigned URL for file download"""
        try:
            download_url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=key,
                expires=expires
            )
            return download_url
            
        except S3Error as e:
            logger.error(f"MinIO download URL generation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
    
    def delete_file(self, key: str) -> bool:
        """Delete file from MinIO"""
        try:
            self.client.remove_object(self.bucket_name, key)
            return True
        except S3Error as e:
            logger.error(f"MinIO file deletion error: {e}")
            return False
    
    def get_file_info(self, key: str) -> Optional[dict]:
        """Get file information from MinIO"""
        try:
            obj = self.client.stat_object(self.bucket_name, key)
            return {
                "size": obj.size,
                "etag": obj.etag,
                "last_modified": obj.last_modified,
                "content_type": obj.content_type
            }
        except S3Error:
            return None


# Singleton instance
minio_service = MinIOService()