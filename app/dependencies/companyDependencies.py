from typing import Annotated
from fastapi import Depends, Request, HTTPException, status
from uuid import UUID
from app.modules.company.utils import get_current_user_and_company
from app.dependencies.userDependencies import user_dependency
from app.modules.auth.models import User


def get_tenant_id(request: Request) -> UUID:
    """Extract tenant_id from request state set by TenantMiddleware"""
    if not hasattr(request.state, 'tenant_id'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context not found. Ensure X-Company-ID header is provided."
        )
    return request.state.tenant_id


def get_tenant_context(
    request: Request,
    current_user: user_dependency
) -> dict:
    """
    Get tenant context with user validation.
    Ensures the user has access to the requested tenant.
    """
    tenant_id = get_tenant_id(request)
    
    # TODO: Add validation to ensure user has access to this tenant
    # This should check UserCompany relationship
    
    return {
        "tenant_id": tenant_id,
        "user": current_user,
        "user_id": current_user.id
    }


# Legacy dependency for backward compatibility
UserCompanyContext = Annotated[dict, Depends(get_current_user_and_company)]

# New tenant-aware dependencies
TenantId = Annotated[UUID, Depends(get_tenant_id)]
TenantContext = Annotated[dict, Depends(get_tenant_context)]
