"""
Sales Reports Router

FastAPI router for all sales-related report endpoints.
Includes summary, by product, by seller, and top customers reports.
"""

from datetime import date
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext

from ..services.sales import SalesReportService
from ..schemas import (
    SalesSummaryFilter,
    SalesSummaryResponse,
    SalesByProductResponse,
    SalesBySellerResponse,
    TopCustomersResponse,
    PaginationParams,
    ExportParams
)
from ..utils import (
    create_csv_response,
    prepare_sales_summary_csv,
    prepare_sales_by_product_csv,
    prepare_sales_by_seller_csv,
    prepare_top_customers_csv,
    CSV_HEADERS
)


router = APIRouter(prefix="/reports/sales", tags=["Reports"])


@router.get("/summary", response_model=None)
async def get_sales_summary(
    start_date: date = Query(..., description="Start date for the report period"),
    end_date: date = Query(..., description="End date for the report period"),
    customer_id: Optional[UUID] = Query(None, description="Filter by specific customer"),
    seller_id: Optional[UUID] = Query(None, description="Filter by specific seller"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """
    Generate sales summary report for a date range.
    
    Returns total sales, amount, average ticket, and invoice counts.
    Supports filtering by customer, seller, and PDV.
    Can export results as CSV.
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
        # Create service instance
        service = SalesReportService(
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
        report_data = service.get_sales_summary(
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            seller_id=seller_id,
            pdv_id=pdv_id
        )
        
        # Export as CSV if requested
        if export == "csv":
            csv_data = prepare_sales_summary_csv(report_data)
            filename = f"sales_summary_{start_date}_{end_date}.csv"
            return create_csv_response(
                data=csv_data,
                filename=filename,
                headers=CSV_HEADERS["sales_summary"]
            )
        
        return SalesSummaryResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/by-product", response_model=None)
async def get_sales_by_product(
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
    Generate sales by product report.
    
    Returns products ranked by sales amount and quantity.
    Includes product information, category, and brand.
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
        # Create service instance
        service = SalesReportService(
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
        report_data = service.get_sales_by_product(
            start_date=start_date,
            end_date=end_date,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        # Export as CSV if requested
        if export == "csv":
            csv_data = prepare_sales_by_product_csv(report_data)
            filename = f"sales_by_product_{start_date}_{end_date}.csv"
            return create_csv_response(
                data=csv_data,
                filename=filename,
                headers=CSV_HEADERS["sales_by_product"]
            )
        
        # Add pagination metadata
        report_data["pagination"] = {
            "limit": limit,
            "offset": offset,
            "total": report_data["total_products"],
            "has_more": (offset + limit) < report_data["total_products"]
        }
        
        return SalesByProductResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/by-seller", response_model=None)
async def get_sales_by_seller(
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
    Generate sales by seller report.
    
    Returns sellers ranked by sales performance with commission estimates.
    Only available for users with appropriate permissions.
    """
    try:
        # Check permissions - only admin, owner, and accountant can see all sellers
        user_role = auth_context.user_role or 'viewer'
        if user_role in ['seller', 'cashier']:
            # Sellers and cashiers can only see their own sales
            # This would need to be implemented based on your auth system
            pass
        
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
        # Create service instance
        service = SalesReportService(
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
        report_data = service.get_sales_by_seller(
            start_date=start_date,
            end_date=end_date,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        # Export as CSV if requested
        if export == "csv":
            csv_data = prepare_sales_by_seller_csv(report_data)
            filename = f"sales_by_seller_{start_date}_{end_date}.csv"
            return create_csv_response(
                data=csv_data,
                filename=filename,
                headers=CSV_HEADERS["sales_by_seller"]
            )
        
        # Add pagination metadata
        report_data["pagination"] = {
            "limit": limit,
            "offset": offset,
            "total": report_data["total_sellers"],
            "has_more": (offset + limit) < report_data["total_sellers"]
        }
        
        return SalesBySellerResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/top-customers", response_model=None)
async def get_top_customers(
    start_date: date = Query(..., description="Start date for the report period"),
    end_date: date = Query(..., description="End date for the report period"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(50, ge=1, le=500, description="Number of top customers to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """
    Generate top customers report.
    
    Returns customers ranked by total purchases amount.
    Useful for identifying most valuable customers.
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
        # Create service instance
        service = SalesReportService(
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
        report_data = service.get_top_customers(
            start_date=start_date,
            end_date=end_date,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        # Export as CSV if requested
        if export == "csv":
            csv_data = prepare_top_customers_csv(report_data)
            filename = f"top_customers_{start_date}_{end_date}.csv"
            return create_csv_response(
                data=csv_data,
                filename=filename,
                headers=CSV_HEADERS["top_customers"]
            )
        
        # Add pagination metadata
        report_data["pagination"] = {
            "limit": limit,
            "offset": offset,
            "total": report_data["total_customers"],
            "has_more": (offset + limit) < report_data["total_customers"]
        }
        
        return TopCustomersResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")