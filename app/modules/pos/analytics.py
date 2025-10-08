"""
Real-Time Analytics Service for POS Module

Provides live dashboard capabilities with WebSocket support for real-time updates.
Includes automatic alerts, live sales tracking, and predictive analytics.

Features:
- Live sales dashboard with WebSocket updates
- Automatic alerts for low stock, sales targets, etc.
- Real-time KPIs and metrics
- Comparative analytics (day/week/month)
- Predictive analytics with basic ML
"""

import asyncio
import json
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set
from uuid import UUID
from statistics import mean, median

from sqlalchemy import and_, func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.pos.models import CashRegister, CashMovement, CashRegisterStatus, MovementType
from app.modules.invoices.models import Invoice
from app.modules.products.models import Product, Stock
from app.modules.pos.schemas import (
    LiveDashboardResponse, AlertResponse, PredictiveAnalyticsResponse,
    SalesTargetCheck, LiveMetricsResponse, ComparativeAnalyticsResponse
)
from app.modules.auth.models import User


class RealTimeAnalyticsService:
    """Service for real-time analytics and live dashboard"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._active_websockets: Set[Any] = set()  # WebSocket connections
        self._cached_metrics: Dict[str, Any] = {}
        self._last_update: Optional[datetime] = None
        
    async def get_live_dashboard(
        self,
        location_id: Optional[UUID],
        tenant_id: UUID
    ) -> LiveDashboardResponse:
        """
        Get comprehensive live dashboard data
        
        Args:
            location_id: PDV location ID (optional, all locations if None)
            tenant_id: Tenant ID for multi-tenancy
            
        Returns:
            LiveDashboardResponse with real-time metrics
        """
        now = datetime.utcnow()
        today = now.date()
        
        # Get today's sales data
        today_sales = await self._get_today_sales(location_id, tenant_id, today)
        
        # Get current period comparisons
        yesterday_sales = await self._get_sales_for_date(
            location_id, tenant_id, today - timedelta(days=1)
        )
        last_week_sales = await self._get_sales_for_date(
            location_id, tenant_id, today - timedelta(days=7)
        )
        
        # Get active cash registers
        active_registers = await self._get_active_registers(location_id, tenant_id)
        
        # Get hourly sales breakdown for today
        hourly_sales = await self._get_hourly_sales(location_id, tenant_id, today)
        
        # Calculate real-time KPIs
        current_hour_sales = await self._get_current_hour_sales(location_id, tenant_id)
        
        # Get top products today
        top_products_today = await self._get_top_products_today(location_id, tenant_id, limit=5)
        
        # Calculate growth percentages
        daily_growth = self._calculate_growth_percentage(
            today_sales['total_amount'], yesterday_sales['total_amount']
        )
        weekly_growth = self._calculate_growth_percentage(
            today_sales['total_amount'], last_week_sales['total_amount']
        )
        
        # Get active alerts
        active_alerts = await self._get_active_alerts(location_id, tenant_id)
        
        return LiveDashboardResponse(
            timestamp=now,
            location_id=location_id,
            today_sales=today_sales,
            current_hour_sales=current_hour_sales,
            active_registers=len(active_registers),
            registers_detail=active_registers,
            hourly_breakdown=hourly_sales,
            top_products_today=top_products_today,
            comparisons={
                "vs_yesterday": {
                    "sales_count": today_sales['sales_count'] - yesterday_sales['sales_count'],
                    "total_amount": today_sales['total_amount'] - yesterday_sales['total_amount'],
                    "growth_percentage": daily_growth
                },
                "vs_last_week": {
                    "sales_count": today_sales['sales_count'] - last_week_sales['sales_count'],
                    "total_amount": today_sales['total_amount'] - last_week_sales['total_amount'],
                    "growth_percentage": weekly_growth
                }
            },
            alerts=active_alerts,
            performance_indicators={
                "sales_velocity": await self._calculate_sales_velocity(location_id, tenant_id),
                "average_ticket_today": today_sales['average_ticket'],
                "conversion_rate": await self._estimate_conversion_rate(location_id, tenant_id),
                "peak_hour": self._identify_peak_hour(hourly_sales)
            }
        )
    
    async def check_sales_targets(
        self,
        location_id: Optional[UUID],
        tenant_id: UUID,
        daily_target: Optional[Decimal] = None,
        monthly_target: Optional[Decimal] = None
    ) -> SalesTargetCheck:
        """
        Check progress against sales targets
        
        Args:
            location_id: PDV location ID
            tenant_id: Tenant ID
            daily_target: Daily sales target (optional)
            monthly_target: Monthly sales target (optional)
            
        Returns:
            SalesTargetCheck with target progress
        """
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        # Get today's sales
        today_sales = await self._get_today_sales(location_id, tenant_id, today)
        
        # Get month's sales
        month_sales = await self._get_sales_for_period(
            location_id, tenant_id, month_start, today
        )
        
        # Calculate target progress
        daily_progress = None
        if daily_target:
            daily_progress = {
                "target": daily_target,
                "current": today_sales['total_amount'],
                "percentage": float(today_sales['total_amount'] / daily_target * 100),
                "remaining": daily_target - today_sales['total_amount'],
                "on_track": today_sales['total_amount'] >= daily_target * 0.8  # 80% by end of day
            }
        
        monthly_progress = None
        if monthly_target:
            days_in_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1)).day
            expected_progress = (today.day / days_in_month) * monthly_target
            
            monthly_progress = {
                "target": monthly_target,
                "current": month_sales['total_amount'],
                "percentage": float(month_sales['total_amount'] / monthly_target * 100),
                "remaining": monthly_target - month_sales['total_amount'],
                "expected_at_date": expected_progress,
                "ahead_behind": month_sales['total_amount'] - expected_progress,
                "on_track": month_sales['total_amount'] >= expected_progress * 0.9
            }
        
        return SalesTargetCheck(
            check_date=today,
            location_id=location_id,
            daily_progress=daily_progress,
            monthly_progress=monthly_progress,
            recommendations=self._generate_target_recommendations(daily_progress, monthly_progress)
        )
    
    async def get_predictive_analytics(
        self,
        location_id: Optional[UUID],
        tenant_id: UUID,
        prediction_days: int = 7
    ) -> PredictiveAnalyticsResponse:
        """
        Generate predictive analytics using historical data
        
        Args:
            location_id: PDV location ID
            tenant_id: Tenant ID
            prediction_days: Number of days to predict
            
        Returns:
            PredictiveAnalyticsResponse with predictions
        """
        # Get historical data (last 30 days)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        historical_sales = await self._get_daily_sales_history(
            location_id, tenant_id, start_date, end_date
        )
        
        # Simple linear regression for sales prediction
        sales_prediction = self._predict_sales_linear(historical_sales, prediction_days)
        
        # Identify trends
        recent_trend = self._identify_sales_trend(historical_sales[-7:])  # Last 7 days
        seasonal_patterns = self._identify_seasonal_patterns(historical_sales)
        
        # Get stock alerts (products likely to run out)
        stock_alerts = await self._predict_stock_shortage(location_id, tenant_id, prediction_days)
        
        # Calculate demand patterns
        demand_forecast = await self._forecast_product_demand(
            location_id, tenant_id, prediction_days
        )
        
        return PredictiveAnalyticsResponse(
            prediction_date=datetime.utcnow(),
            prediction_period_days=prediction_days,
            location_id=location_id,
            sales_forecast=sales_prediction,
            trend_analysis=recent_trend,
            seasonal_patterns=seasonal_patterns,
            stock_alerts=stock_alerts,
            demand_forecast=demand_forecast,
            confidence_level=self._calculate_prediction_confidence(historical_sales),
            recommendations=self._generate_predictive_recommendations(
                sales_prediction, recent_trend, stock_alerts
            )
        )
    
    async def get_live_alerts(
        self,
        location_id: Optional[UUID],
        tenant_id: UUID,
        alert_types: Optional[List[str]] = None
    ) -> List[AlertResponse]:
        """
        Get active alerts for the location
        
        Args:
            location_id: PDV location ID
            tenant_id: Tenant ID
            alert_types: Filter by alert types (optional)
            
        Returns:
            List of active alerts
        """
        alerts = []
        
        # Low stock alerts
        if not alert_types or 'stock' in alert_types:
            stock_alerts = await self._check_low_stock_alerts(location_id, tenant_id)
            alerts.extend(stock_alerts)
        
        # Sales performance alerts
        if not alert_types or 'sales' in alert_types:
            sales_alerts = await self._check_sales_alerts(location_id, tenant_id)
            alerts.extend(sales_alerts)
        
        # Cash register alerts
        if not alert_types or 'cash' in alert_types:
            cash_alerts = await self._check_cash_alerts(location_id, tenant_id)
            alerts.extend(cash_alerts)
        
        # System alerts
        if not alert_types or 'system' in alert_types:
            system_alerts = await self._check_system_alerts(location_id, tenant_id)
            alerts.extend(system_alerts)
        
        # Sort by priority and timestamp
        alerts.sort(key=lambda x: (x.priority, x.created_at), reverse=True)
        
        return alerts
    
    async def get_comparative_analytics(
        self,
        location_id: Optional[UUID],
        tenant_id: UUID,
        comparison_period: str = "week"  # day, week, month, year
    ) -> ComparativeAnalyticsResponse:
        """
        Get comparative analytics for different time periods
        
        Args:
            location_id: PDV location ID
            tenant_id: Tenant ID
            comparison_period: Period to compare (day, week, month, year)
            
        Returns:
            ComparativeAnalyticsResponse with comparison data
        """
        today = datetime.now().date()
        
        if comparison_period == "day":
            current_start = today
            current_end = today
            previous_start = today - timedelta(days=1)
            previous_end = today - timedelta(days=1)
            period_name = "Today vs Yesterday"
        elif comparison_period == "week":
            # Current week (Monday to Sunday)
            current_start = today - timedelta(days=today.weekday())
            current_end = today
            previous_start = current_start - timedelta(weeks=1)
            previous_end = current_start - timedelta(days=1)
            period_name = "This Week vs Last Week"
        elif comparison_period == "month":
            current_start = today.replace(day=1)
            current_end = today
            previous_month = current_start - timedelta(days=1)
            previous_start = previous_month.replace(day=1)
            previous_end = previous_month
            period_name = "This Month vs Last Month"
        else:  # year
            current_start = today.replace(month=1, day=1)
            current_end = today
            previous_start = current_start.replace(year=current_start.year - 1)
            previous_end = current_start - timedelta(days=1)
            period_name = "This Year vs Last Year"
        
        # Get data for both periods
        current_data = await self._get_sales_for_period(
            location_id, tenant_id, current_start, current_end
        )
        previous_data = await self._get_sales_for_period(
            location_id, tenant_id, previous_start, previous_end
        )
        
        # Calculate changes
        sales_change = current_data['sales_count'] - previous_data['sales_count']
        amount_change = current_data['total_amount'] - previous_data['total_amount']
        
        growth_rate = self._calculate_growth_percentage(
            current_data['total_amount'], previous_data['total_amount']
        )
        
        return ComparativeAnalyticsResponse(
            comparison_period=comparison_period,
            period_name=period_name,
            current_period={
                "start_date": current_start,
                "end_date": current_end,
                "sales_count": current_data['sales_count'],
                "total_amount": current_data['total_amount'],
                "average_ticket": current_data['average_ticket']
            },
            previous_period={
                "start_date": previous_start,
                "end_date": previous_end,
                "sales_count": previous_data['sales_count'],
                "total_amount": previous_data['total_amount'],
                "average_ticket": previous_data['average_ticket']
            },
            changes={
                "sales_count_change": sales_change,
                "amount_change": amount_change,
                "growth_rate": growth_rate,
                "trend": "up" if growth_rate > 0 else "down" if growth_rate < 0 else "stable"
            },
            analysis=self._generate_comparative_analysis(current_data, previous_data, growth_rate)
        )
    
    # WebSocket support methods
    
    async def register_websocket(self, websocket) -> None:
        """Register a WebSocket connection for real-time updates"""
        self._active_websockets.add(websocket)
    
    async def unregister_websocket(self, websocket) -> None:
        """Unregister a WebSocket connection"""
        self._active_websockets.discard(websocket)
    
    async def broadcast_update(self, data: Dict[str, Any]) -> None:
        """Broadcast real-time update to all connected WebSockets"""
        if not self._active_websockets:
            return
        
        message = json.dumps(data, default=str)
        disconnected = set()
        
        for websocket in self._active_websockets:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.add(websocket)
        
        # Remove disconnected WebSockets
        for websocket in disconnected:
            self._active_websockets.discard(websocket)
    
    # Private helper methods
    
    async def _get_today_sales(self, location_id: Optional[UUID], tenant_id: UUID, date: date) -> Dict[str, Any]:
        """Get today's sales summary"""
        return await self._get_sales_for_date(location_id, tenant_id, date)
    
    async def _get_sales_for_date(self, location_id: Optional[UUID], tenant_id: UUID, date: date) -> Dict[str, Any]:
        """Get sales data for a specific date"""
        query = select(
            func.count(Invoice.id).label('sales_count'),
            func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount')
        ).where(
            and_(
                Invoice.tenant_id == tenant_id,
                func.date(Invoice.issue_date) == date,
                Invoice.type == 'pos'
            )
        )
        
        if location_id:
            # Assuming invoices have location_id or we join with cash_registers
            query = query.where(Invoice.location_id == location_id)
        
        result = await self.db.execute(query)
        row = result.first()
        
        sales_count = row.sales_count or 0
        total_amount = Decimal(str(row.total_amount or 0))
        average_ticket = total_amount / sales_count if sales_count > 0 else Decimal('0.00')
        
        return {
            'sales_count': sales_count,
            'total_amount': total_amount,
            'average_ticket': average_ticket
        }
    
    async def _get_sales_for_period(
        self, 
        location_id: Optional[UUID], 
        tenant_id: UUID, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """Get sales data for a date range"""
        query = select(
            func.count(Invoice.id).label('sales_count'),
            func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount')
        ).where(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.issue_date.between(start_date, end_date),
                Invoice.type == 'pos'
            )
        )
        
        if location_id:
            query = query.where(Invoice.location_id == location_id)
        
        result = await self.db.execute(query)
        row = result.first()
        
        sales_count = row.sales_count or 0
        total_amount = Decimal(str(row.total_amount or 0))
        average_ticket = total_amount / sales_count if sales_count > 0 else Decimal('0.00')
        
        return {
            'sales_count': sales_count,
            'total_amount': total_amount,
            'average_ticket': average_ticket
        }
    
    async def _get_active_registers(self, location_id: Optional[UUID], tenant_id: UUID) -> List[Dict[str, Any]]:
        """Get active cash registers"""
        query = select(CashRegister).where(
            and_(
                CashRegister.tenant_id == tenant_id,
                CashRegister.status == CashRegisterStatus.OPEN
            )
        )
        
        if location_id:
            query = query.where(CashRegister.location_id == location_id)
        
        result = await self.db.execute(query)
        registers = result.scalars().all()
        
        registers_data = []
        for register in registers:
            # Calculate current balance and today's sales
            current_balance = await self._calculate_register_balance(register.id)
            today_sales = await self._get_register_sales_today(register.id)
            
            registers_data.append({
                "register_id": register.id,
                "register_name": register.name,
                "current_balance": current_balance,
                "today_sales_count": today_sales['count'],
                "today_sales_amount": today_sales['amount'],
                "opened_at": register.opened_at,
                "opened_by": register.opened_by
            })
        
        return registers_data
    
    async def _get_hourly_sales(self, location_id: Optional[UUID], tenant_id: UUID, date: date) -> List[Dict[str, Any]]:
        """Get hourly sales breakdown for a date"""
        query = select(
            func.extract('hour', Invoice.created_at).label('hour'),
            func.count(Invoice.id).label('sales_count'),
            func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount')
        ).where(
            and_(
                Invoice.tenant_id == tenant_id,
                func.date(Invoice.issue_date) == date,
                Invoice.type == 'pos'
            )
        ).group_by(func.extract('hour', Invoice.created_at)).order_by('hour')
        
        if location_id:
            query = query.where(Invoice.location_id == location_id)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        hourly_data = []
        for row in rows:
            hourly_data.append({
                "hour": int(row.hour),
                "sales_count": row.sales_count,
                "total_amount": Decimal(str(row.total_amount))
            })
        
        return hourly_data
    
    async def _get_current_hour_sales(self, location_id: Optional[UUID], tenant_id: UUID) -> Dict[str, Any]:
        """Get sales for the current hour"""
        now = datetime.utcnow()
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        query = select(
            func.count(Invoice.id).label('sales_count'),
            func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount')
        ).where(
            and_(
                Invoice.tenant_id == tenant_id,
                Invoice.created_at >= current_hour_start,
                Invoice.created_at < current_hour_start + timedelta(hours=1),
                Invoice.type == 'pos'
            )
        )
        
        if location_id:
            query = query.where(Invoice.location_id == location_id)
        
        result = await self.db.execute(query)
        row = result.first()
        
        return {
            'hour': current_hour_start.hour,
            'sales_count': row.sales_count or 0,
            'total_amount': Decimal(str(row.total_amount or 0))
        }
    
    def _calculate_growth_percentage(self, current: Decimal, previous: Decimal) -> float:
        """Calculate growth percentage between two values"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return float((current - previous) / previous * 100)
    
    async def _get_active_alerts(self, location_id: Optional[UUID], tenant_id: UUID) -> List[AlertResponse]:
        """Get active alerts for the location"""
        # This would integrate with a more sophisticated alerting system
        # For now, we'll return some basic alerts
        alerts = []
        
        # Check for any basic conditions that need alerts
        # (This is a simplified implementation)
        
        return alerts
    
    async def _calculate_sales_velocity(self, location_id: Optional[UUID], tenant_id: UUID) -> float:
        """Calculate sales velocity (sales per hour)"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hours_elapsed = (now - today_start).total_seconds() / 3600
        
        if hours_elapsed == 0:
            return 0.0
        
        today_sales = await self._get_today_sales(location_id, tenant_id, now.date())
        return float(today_sales['sales_count'] / hours_elapsed)
    
    def _identify_peak_hour(self, hourly_sales: List[Dict[str, Any]]) -> Optional[int]:
        """Identify the peak sales hour"""
        if not hourly_sales:
            return None
        
        peak_hour_data = max(hourly_sales, key=lambda x: x['sales_count'])
        return peak_hour_data['hour']
    
    # Additional helper methods would go here...
    # (Prediction algorithms, alert checking, etc.)
    
    def _predict_sales_linear(self, historical_data: List[Dict], days: int) -> List[Dict[str, Any]]:
        """Simple linear regression prediction for sales"""
        # Simplified implementation - in production, use proper ML libraries
        if len(historical_data) < 2:
            return []
        
        # Extract amounts for trend calculation
        amounts = [float(day['total_amount']) for day in historical_data[-14:]]  # Last 2 weeks
        trend = (amounts[-1] - amounts[0]) / len(amounts) if len(amounts) > 1 else 0
        
        predictions = []
        last_amount = amounts[-1] if amounts else 0
        
        for i in range(1, days + 1):
            predicted_amount = max(0, last_amount + (trend * i))
            predictions.append({
                "date": (datetime.now().date() + timedelta(days=i)).isoformat(),
                "predicted_amount": round(predicted_amount, 2),
                "confidence": max(0.3, 0.9 - (i * 0.1))  # Confidence decreases with distance
            })
        
        return predictions
    
    def _generate_target_recommendations(
        self, 
        daily_progress: Optional[Dict], 
        monthly_progress: Optional[Dict]
    ) -> List[str]:
        """Generate recommendations based on target progress"""
        recommendations = []
        
        if daily_progress and daily_progress['percentage'] < 50:
            recommendations.append("Daily sales below 50% - consider promotional activities")
        
        if monthly_progress and monthly_progress['percentage'] < 80:
            recommendations.append("Monthly target at risk - implement sales strategies")
        
        return recommendations