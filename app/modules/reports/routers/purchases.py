"""
Purchase Reports Router

FastAPI router for all purchase-related report endpoints.
Includes by supplier and by category reports.
"""

from datetime import date
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from ..services.purchases import PurchaseReportService
from ..schemas import (
    PurchasesBySupplierFilter,
    PurchasesBySupplierResponse,
    PurchasesByCategoryResponse
)
from ..utils import (
    create_csv_response,
    prepare_purchases_by_supplier_csv,
    prepare_purchases_by_category_csv,
    CSV_HEADERS
)


router = APIRouter(prefix="/reports/purchases", tags=["Reports"])


@router.get("/by-supplier", response_model=None)
async def get_purchases_by_supplier(
    start_date: date = Query(..., description="Start date for the report period"),
    end_date: date = Query(..., description="End date for the report period"),
    supplier_id: Optional[UUID] = Query(None, description="Filter by specific supplier"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """
    Generate purchases by supplier report.
    
    Returns suppliers ranked by total purchase amount.
    Includes supplier contact information and purchase statistics.
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
        # Create service instance
        service = PurchaseReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        # Validate PDV ownership if specified
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(
                status_code=404,
                detail="PDV not found or doesn't belong to your company"
            )
        
        # Generate report
        report_data = service.get_purchases_by_supplier(
            start_date=start_date,
            end_date=end_date,
            supplier_id=supplier_id,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        # Export as CSV if requested
        if export == "csv":
            csv_data = prepare_purchases_by_supplier_csv(report_data)
            filename = f"purchases_by_supplier_{start_date}_{end_date}.csv"
            return create_csv_response(
                data=csv_data,
                filename=filename,
                headers=CSV_HEADERS["purchases_by_supplier"]
            )
        
        # Add pagination metadata
        report_data["pagination"] = {
            "limit": limit,
            "offset": offset,
            "total": report_data["total_suppliers"],
            "has_more": (offset + limit) < report_data["total_suppliers"]
        }
        
        return PurchasesBySupplierResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/by-category", response_model=None)
async def get_purchases_by_category(
    start_date: date = Query(..., description="Start date for the report period"),
    end_date: date = Query(..., description="End date for the report period"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """
    Generate purchases by category report.
    
    Returns product categories ranked by total purchase amount.
    Useful for analyzing purchase patterns by product type.
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
        # Create service instance
        service = PurchaseReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        # Validate PDV ownership if specified
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(
                status_code=404,
                detail="PDV not found or doesn't belong to your company"
            )
        
        # Generate report
        report_data = service.get_purchases_by_category(
            start_date=start_date,
            end_date=end_date,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        # Export as CSV if requested
        if export == "csv":
            csv_data = prepare_purchases_by_category_csv(report_data)
            filename = f"purchases_by_category_{start_date}_{end_date}.csv"
            return create_csv_response(
                data=csv_data,
                filename=filename,
                headers=CSV_HEADERS["purchases_by_category"]
            )
        
        # Add pagination metadata
        report_data["pagination"] = {
            "limit": limit,
            "offset": offset,
            "total": report_data["total_categories"],
            "has_more": (offset + limit) < report_data["total_categories"]
        }
        
        return PurchasesByCategoryResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")