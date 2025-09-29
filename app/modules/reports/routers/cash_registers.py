"""
Cash Register Reports Router

FastAPI router for all cash register and POS-related report endpoints.
"""

from datetime import date
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from ..services.cash_registers import CashRegisterReportService
from ..schemas import (
    CashRegisterSummaryFilter,
    CashRegisterSummaryResponse,
    CashMovementsResponse
)
from ..utils import (
    create_csv_response,
    prepare_cash_register_summary_csv,
    prepare_cash_movements_csv,
    CSV_HEADERS
)


router = APIRouter(prefix="/reports/cash-registers", tags=["Reports"])


@router.get("/summary", response_model=None)
async def get_cash_register_summary(
    start_date: date = Query(..., description="Start date for the report period"),
    end_date: date = Query(..., description="End date for the report period"),
    cash_register_id: Optional[UUID] = Query(None, description="Filter by specific cash register"),
    status: Optional[str] = Query(None, pattern="^(open|closed)$", description="Filter by status"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate cash register summary report."""
    try:
        if end_date < start_date:
            raise HTTPException(422, "end_date must be greater than or equal to start_date")
        
        service = CashRegisterReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_cash_register_summary(
            start_date=start_date,
            end_date=end_date,
            cash_register_id=cash_register_id,
            status=status,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_cash_register_summary_csv(report_data)
            filename = f"cash_register_summary_{start_date}_{end_date}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["cash_register_summary"])
        
        return CashRegisterSummaryResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")


@router.get("/{cash_register_id}/movements", response_model=None)
async def get_cash_movements_detail(
    cash_register_id: UUID,
    limit: int = Query(500, ge=1, le=2000, description="Number of movements to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate detailed cash movements report for a specific cash register."""
    try:
        service = CashRegisterReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        report_data = service.get_cash_movements_detail(
            cash_register_id=cash_register_id,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_cash_movements_csv(report_data)
            filename = f"cash_movements_{cash_register_id}_{offset}-{offset+limit}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["cash_movements"])
        
        return CashMovementsResponse(**report_data)
        
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")