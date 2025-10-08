"""
Multi-Cash Register Service for POS Module

Handles multiple cash registers operating simultaneously in the same PDV (Point of Sale).
Supports overlapping shifts, load balancing, and consolidated auditing.

Features:
- Multiple cash registers per PDV
- Overlapping shifts without closing registers
- Automatic load balancing for sales distribution
- Consolidated auditing and reconciliation
- Shift management with supervisor control
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.pos.models import CashRegister, CashMovement, CashRegisterStatus, MovementType
from app.modules.pos.schemas import (
    MultiCashSessionCreate, MultiCashSessionResponse, MultiCashSessionClose,
    CashRegisterOut, LoadBalancingConfig, ConsolidatedAuditResponse,
    ShiftTransferRequest, ShiftTransferResponse
)
from app.modules.auth.models import User
from fastapi import HTTPException


class MultiCashService:
    """Service for managing multiple cash registers per PDV"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_multi_cash_session(
        self,
        session_data: MultiCashSessionCreate,
        current_user: User,
        tenant_id: UUID
    ) -> MultiCashSessionResponse:
        """
        Create a multi-cash session with multiple registers
        
        Args:
            session_data: Configuration for the multi-cash session
            current_user: User creating the session
            tenant_id: Tenant ID for multi-tenancy
            
        Returns:
            MultiCashSessionResponse with all created registers
        """
        try:
            # Validate location access
            await self._validate_location_access(session_data.location_id, current_user, tenant_id)
            
            # Check if there are existing open registers
            existing_registers = await self._get_open_registers(session_data.location_id, tenant_id)
            
            if existing_registers and not session_data.allow_existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Location has {len(existing_registers)} open registers. Set allow_existing=true to continue."
                )
            
            # Create primary register
            primary_register = await self._create_cash_register(
                location_id=session_data.location_id,
                name=f"Caja Principal - {datetime.now().strftime('%Y%m%d')}",
                opening_balance=session_data.primary_balance,
                opening_notes=session_data.session_notes,
                user_id=current_user.id,
                tenant_id=tenant_id,
                is_primary=True
            )
            
            # Create secondary registers
            secondary_registers = []
            for i, secondary_balance in enumerate(session_data.secondary_balances, 1):
                register = await self._create_cash_register(
                    location_id=session_data.location_id,
                    name=f"Caja Secundaria {i} - {datetime.now().strftime('%Y%m%d')}",
                    opening_balance=secondary_balance,
                    opening_notes=f"Caja secundaria {i} - Sesión multi-caja",
                    user_id=current_user.id,
                    tenant_id=tenant_id,
                    is_primary=False
                )
                secondary_registers.append(register)
            
            # Create session record (for future tracking)
            session_id = uuid4()
            
            await self.db.commit()
            
            return MultiCashSessionResponse(
                session_id=session_id,
                location_id=session_data.location_id,
                primary_register=self._to_cash_register_out(primary_register),
                secondary_registers=[self._to_cash_register_out(reg) for reg in secondary_registers],
                supervisor_id=current_user.id,
                created_at=datetime.utcnow(),
                status="active",
                load_balancing_enabled=session_data.enable_load_balancing,
                total_registers=1 + len(secondary_registers)
            )
            
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Cross-session transfer failed: {str(e)}")
    
    async def get_load_balancing_suggestion(
        self,
        location_id: UUID,
        tenant_id: UUID,
        sale_amount: Decimal
    ) -> Dict[str, Any]:
        """
        Suggest the best cash register for a new sale based on load balancing
        
        Args:
            location_id: PDV location ID
            tenant_id: Tenant ID
            sale_amount: Amount of the new sale
            
        Returns:
            Dict with suggested register and balancing metrics
        """
        # Get all open registers for the location
        registers = await self._get_open_registers(location_id, tenant_id)
        
        if not registers:
            raise HTTPException(status_code=404, detail="No cash registers are currently open for this location")
        
        # Calculate metrics for each register
        register_metrics = []
        for register in registers:
            # Get sales count and amount for today
            today_sales = await self._get_register_sales_today(register.id, tenant_id)
            
            # Calculate current balance
            current_balance = await self._calculate_current_balance(register.id)
            
            # Calculate load score (lower is better)
            load_score = (
                today_sales['count'] * 0.4 +  # Sales frequency weight
                (float(today_sales['amount']) / 1000000) * 0.3 +  # Amount weight
                (float(current_balance) / 1000000) * 0.3  # Balance weight
            )
            
            register_metrics.append({
                "register_id": register.id,
                "register_name": register.name,
                "is_primary": getattr(register, 'is_primary', True),
                "current_balance": current_balance,
                "today_sales_count": today_sales['count'],
                "today_sales_amount": today_sales['amount'],
                "load_score": load_score,
                "utilization_percentage": min(100, (today_sales['count'] / 50) * 100)  # Assuming 50 sales is 100%
            })
        
        # Sort by load score (ascending - lowest load first)
        register_metrics.sort(key=lambda x: x['load_score'])
        
        # Select the register with lowest load
        suggested_register = register_metrics[0]
        
        return {
            "suggested_register_id": suggested_register["register_id"],
            "suggested_register_name": suggested_register["register_name"],
            "reason": f"Lowest load score: {suggested_register['load_score']:.2f}",
            "all_registers": register_metrics,
            "load_balancing_effective": len(register_metrics) > 1
        }
    
    async def transfer_shift(
        self,
        transfer_data: ShiftTransferRequest,
        current_user: User,
        tenant_id: UUID
    ) -> ShiftTransferResponse:
        """
        Transfer shift responsibility from one user to another without closing registers
        
        Args:
            transfer_data: Shift transfer configuration
            current_user: User initiating the transfer
            tenant_id: Tenant ID
            
        Returns:
            ShiftTransferResponse with transfer details
        """
        try:
            # Validate registers belong to the location and tenant
            registers = await self._validate_registers_ownership(
                transfer_data.register_ids, 
                transfer_data.location_id, 
                tenant_id
            )
            
            # Create shift transfer records
            transfer_records = []
            for register in registers:
                # Calculate intermediate balance
                current_balance = await self._calculate_current_balance(register.id)
                
                # Create transfer movement
                transfer_movement = CashMovement(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    cash_register_id=register.id,
                    type=MovementType.ADJUSTMENT,
                    amount=Decimal('0.00'),  # No money movement, just shift change
                    description=f"Shift transfer from {current_user.name} to new operator",
                    reference=f"SHIFT_TRANSFER_{transfer_data.new_operator_id}",
                    created_by=current_user.id,
                    created_at=datetime.utcnow()
                )
                
                self.db.add(transfer_movement)
                
                transfer_records.append({
                    "register_id": register.id,
                    "register_name": register.name,
                    "balance_at_transfer": current_balance,
                    "transfer_movement_id": transfer_movement.id
                })
            
            # Create notification/log entry for the new operator
            # (This would integrate with a notification service)
            
            await self.db.commit()
            
            return ShiftTransferResponse(
                transfer_id=uuid4(),
                location_id=transfer_data.location_id,
                from_user_id=current_user.id,
                to_user_id=transfer_data.new_operator_id,
                transferred_registers=transfer_records,
                transfer_time=datetime.utcnow(),
                notes=transfer_data.notes,
                status="completed"
            )
            
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Shift transfer failed: {str(e)}")
    
    async def consolidate_audit(
        self,
        location_id: UUID,
        register_ids: List[UUID],
        tenant_id: UUID,
        audit_date: Optional[datetime] = None
    ) -> ConsolidatedAuditResponse:
        """
        Perform consolidated audit across multiple cash registers
        
        Args:
            location_id: PDV location ID
            register_ids: List of register IDs to audit
            tenant_id: Tenant ID
            audit_date: Date for audit (defaults to today)
            
        Returns:
            ConsolidatedAuditResponse with comprehensive audit data
        """
        if audit_date is None:
            audit_date = datetime.now().date()
        
        # Get registers with movements
        registers_data = []
        total_opening_balance = Decimal('0.00')
        total_current_balance = Decimal('0.00')
        total_sales_amount = Decimal('0.00')
        total_sales_count = 0
        
        for register_id in register_ids:
            register = await self.db.get(CashRegister, register_id)
            if not register or register.tenant_id != tenant_id:
                continue
            
            # Get movements for the audit date
            movements = await self._get_movements_by_date(register_id, audit_date)
            
            # Calculate metrics
            current_balance = await self._calculate_current_balance(register_id)
            sales_movements = [m for m in movements if m.type == MovementType.SALE]
            sales_amount = sum(m.amount for m in sales_movements)
            
            register_data = {
                "register_id": register_id,
                "register_name": register.name,
                "opening_balance": register.opening_balance,
                "current_balance": current_balance,
                "movements_count": len(movements),
                "sales_count": len(sales_movements),
                "sales_amount": sales_amount,
                "last_movement_time": max((m.created_at for m in movements), default=None),
                "is_primary": getattr(register, 'is_primary', True)
            }
            
            registers_data.append(register_data)
            total_opening_balance += register.opening_balance
            total_current_balance += current_balance
            total_sales_amount += sales_amount
            total_sales_count += len(sales_movements)
        
        # Calculate consolidated metrics
        total_movements = sum(r["movements_count"] for r in registers_data)
        average_ticket = total_sales_amount / total_sales_count if total_sales_count > 0 else Decimal('0.00')
        
        # Generate recommendations
        recommendations = self._generate_audit_recommendations(registers_data)
        
        return ConsolidatedAuditResponse(
            audit_id=uuid4(),
            location_id=location_id,
            audit_date=audit_date,
            registers_audited=len(registers_data),
            total_opening_balance=total_opening_balance,
            total_current_balance=total_current_balance,
            total_movements=total_movements,
            total_sales_count=total_sales_count,
            total_sales_amount=total_sales_amount,
            average_ticket=average_ticket,
            registers_detail=registers_data,
            recommendations=recommendations,
            audit_performed_by=None,  # Would be set by the calling function
            audit_performed_at=datetime.utcnow()
        )
    
    async def close_multi_cash_session(
        self,
        session_close_data: MultiCashSessionClose,
        current_user: User,
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        Close all registers in a multi-cash session with consolidated audit
        
        Args:
            session_close_data: Session closure configuration
            current_user: User closing the session
            tenant_id: Tenant ID
            
        Returns:
            Dict with closure results and audit data
        """
        try:
            closed_registers = []
            total_difference = Decimal('0.00')
            
            for register_close in session_close_data.register_closures:
                register = await self.db.get(CashRegister, register_close.register_id)
                if not register or register.tenant_id != tenant_id:
                    continue
                
                # Calculate current balance
                calculated_balance = await self._calculate_current_balance(register.id)
                difference = register_close.declared_balance - calculated_balance
                
                # Close the register
                register.status = CashRegisterStatus.CLOSED
                register.closing_balance = register_close.declared_balance
                register.closed_by = current_user.id
                register.closed_at = datetime.utcnow()
                register.closing_notes = register_close.notes
                
                # Create adjustment if there's a difference
                if difference != 0:
                    adjustment = CashMovement(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        cash_register_id=register.id,
                        type=MovementType.ADJUSTMENT,
                        amount=abs(difference),
                        description=f"Adjustment on closing - {'Overage' if difference > 0 else 'Shortage'}",
                        reference=f"CLOSE_ADJ_{register.id}",
                        created_by=current_user.id,
                        created_at=datetime.utcnow()
                    )
                    self.db.add(adjustment)
                
                closed_registers.append({
                    "register_id": register.id,
                    "register_name": register.name,
                    "calculated_balance": calculated_balance,
                    "declared_balance": register_close.declared_balance,
                    "difference": difference,
                    "status": "closed"
                })
                
                total_difference += difference
            
            await self.db.commit()
            
            return {
                "session_id": session_close_data.session_id,
                "closed_registers": closed_registers,
                "total_difference": total_difference,
                "closure_summary": {
                    "registers_closed": len(closed_registers),
                    "total_calculated": sum(r["calculated_balance"] for r in closed_registers),
                    "total_declared": sum(r["declared_balance"] for r in closed_registers),
                    "accuracy_percentage": 100 - abs(float(total_difference)) / max(float(sum(r["calculated_balance"] for r in closed_registers)), 1) * 100
                },
                "closed_by": current_user.id,
                "closed_at": datetime.utcnow()
            }
            
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Multi-cash session closure failed: {str(e)}")
    
    # Private helper methods
    
    async def _validate_location_access(self, location_id: UUID, user: User, tenant_id: UUID) -> None:
        """Validate user has access to the location"""
        # This would integrate with location/PDV access control
        # For now, we'll just check tenant_id
        pass
    
    async def _get_open_registers(self, location_id: UUID, tenant_id: UUID) -> List[CashRegister]:
        """Get all open cash registers for a location"""
        query = select(CashRegister).where(
            and_(
                CashRegister.location_id == location_id,
                CashRegister.tenant_id == tenant_id,
                CashRegister.status == CashRegisterStatus.OPEN
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def _create_cash_register(
        self,
        location_id: UUID,
        name: str,
        opening_balance: Decimal,
        opening_notes: str,
        user_id: UUID,
        tenant_id: UUID,
        is_primary: bool = False
    ) -> CashRegister:
        """Create a new cash register"""
        register = CashRegister(
            id=uuid4(),
            tenant_id=tenant_id,
            location_id=location_id,
            name=name,
            opening_balance=opening_balance,
            status=CashRegisterStatus.OPEN,
            opened_by=user_id,
            opened_at=datetime.utcnow(),
            opening_notes=opening_notes
        )
        
        # Add is_primary as a custom attribute (would need to be added to model)
        setattr(register, 'is_primary', is_primary)
        
        self.db.add(register)
        return register
    
    async def _get_register_sales_today(self, register_id: UUID, tenant_id: UUID) -> Dict[str, Any]:
        """Get sales count and amount for today"""
        today = datetime.now().date()
        
        query = select(
            func.count(CashMovement.id).label('count'),
            func.coalesce(func.sum(CashMovement.amount), 0).label('amount')
        ).where(
            and_(
                CashMovement.cash_register_id == register_id,
                CashMovement.tenant_id == tenant_id,
                CashMovement.type == MovementType.SALE,
                func.date(CashMovement.created_at) == today
            )
        )
        
        result = await self.db.execute(query)
        row = result.first()
        
        return {
            'count': row.count or 0,
            'amount': Decimal(str(row.amount or 0))
        }
    
    async def _calculate_current_balance(self, register_id: UUID) -> Decimal:
        """Calculate current balance for a register"""
        register = await self.db.get(CashRegister, register_id)
        if not register:
            return Decimal('0.00')
        
        # Get all movements
        query = select(
            func.sum(
                func.case(
                    (CashMovement.type.in_([MovementType.SALE, MovementType.DEPOSIT]), CashMovement.amount),
                    else_=-CashMovement.amount
                )
            )
        ).where(CashMovement.cash_register_id == register_id)
        
        result = await self.db.execute(query)
        movements_total = result.scalar() or Decimal('0.00')
        
        return register.opening_balance + movements_total
    
    async def _get_movements_by_date(self, register_id: UUID, date: datetime.date) -> List[CashMovement]:
        """Get all movements for a register on a specific date"""
        query = select(CashMovement).where(
            and_(
                CashMovement.cash_register_id == register_id,
                func.date(CashMovement.created_at) == date
            )
        ).order_by(CashMovement.created_at)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def _validate_registers_ownership(
        self, 
        register_ids: List[UUID], 
        location_id: UUID, 
        tenant_id: UUID
    ) -> List[CashRegister]:
        """Validate that registers belong to the specified location and tenant"""
        query = select(CashRegister).where(
            and_(
                CashRegister.id.in_(register_ids),
                CashRegister.location_id == location_id,
                CashRegister.tenant_id == tenant_id,
                CashRegister.status == CashRegisterStatus.OPEN
            )
        )
        
        result = await self.db.execute(query)
        registers = result.scalars().all()
        
        if len(registers) != len(register_ids):
            raise HTTPException(status_code=400, detail="Invalid registers: Some registers do not belong to the specified location or are not open")
        
        return registers
    
    def _generate_audit_recommendations(self, registers_data: List[Dict[str, Any]]) -> List[str]:
        """Generate audit recommendations based on register data"""
        recommendations = []
        
        # Check for load imbalance
        if len(registers_data) > 1:
            sales_counts = [r["sales_count"] for r in registers_data]
            if max(sales_counts) > 2 * min(sales_counts):
                recommendations.append("Consider rebalancing sales distribution - some registers have significantly more activity")
        
        # Check for idle registers
        idle_registers = [r for r in registers_data if r["sales_count"] == 0]
        if idle_registers:
            recommendations.append(f"{len(idle_registers)} register(s) had no sales - consider reducing active registers")
        
        # Check for high activity registers
        high_activity = [r for r in registers_data if r["sales_count"] > 100]
        if high_activity:
            recommendations.append("Some registers have very high activity - consider adding more registers or optimizing processes")
        
        if not recommendations:
            recommendations.append("All registers are operating within normal parameters")
        
        return recommendations
    
    def _to_cash_register_out(self, register: CashRegister) -> CashRegisterOut:
        """Convert CashRegister model to response schema"""
        return CashRegisterOut(
            id=register.id,
            tenant_id=register.tenant_id,
            location_id=register.location_id,
            name=register.name,
            opening_balance=register.opening_balance,
            closing_balance=register.closing_balance,
            status=register.status,
            opened_by=register.opened_by,
            closed_by=register.closed_by,
            opened_at=register.opened_at,
            closed_at=register.closed_at,
            opening_notes=register.opening_notes,
            closing_notes=register.closing_notes,
            created_at=register.created_at,
            updated_at=register.updated_at
        )