"""
Financial Reports Router

FastAPI router for all financial report endpoints.
"""

from datetime import date
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.modules.auth.dependencies import AuthDependencies
from app.modules.auth.schemas import AuthContext
from ..services.financial import FinancialReportService
from ..schemas import (
    IncomeVsExpensesFilter,
    IncomeVsExpensesResponse,
    AccountsReceivableResponse,
    AccountsPayableResponse
)
from ..utils import (
    create_csv_response,
    prepare_income_vs_expenses_csv,
    prepare_accounts_receivable_csv,
    prepare_accounts_payable_csv,
    CSV_HEADERS
)


router = APIRouter(prefix="/reports/financial", tags=["Reports"])


@router.get("/income-vs-expenses", response_model=None)
async def get_income_vs_expenses(
    start_date: date = Query(..., description="Start date for the report period"),
    end_date: date = Query(..., description="End date for the report period"),
    include_pending: bool = Query(False, description="Include unpaid invoices/bills"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate income vs expenses report."""
    try:
        if end_date < start_date:
            raise HTTPException(422, "end_date must be greater than or equal to start_date")
        
        service = FinancialReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_income_vs_expenses(
            start_date=start_date,
            end_date=end_date,
            include_pending=include_pending,
            pdv_id=pdv_id
        )
        
        if export == "csv":
            csv_data = prepare_income_vs_expenses_csv(report_data)
            filename = f"income_vs_expenses_{start_date}_{end_date}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["income_vs_expenses"])
        
        return IncomeVsExpensesResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")


@router.get("/accounts-receivable", response_model=None)
async def get_accounts_receivable(
    as_of_date: Optional[date] = Query(None, description="As of date (default: today)"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate accounts receivable report."""
    try:
        service = FinancialReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_accounts_receivable(
            as_of_date=as_of_date,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_accounts_receivable_csv(report_data)
            filename = f"accounts_receivable_{report_data['as_of_date']}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["accounts_receivable"])
        
        return AccountsReceivableResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")


@router.get("/accounts-payable", response_model=None)
async def get_accounts_payable(
    as_of_date: Optional[date] = Query(None, description="As of date (default: today)"),
    pdv_id: Optional[UUID] = Query(None, description="Filter by specific PDV"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records per page"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    export: Optional[str] = Query(None, pattern="^(csv)$", description="Export format: csv"),
    auth_context: AuthContext = Depends(AuthDependencies.require_any_role()),
    db: Session = Depends(get_db)
):
    """Generate accounts payable report."""
    try:
        service = FinancialReportService(
            db=db,
            tenant_id=auth_context.tenant_id,
            pdv_id=pdv_id
        )
        
        if pdv_id and not service._validate_pdv_ownership(pdv_id):
            raise HTTPException(404, "PDV not found or doesn't belong to your company")
        
        report_data = service.get_accounts_payable(
            as_of_date=as_of_date,
            pdv_id=pdv_id,
            limit=limit,
            offset=offset
        )
        
        if export == "csv":
            csv_data = prepare_accounts_payable_csv(report_data)
            filename = f"accounts_payable_{report_data['as_of_date']}.csv"
            return create_csv_response(csv_data, filename, CSV_HEADERS["accounts_payable"])
        
        return AccountsPayableResponse(**report_data)
        
    except Exception as e:
        raise HTTPException(500, f"Error generating report: {str(e)}")