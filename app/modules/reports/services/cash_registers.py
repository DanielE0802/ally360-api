"""
Cash Register Reports Service

Handles all cash register and POS-related reports including
summary reports and detailed movement reports.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, case

from .base import BaseReportService
from app.modules.pos.models import CashRegister, CashMovement, CashRegisterStatus, MovementType
from app.modules.invoices.models import Invoice


class CashRegisterReportService(BaseReportService):
    """Service for generating cash register reports"""
    
    def get_cash_register_summary(
        self,
        start_date: date,
        end_date: date,
        cash_register_id: Optional[UUID] = None,
        status: Optional[str] = None,
        pdv_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Generate cash register summary report.
        
        Returns summary of cash register operations including balances and movements.
        """
        # Base query for cash registers with aggregated movement data
        query = self.db.query(
            CashRegister.id.label('cash_register_id'),
            CashRegister.name.label('cash_register_name'),
            CashRegister.pdv_id,
            CashRegister.opened_by,
            CashRegister.closed_by,
            CashRegister.opened_at,
            CashRegister.closed_at,
            CashRegister.opening_balance,
            CashRegister.closing_balance,
            # Subquery for movement aggregations
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == MovementType.SALE, CashMovement.amount),
                        else_=0
                    )
                ), 0
            ).label('total_sales'),
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == MovementType.DEPOSIT, CashMovement.amount),
                        else_=0
                    )
                ), 0
            ).label('total_deposits'),
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == MovementType.WITHDRAWAL, CashMovement.amount),
                        else_=0
                    )
                ), 0
            ).label('total_withdrawals'),
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == MovementType.EXPENSE, CashMovement.amount),
                        else_=0
                    )
                ), 0
            ).label('total_expenses'),
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == MovementType.ADJUSTMENT, CashMovement.amount),
                        else_=0
                    )
                ), 0
            ).label('total_adjustments'),
            func.count(CashMovement.id).label('movements_count')
        ).outerjoin(
            CashMovement, CashRegister.id == CashMovement.cash_register_id
        ).filter(
            CashRegister.tenant_id == self.tenant_id
        )
        
        # Apply date filter on opened_at
        query = self._apply_date_filter(query, CashRegister.opened_at, start_date, end_date)
        
        # Apply optional filters
        if cash_register_id:
            query = query.filter(CashRegister.id == cash_register_id)
        
        if status:
            query = query.filter(CashRegister.status == status)
        
        if pdv_id:
            query = query.filter(CashRegister.pdv_id == pdv_id)
        
        # Group by cash register
        query = query.group_by(
            CashRegister.id,
            CashRegister.name,
            CashRegister.pdv_id,
            CashRegister.opened_by,
            CashRegister.closed_by,
            CashRegister.opened_at,
            CashRegister.closed_at,
            CashRegister.opening_balance,
            CashRegister.closing_balance
        ).order_by(desc(CashRegister.opened_at))
        
        # Get total count for pagination
        total_registers = query.count()
        
        # Apply pagination
        registers = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries with calculated fields
        registers_list = []
        total_opening_balance = Decimal('0')
        total_closing_balance = Decimal('0')
        total_calculated_balance = Decimal('0')
        total_difference = Decimal('0')
        
        for register in registers:
            # Calculate balance
            calculated_balance = (
                register.opening_balance +
                register.total_sales +
                register.total_deposits -
                register.total_withdrawals -
                register.total_expenses +
                register.total_adjustments
            )
            
            # Calculate difference (only if closed)
            difference = None
            if register.closing_balance is not None:
                difference = register.closing_balance - calculated_balance
                total_difference += difference
            
            # Get user names
            opened_by_name = self._get_user_name(register.opened_by)
            closed_by_name = self._get_user_name(register.closed_by) if register.closed_by else None
            
            # Get PDV name
            pdv_name = self._get_pdv_name(register.pdv_id)
            
            total_opening_balance += register.opening_balance
            if register.closing_balance:
                total_closing_balance += register.closing_balance
            total_calculated_balance += calculated_balance
            
            registers_list.append({
                "cash_register_id": register.cash_register_id,
                "cash_register_name": register.cash_register_name,
                "pdv_name": pdv_name,
                "opened_by_name": opened_by_name,
                "closed_by_name": closed_by_name,
                "opened_at": register.opened_at,
                "closed_at": register.closed_at,
                "opening_balance": register.opening_balance,
                "closing_balance": register.closing_balance,
                "calculated_balance": calculated_balance,
                "difference": difference,
                "total_sales": register.total_sales,
                "total_deposits": register.total_deposits,
                "total_withdrawals": register.total_withdrawals,
                "total_expenses": register.total_expenses,
                "total_adjustments": register.total_adjustments,
                "movements_count": register.movements_count
            })
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "registers": registers_list,
            "total_registers": total_registers,
            "total_opening_balance": total_opening_balance,
            "total_closing_balance": total_closing_balance,
            "total_calculated_balance": total_calculated_balance,
            "total_difference": total_difference
        }
    
    def get_cash_movements_detail(
        self,
        cash_register_id: UUID,
        limit: int = 500,
        offset: int = 0
    ) -> Dict:
        """
        Generate detailed cash movements report for a specific cash register.
        
        Returns all movements with invoice references and user information.
        """
        # Validate cash register belongs to tenant
        cash_register = self._get_base_cash_register_query().filter(
            CashRegister.id == cash_register_id
        ).first()
        
        if not cash_register:
            raise ValueError(f"Cash register {cash_register_id} not found")
        
        # Query movements with invoice information
        query = self.db.query(
            CashMovement.id.label('movement_id'),
            CashMovement.created_at.label('movement_date'),
            CashMovement.type.label('movement_type'),
            CashMovement.amount,
            CashMovement.reference,
            CashMovement.notes,
            CashMovement.created_by,
            Invoice.number.label('invoice_number')
        ).outerjoin(
            Invoice, CashMovement.invoice_id == Invoice.id
        ).filter(
            CashMovement.cash_register_id == cash_register_id,
            CashMovement.tenant_id == self.tenant_id
        ).order_by(desc(CashMovement.created_at))
        
        # Get total count for pagination
        total_movements = query.count()
        
        # Apply pagination
        movements = query.offset(offset).limit(limit).all()
        
        # Convert to list of dictionaries with signed amounts
        movements_list = []
        summary_by_type = {}
        
        for movement in movements:
            # Calculate signed amount based on movement type
            signed_amount = self._calculate_signed_amount(movement.movement_type, movement.amount)
            
            # Get user name
            created_by_name = self._get_user_name(movement.created_by)
            
            # Update summary by type
            if movement.movement_type not in summary_by_type:
                summary_by_type[movement.movement_type] = Decimal('0')
            summary_by_type[movement.movement_type] += movement.amount
            
            movements_list.append({
                "movement_id": movement.movement_id,
                "movement_date": movement.movement_date,
                "movement_type": movement.movement_type,
                "amount": movement.amount,
                "signed_amount": signed_amount,
                "reference": movement.reference,
                "notes": movement.notes,
                "invoice_number": movement.invoice_number,
                "created_by_name": created_by_name
            })
        
        return {
            "cash_register_id": cash_register_id,
            "cash_register_name": cash_register.name,
            "movements": movements_list,
            "total_movements": total_movements,
            "summary_by_type": summary_by_type
        }
    
    def _calculate_signed_amount(self, movement_type: str, amount: Decimal) -> Decimal:
        """Calculate signed amount based on movement type"""
        if movement_type in [MovementType.SALE, MovementType.DEPOSIT]:
            return amount  # Positive (money in)
        elif movement_type in [MovementType.WITHDRAWAL, MovementType.EXPENSE]:
            return -amount  # Negative (money out)
        else:  # ADJUSTMENT
            return amount  # Could be positive or negative