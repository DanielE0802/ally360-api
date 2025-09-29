"""
Inventory Reports Router

FastAPI router for all inventory-related report endpoints.
Includes stock, kardex, and low-stock reports.
"""

from datetime import date
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from ..services.inventory import InventoryReportService
from ..schemas import (
    InventoryStockFilter,
    InventoryStockResponse,
    KardexFilter,
    KardexResponse,
    LowStockResponse
)
from ..utils import (
    create_csv_response,
    prepare_inventory_stock_csv,
    prepare_kardex_csv,
    CSV_HEADERS
)


router = APIRouter(prefix="/reports/inventory", tags=["Reports"])


@router.get("/stock", response_model=None)
async def get_inventory_stock(
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    category_id: Optional[UUID] = Query(None, description="Filter by product category"),
    brand_id: Optional[UUID] = Query(None, description="Filter by product brand"),
    low_stock_only: bool = Query(False, description="Show only products with low stock"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate current inventory stock report."""
    try:
        service = InventoryReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_inventory_stock(
            pdv_id=pdv_id,
            category_id=category_id,
            brand_id=brand_id,
            low_stock_only=low_stock_only,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_inventory_stock_csv(report_data)
            filename = f"inventory_stock_{report_data['as_of_date'].strftime('%Y%m%d')}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["inventory_stock"])
        
        return InventoryStockResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")


@router.get("/kardex", response_model=None)
async def get_kardex(
    product_id: UUID = Query(..., description="Product ID for kardex"),
    pdv_id: Optional[UUID] = Query(None, description="Optional PDV filter"),
    start_date: Optional[date] = Query(None, description="Start date for movements"),
    end_date: Optional[date] = Query(None, description="End date for movements"),
    limit: int = Query(1000, ge=1, le=5000, description="Number of movements to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate kardex report for a specific product."""
    try:
        service = InventoryReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_kardex(
            product_id=product_id,
            pdv_id=pdv_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_kardex_csv(report_data)
            filename = f"kardex_{product_id}_{start_date or 'all'}_{end_date or 'all'}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["kardex"])
        
        return KardexResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")


@router.get("/low-stock", response_model=None)
async def get_low_stock_items(
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate low stock alert report."""
    try:
        service = InventoryReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_low_stock_items(
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_inventory_stock_csv(report_data)
            filename = f"low_stock_{report_data['as_of_date'].strftime('%Y%m%d')}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["inventory_stock"])
        
        return LowStockResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")