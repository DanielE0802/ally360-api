# Ally360 API - Multi-Tenant Implementation Guide

This document explains how the multi-tenant, scalable architecture is implemented and how to use it.

## 🏗️ Architecture Overview

### Multi-Tenancy
- **TenantMiddleware**: Extracts `tenant_id` from `X-Company-ID` header
- **TenantMixin**: Adds `tenant_id` to all business models
- **TenantContext**: Provides tenant-scoped dependencies for endpoints
- All queries are automatically scoped by `tenant_id`

### Components Implemented

1. **Database Layer**
   - Async SQLAlchemy with AsyncPG driver
   - Sync engine for migrations
   - Tenant-scoped queries
   - UUID primary keys
   - Audit fields (created_at, updated_at, deleted_at)

2. **File Storage (MinIO)**
   - Presigned URLs for secure upload/download
   - Structured file paths: `{tenant_id}/{module}/{yyyy}/{mm}/{dd}/{uuid}-{filename}`
   - File metadata stored in database
   - Background tasks for processing

3. **Background Processing (Celery + Redis)**
   - File virus scanning
   - Thumbnail generation
   - Cleanup tasks
   - Async task queues

4. **Security & Middleware**
   - Tenant isolation middleware
   - Security headers
   - Rate limiting ready
   - CORS configuration

## 🚀 Usage Examples

### 1. Making API Requests

All business endpoints require the `X-Company-ID` header:

```bash
# Login (no tenant required)
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123"

# Use token and company ID for business operations
curl -X GET "http://localhost:8000/products/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "X-Company-ID: 550e8400-e29b-41d4-a716-446655440000"
```

### 2. File Upload Flow

```python
# 1. Request presigned upload URL
upload_request = {
    "filename": "product_image.jpg",
    "content_type": "image/jpeg",
    "module": "products",
    "description": "Product main image"
}

response = await client.post(
    "/files/upload/presign",
    json=upload_request,
    headers={"X-Company-ID": tenant_id}
)

# 2. Upload file directly to MinIO using presigned URL
files = {"file": ("product_image.jpg", file_data, "image/jpeg")}
upload_response = requests.put(response.json()["upload_url"], files=files)

# 3. File is automatically processed in background
# - Virus scanning
# - Thumbnail generation
# - Size verification
```

### 3. Creating Tenant-Safe Endpoints

```python
from fastapi import APIRouter
from app.dependencies.companyDependencies import TenantId, TenantContext
from app.dependencies.dbDependecies import async_db_dependency

router = APIRouter()

@router.get("/products/")
async def list_products(
    tenant_id: TenantId,  # Automatically extracted from header
    tenant_context: TenantContext,  # Includes user validation
    db: async_db_dependency
):
    # Query is automatically scoped to tenant
    query = select(Product).where(Product.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalars().all()
```

### 4. Using Background Tasks

```python
from app.modules.files.tasks import scan_file_for_virus

# Schedule a background task
scan_file_for_virus.delay(
    tenant_id=str(tenant_id),
    file_id=str(file_id),
    file_key=file_key
)
```

## 🔧 Development Setup

### 1. Environment Variables

Create `.env` file:

```env
# Database
POSTGRES_USER=ally_user
POSTGRES_PASSWORD=ally_pass
POSTGRES_DB=ally_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# MinIO
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=ally360
MINIO_USE_SSL=false

# JWT
APP_SECRET_STRING=your-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
ENVIRONMENT=development
DEBUG=true
```

### 2. Start Services

```bash
# Start all services
docker-compose up --build

# Or start individual services
docker-compose up postgres redis minio
docker-compose up api
docker-compose up celery-worker celery-beat
```

### 3. Database Migrations

```bash
# Install alembic
pip install alembic

# Initialize migrations (already done)
# alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add tenant support"

# Apply migrations
alembic upgrade head
```

## 📊 Performance Considerations

### Database
- Use async endpoints for I/O operations
- Implement cursor-based pagination for large datasets
- Add composite indexes on `(tenant_id, other_columns)`
- Use connection pooling (PgBouncer in production)

### File Storage
- Use presigned URLs to avoid proxy traffic through API
- Implement CDN for file downloads in production
- Set appropriate file size limits
- Use background tasks for heavy processing

### Caching
- Redis for session data and rate limiting
- Cache frequently accessed tenant settings
- Implement cache invalidation strategies

## 🛡️ Security Features

### Tenant Isolation
- Middleware enforces tenant header
- All queries filtered by tenant_id
- User-tenant relationship validation
- File access scoped to tenant

### File Security
- File type validation
- Size limits
- Virus scanning (background)
- Presigned URL expiration
- Structured storage paths

### Rate Limiting (Ready for implementation)
```python
# Example rate limiting decorator
@router.get("/products/")
@rate_limit("100/minute", per_tenant=True)
async def list_products(...):
    pass
```

## 🔍 Monitoring & Logging

All components include structured logging:

```python
import logging
logger = logging.getLogger(__name__)

# In endpoints
logger.info(f"Product created for tenant {tenant_id}", extra={
    "tenant_id": tenant_id,
    "user_id": user_id,
    "product_id": product.id
})
```

## 📈 Scaling Recommendations

### Horizontal Scaling
- API servers are stateless and can be scaled horizontally
- Use load balancer with session affinity if needed
- Separate Celery workers by task type

### Database Scaling
- Implement read replicas for read-heavy workloads
- Consider sharding by tenant_id for very large datasets
- Use PgBouncer for connection pooling

### File Storage Scaling
- MinIO supports clustering for high availability
- Implement lifecycle policies for old files
- Use CDN for global file distribution

## 🧪 Testing Strategy

### Unit Tests
- Test tenant isolation in all CRUD operations
- Verify middleware behavior
- Test file upload/download flows

### Integration Tests
- Multi-tenant data isolation
- End-to-end file workflows
- Background task execution

### Load Testing
- API endpoint performance under load
- File upload/download throughput
- Celery task processing capacity

## 🚀 Production Deployment

### Database
- Use managed PostgreSQL (AWS RDS, etc.)
- Enable connection pooling
- Set up backup and recovery
- Monitor query performance

### File Storage
- Use managed MinIO or S3
- Enable versioning and lifecycle policies
- Set up backup strategies
- Configure CDN

### Background Jobs
- Use separate Celery worker instances
- Monitor queue lengths and processing times
- Set up error handling and retries
- Scale workers based on load

### Monitoring
- Application performance monitoring (APM)
- Database monitoring
- File storage monitoring  
- Celery monitoring

This architecture provides a solid foundation for a scalable, multi-tenant SaaS application. Each component is designed to handle growth and can be optimized or replaced as needs evolve.