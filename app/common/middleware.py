"""
Middleware for handling multi-tenancy
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant_id from X-Company-ID header
    and sets it on request.state for use in endpoint handlers
    """
    
    # Paths that don't require tenant context
    EXEMPT_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/auth/login",
        "/auth/register",
        "/health",
        "/"
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Skip tenant validation for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
            
        # Skip for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Extract tenant_id from header
        tenant_header = request.headers.get("X-Company-ID")
        
        if not tenant_header:
            return Response(
                content='{"detail":"Missing X-Company-ID header"}',
                status_code=status.HTTP_400_BAD_REQUEST,
                media_type="application/json"
            )
        
        try:
            tenant_id = UUID(tenant_header)
            request.state.tenant_id = tenant_id
            
            # Log tenant context for debugging
            logger.debug(f"Request to {request.url.path} with tenant_id: {tenant_id}")
            
        except ValueError:
            return Response(
                content='{"detail":"Invalid X-Company-ID format. Must be a valid UUID"}',
                status_code=status.HTTP_400_BAD_REQUEST,
                media_type="application/json"
            )
        
        response = await call_next(request)
        
        # Add tenant ID to response headers for debugging
        response.headers["X-Tenant-ID"] = str(tenant_id)
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers for production
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response