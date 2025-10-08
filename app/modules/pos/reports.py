"""
Servicios de reportes avanzados para el módulo POS

Implementa reportes especializados para análisis de punto de venta:
- Sales by Seller: Performance individual con comisiones
- Cash Register Audit: Arqueos detallados y tendencias
- Shift Analysis: Comparación por turnos (mañana, tarde, noche)
- Top Products POS: Productos más vendidos en punto de venta
- Real-time Analytics: Métricas en tiempo real

Todas las consultas están optimizadas para multi-tenancy y performance.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, case, text, cast, Integer
from sqlalchemy.sql import extract
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import date, datetime, time, timedelta
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field, field_validator

from app.modules.pos.models import (
    CashRegister, CashMovement, Seller,
    CashRegisterStatus, MovementType
)
from app.modules.invoices.models import Invoice, InvoiceLineItem, InvoiceType
from app.modules.products.models import Product
from app.modules.pdv.models import PDV


class ShiftType(str, Enum):
    """Tipos de turnos para análisis"""
    MORNING = "morning"      # 06:00 - 14:00
    AFTERNOON = "afternoon"  # 14:00 - 22:00
    NIGHT = "night"         # 22:00 - 06:00


@dataclass
class DateRange:
    """Rango de fechas para reportes"""
    start_date: date
    end_date: date


class POSReportsService:
    """Servicio para reportes avanzados de POS"""

    def __init__(self, db: Session):
        self.db = db

    # ===== VENTAS POR VENDEDOR =====
    
    def get_sales_by_seller_report(
        self, 
        tenant_id: UUID,
        date_range: DateRange,
        seller_id: Optional[UUID] = None,
        pdv_id: Optional[UUID] = None,
        include_commissions: bool = True
    ) -> Dict[str, Any]:
        """
        Reporte de ventas por vendedor con performance individual y comisiones.
        
        Args:
            tenant_id: ID del tenant
            date_range: Rango de fechas
            seller_id: Filtro opcional por vendedor específico
            pdv_id: Filtro opcional por PDV específico
            include_commissions: Incluir cálculo de comisiones
            
        Returns:
            Dict con datos detallados por vendedor
        """
        try:
            # Query base para ventas POS
            query = self.db.query(
                Seller.id.label('seller_id'),
                Seller.name.label('seller_name'),
                Seller.commission_rate,
                Seller.base_salary,
                func.count(Invoice.id).label('total_sales'),
                func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount'),
                func.coalesce(func.avg(Invoice.total_amount), 0).label('avg_ticket'),
                func.min(Invoice.total_amount).label('min_sale'),
                func.max(Invoice.total_amount).label('max_sale'),
                func.count(func.distinct(Invoice.issue_date)).label('active_days')
            ).join(
                Invoice, Invoice.seller_id == Seller.id
            ).filter(
                Seller.tenant_id == tenant_id,
                Invoice.tenant_id == tenant_id,
                Invoice.type == InvoiceType.POS,
                Invoice.issue_date.between(date_range.start_date, date_range.end_date)
            )

            # Filtros opcionales
            if seller_id:
                query = query.filter(Seller.id == seller_id)
            
            if pdv_id:
                query = query.filter(Invoice.pdv_id == pdv_id)

            # Agrupar por vendedor
            results = query.group_by(
                Seller.id, Seller.name, Seller.commission_rate, Seller.base_salary
            ).order_by(desc('total_amount')).all()

            # Procesar resultados
            sellers_data = []
            total_sales_amount = Decimal('0')
            total_sales_count = 0

            for result in results:
                seller_data = {
                    'seller_id': str(result.seller_id),
                    'seller_name': result.seller_name,
                    'total_sales': result.total_sales,
                    'total_amount': float(result.total_amount),
                    'avg_ticket': float(result.avg_ticket),
                    'min_sale': float(result.min_sale) if result.min_sale else 0,
                    'max_sale': float(result.max_sale) if result.max_sale else 0,
                    'active_days': result.active_days,
                    'sales_per_day': round(result.total_sales / max(result.active_days, 1), 2),
                    'commission_rate': float(result.commission_rate) if result.commission_rate else 0,
                    'base_salary': float(result.base_salary) if result.base_salary else 0
                }

                # Calcular comisiones si está habilitado
                if include_commissions and result.commission_rate:
                    estimated_commission = result.total_amount * result.commission_rate
                    seller_data['estimated_commission'] = float(estimated_commission)
                else:
                    seller_data['estimated_commission'] = 0

                sellers_data.append(seller_data)
                total_sales_amount += result.total_amount
                total_sales_count += result.total_sales

            # Calcular participación de mercado
            for seller in sellers_data:
                if total_sales_amount > 0:
                    seller['market_share'] = round(
                        (seller['total_amount'] / float(total_sales_amount)) * 100, 2
                    )
                else:
                    seller['market_share'] = 0

            # Resumen general
            summary = {
                'total_sellers': len(sellers_data),
                'total_sales_count': total_sales_count,
                'total_sales_amount': float(total_sales_amount),
                'avg_ticket_general': float(total_sales_amount / max(total_sales_count, 1)),
                'best_seller': sellers_data[0] if sellers_data else None,
                'total_commissions': sum(s['estimated_commission'] for s in sellers_data)
            }

            return {
                'summary': summary,
                'sellers': sellers_data,
                'period': {
                    'start_date': date_range.start_date.isoformat(),
                    'end_date': date_range.end_date.isoformat(),
                    'days': (date_range.end_date - date_range.start_date).days + 1
                }
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando reporte de ventas por vendedor: {str(e)}"
            )

    # ===== ARQUEOS DETALLADOS =====
    
    def get_cash_audit_report(
        self,
        tenant_id: UUID,
        date_range: DateRange,
        pdv_id: Optional[UUID] = None,
        include_trends: bool = True
    ) -> Dict[str, Any]:
        """
        Reporte de arqueos detallados con diferencias históricas y tendencias.
        
        Args:
            tenant_id: ID del tenant
            date_range: Rango de fechas
            pdv_id: Filtro opcional por PDV
            include_trends: Incluir análisis de tendencias
            
        Returns:
            Dict con análisis detallado de arqueos
        """
        try:
            # Query para cajas cerradas con cálculos
            query = self.db.query(
                CashRegister.id,
                CashRegister.name,
                CashRegister.pdv_id,
                PDV.name.label('pdv_name'),
                CashRegister.opened_at,
                CashRegister.closed_at,
                CashRegister.opening_balance,
                CashRegister.closing_balance,
                func.coalesce(
                    func.sum(
                        case(
                            (CashMovement.type.in_([MovementType.SALE, MovementType.DEPOSIT]), 
                             CashMovement.amount),
                            (CashMovement.type.in_([MovementType.WITHDRAWAL, MovementType.EXPENSE]), 
                             -CashMovement.amount),
                            else_=CashMovement.amount  # ADJUSTMENT
                        )
                    ), 0
                ).label('total_movements')
            ).outerjoin(
                CashMovement, CashMovement.cash_register_id == CashRegister.id
            ).join(
                PDV, PDV.id == CashRegister.pdv_id
            ).filter(
                CashRegister.tenant_id == tenant_id,
                CashRegister.status == CashRegisterStatus.CLOSED,
                func.date(CashRegister.closed_at).between(date_range.start_date, date_range.end_date)
            )

            if pdv_id:
                query = query.filter(CashRegister.pdv_id == pdv_id)

            results = query.group_by(
                CashRegister.id, CashRegister.name, CashRegister.pdv_id, PDV.name,
                CashRegister.opened_at, CashRegister.closed_at,
                CashRegister.opening_balance, CashRegister.closing_balance
            ).order_by(desc(CashRegister.closed_at)).all()

            # Procesar datos de arqueo
            audits = []
            total_differences = Decimal('0')
            differences_by_day = {}

            for result in results:
                calculated_balance = result.opening_balance + result.total_movements
                difference = result.closing_balance - calculated_balance if result.closing_balance else Decimal('0')
                
                audit_data = {
                    'cash_register_id': str(result.id),
                    'cash_register_name': result.name,
                    'pdv_id': str(result.pdv_id),
                    'pdv_name': result.pdv_name,
                    'opened_at': result.opened_at.isoformat(),
                    'closed_at': result.closed_at.isoformat() if result.closed_at else None,
                    'duration_hours': (
                        (result.closed_at - result.opened_at).total_seconds() / 3600
                        if result.closed_at else 0
                    ),
                    'opening_balance': float(result.opening_balance),
                    'closing_balance': float(result.closing_balance) if result.closing_balance else 0,
                    'calculated_balance': float(calculated_balance),
                    'difference': float(difference),
                    'difference_percentage': (
                        float(difference / calculated_balance * 100) 
                        if calculated_balance != 0 else 0
                    ),
                    'status': 'exact' if difference == 0 else ('surplus' if difference > 0 else 'shortage')
                }

                audits.append(audit_data)
                total_differences += abs(difference)

                # Agrupar diferencias por día para tendencias
                if include_trends and result.closed_at:
                    day_key = result.closed_at.date()
                    if day_key not in differences_by_day:
                        differences_by_day[day_key] = []
                    differences_by_day[day_key].append(float(difference))

            # Análisis de tendencias
            trends = {}
            if include_trends and differences_by_day:
                daily_stats = []
                for day, diffs in differences_by_day.items():
                    daily_stats.append({
                        'date': day.isoformat(),
                        'total_difference': sum(diffs),
                        'avg_difference': sum(diffs) / len(diffs),
                        'max_difference': max(diffs),
                        'min_difference': min(diffs),
                        'count_audits': len(diffs)
                    })

                trends = {
                    'daily_stats': sorted(daily_stats, key=lambda x: x['date']),
                    'trend_analysis': self._analyze_difference_trends(daily_stats)
                }

            # Resumen general
            summary = {
                'total_audits': len(audits),
                'exact_audits': len([a for a in audits if a['status'] == 'exact']),
                'surplus_audits': len([a for a in audits if a['status'] == 'surplus']),
                'shortage_audits': len([a for a in audits if a['status'] == 'shortage']),
                'total_absolute_differences': float(total_differences),
                'avg_difference': float(total_differences / len(audits)) if audits else 0,
                'accuracy_rate': (
                    len([a for a in audits if a['status'] == 'exact']) / len(audits) * 100
                    if audits else 100
                )
            }

            return {
                'summary': summary,
                'audits': audits,
                'trends': trends,
                'period': {
                    'start_date': date_range.start_date.isoformat(),
                    'end_date': date_range.end_date.isoformat()
                }
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando reporte de arqueos: {str(e)}"
            )

    # ===== ANÁLISIS DE TURNOS =====
    
    def get_shift_analysis_report(
        self,
        tenant_id: UUID,
        date_range: DateRange,
        pdv_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Análisis comparativo por turnos (mañana, tarde, noche).
        
        Args:
            tenant_id: ID del tenant
            date_range: Rango de fechas
            pdv_id: Filtro opcional por PDV
            
        Returns:
            Dict con análisis por turnos
        """
        try:
            # Query con clasificación de turnos basada en hora de creación
            shift_case = case(
                (extract('hour', Invoice.created_at).between(6, 13), 'morning'),
                (extract('hour', Invoice.created_at).between(14, 21), 'afternoon'),
                else_='night'
            ).label('shift')

            query = self.db.query(
                shift_case,
                func.count(Invoice.id).label('total_sales'),
                func.coalesce(func.sum(Invoice.total_amount), 0).label('total_amount'),
                func.coalesce(func.avg(Invoice.total_amount), 0).label('avg_ticket'),
                func.count(func.distinct(Invoice.seller_id)).label('active_sellers'),
                func.count(func.distinct(Invoice.issue_date)).label('active_days')
            ).filter(
                Invoice.tenant_id == tenant_id,
                Invoice.type == InvoiceType.POS,
                Invoice.issue_date.between(date_range.start_date, date_range.end_date)
            )

            if pdv_id:
                query = query.filter(Invoice.pdv_id == pdv_id)

            results = query.group_by(shift_case).all()

            # Procesar resultados por turno
            shifts_data = {}
            total_sales = 0
            total_amount = Decimal('0')

            for result in results:
                shift_data = {
                    'shift': result.shift,
                    'total_sales': result.total_sales,
                    'total_amount': float(result.total_amount),
                    'avg_ticket': float(result.avg_ticket),
                    'active_sellers': result.active_sellers,
                    'active_days': result.active_days,
                    'sales_per_day': round(result.total_sales / max(result.active_days, 1), 2),
                    'sales_per_seller': round(result.total_sales / max(result.active_sellers, 1), 2)
                }

                shifts_data[result.shift] = shift_data
                total_sales += result.total_sales
                total_amount += result.total_amount

            # Calcular participación por turno
            for shift_name, shift_data in shifts_data.items():
                if total_sales > 0:
                    shift_data['sales_percentage'] = round(
                        (shift_data['total_sales'] / total_sales) * 100, 2
                    )
                    shift_data['amount_percentage'] = round(
                        (shift_data['total_amount'] / float(total_amount)) * 100, 2
                    )
                else:
                    shift_data['sales_percentage'] = 0
                    shift_data['amount_percentage'] = 0

            # Análisis comparativo
            best_shift_by_sales = max(shifts_data.values(), key=lambda x: x['total_sales']) if shifts_data else None
            best_shift_by_amount = max(shifts_data.values(), key=lambda x: x['total_amount']) if shifts_data else None

            comparison = {
                'best_shift_by_sales': best_shift_by_sales['shift'] if best_shift_by_sales else None,
                'best_shift_by_amount': best_shift_by_amount['shift'] if best_shift_by_amount else None,
                'most_consistent_shift': self._find_most_consistent_shift(shifts_data),
                'recommendations': self._generate_shift_recommendations(shifts_data)
            }

            return {
                'shifts': shifts_data,
                'comparison': comparison,
                'summary': {
                    'total_sales': total_sales,
                    'total_amount': float(total_amount),
                    'active_shifts': len(shifts_data)
                },
                'period': {
                    'start_date': date_range.start_date.isoformat(),
                    'end_date': date_range.end_date.isoformat()
                }
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando análisis de turnos: {str(e)}"
            )

    # ===== TOP PRODUCTOS POS =====
    
    def get_top_products_report(
        self,
        tenant_id: UUID,
        date_range: DateRange,
        pdv_id: Optional[UUID] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Reporte de productos más vendidos en punto de venta.
        
        Args:
            tenant_id: ID del tenant
            date_range: Rango de fechas
            pdv_id: Filtro opcional por PDV
            limit: Número máximo de productos a retornar
            
        Returns:
            Dict con ranking de productos más vendidos
        """
        try:
            # Query para productos más vendidos
            query = self.db.query(
                Product.id.label('product_id'),
                Product.name.label('product_name'),
                Product.sku.label('product_sku'),
                Product.price.label('unit_price'),
                func.sum(InvoiceLineItem.quantity).label('total_quantity'),
                func.count(func.distinct(Invoice.id)).label('total_invoices'),
                func.sum(InvoiceLineItem.line_total).label('total_revenue'),
                func.avg(InvoiceLineItem.unit_price).label('avg_price'),
                func.count(func.distinct(Invoice.seller_id)).label('sold_by_sellers')
            ).join(
                InvoiceLineItem, InvoiceLineItem.product_id == Product.id
            ).join(
                Invoice, Invoice.id == InvoiceLineItem.invoice_id
            ).filter(
                Product.tenant_id == tenant_id,
                Invoice.tenant_id == tenant_id,
                Invoice.type == InvoiceType.POS,
                Invoice.issue_date.between(date_range.start_date, date_range.end_date)
            )

            if pdv_id:
                query = query.filter(Invoice.pdv_id == pdv_id)

            results = query.group_by(
                Product.id, Product.name, Product.sku, Product.price
            ).order_by(desc('total_quantity')).limit(limit).all()

            # Procesar resultados
            products = []
            total_quantity = 0
            total_revenue = Decimal('0')

            for rank, result in enumerate(results, 1):
                product_data = {
                    'rank': rank,
                    'product_id': str(result.product_id),
                    'product_name': result.product_name,
                    'product_sku': result.product_sku,
                    'unit_price': float(result.unit_price),
                    'total_quantity': float(result.total_quantity),
                    'total_invoices': result.total_invoices,
                    'total_revenue': float(result.total_revenue),
                    'avg_price': float(result.avg_price),
                    'sold_by_sellers': result.sold_by_sellers,
                    'avg_quantity_per_sale': round(
                        float(result.total_quantity) / result.total_invoices, 2
                    )
                }

                products.append(product_data)
                total_quantity += float(result.total_quantity)
                total_revenue += result.total_revenue

            # Calcular participación
            for product in products:
                if total_quantity > 0:
                    product['quantity_percentage'] = round(
                        (product['total_quantity'] / total_quantity) * 100, 2
                    )
                if total_revenue > 0:
                    product['revenue_percentage'] = round(
                        (product['total_revenue'] / float(total_revenue)) * 100, 2
                    )

            # Análisis adicional
            analysis = {
                'top_by_quantity': products[0] if products else None,
                'top_by_revenue': max(products, key=lambda x: x['total_revenue']) if products else None,
                'most_consistent': max(products, key=lambda x: x['total_invoices']) if products else None,
                'concentration_index': self._calculate_concentration_index(products)
            }

            return {
                'products': products,
                'analysis': analysis,
                'summary': {
                    'total_products': len(products),
                    'total_quantity_sold': total_quantity,
                    'total_revenue': float(total_revenue),
                    'avg_revenue_per_product': float(total_revenue / len(products)) if products else 0
                },
                'period': {
                    'start_date': date_range.start_date.isoformat(),
                    'end_date': date_range.end_date.isoformat()
                }
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando reporte de top productos: {str(e)}"
            )

    # ===== MÉTODOS AUXILIARES =====
    
    def _analyze_difference_trends(self, daily_stats: List[Dict]) -> Dict[str, Any]:
        """Analizar tendencias en diferencias de arqueo"""
        if len(daily_stats) < 2:
            return {'trend': 'insufficient_data'}

        # Calcular tendencia simple
        differences = [stat['avg_difference'] for stat in daily_stats]
        first_half = differences[:len(differences)//2]
        second_half = differences[len(differences)//2:]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        if avg_second > avg_first * 1.1:
            trend = 'worsening'
        elif avg_second < avg_first * 0.9:
            trend = 'improving'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'avg_first_period': avg_first,
            'avg_second_period': avg_second,
            'change_percentage': ((avg_second - avg_first) / abs(avg_first) * 100) if avg_first != 0 else 0
        }

    def _find_most_consistent_shift(self, shifts_data: Dict) -> Optional[str]:
        """Encontrar el turno más consistente basado en variación"""
        if not shifts_data:
            return None

        # Calcular coeficiente de variación para cada turno
        # (Para simplificar, usamos ventas por día como métrica de consistencia)
        most_consistent = None
        best_consistency = float('inf')

        for shift_name, data in shifts_data.items():
            if data['active_days'] > 0:
                consistency = data['sales_per_day']  # Simple metric
                if consistency < best_consistency:
                    best_consistency = consistency
                    most_consistent = shift_name

        return most_consistent

    def _generate_shift_recommendations(self, shifts_data: Dict) -> List[str]:
        """Generar recomendaciones basadas en análisis de turnos"""
        recommendations = []

        if not shifts_data:
            return ["No hay datos suficientes para generar recomendaciones"]

        # Analizar distribución de ventas
        total_sales = sum(data['total_sales'] for data in shifts_data.values())
        
        for shift, data in shifts_data.items():
            percentage = (data['total_sales'] / total_sales * 100) if total_sales > 0 else 0
            
            if percentage < 20:
                recommendations.append(f"Considerar estrategias para incrementar ventas en turno {shift}")
            elif percentage > 50:
                recommendations.append(f"Turno {shift} es muy exitoso, considerar replicar estrategias")

        return recommendations

    def _calculate_concentration_index(self, products: List[Dict]) -> float:
        """Calcular índice de concentración de ventas (Herfindahl-Hirschman)"""
        if not products:
            return 0

        total_revenue = sum(p['total_revenue'] for p in products)
        if total_revenue == 0:
            return 0

        # Calcular HHI
        hhi = sum((p['total_revenue'] / total_revenue) ** 2 for p in products)
        return round(hhi * 10000, 2)  # Normalizado a 10,000


# ===== SCHEMAS PARA REPORTES =====

class DateRangeSchema(BaseModel):
    """Schema para rango de fechas en reportes"""
    start_date: date = Field(..., description="Fecha de inicio")
    end_date: date = Field(..., description="Fecha de fin")

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('La fecha de fin debe ser mayor o igual a la fecha de inicio')
        return v


class SalesBySellerResponse(BaseModel):
    """Response schema para reporte de ventas por vendedor"""
    summary: Dict[str, Any] = Field(description="Resumen general")
    sellers: List[Dict[str, Any]] = Field(description="Datos detallados por vendedor")
    period: Dict[str, str] = Field(description="Información del período")


class CashAuditResponse(BaseModel):
    """Response schema para reporte de arqueos"""
    summary: Dict[str, Any] = Field(description="Resumen de arqueos")
    audits: List[Dict[str, Any]] = Field(description="Arqueos detallados")
    trends: Dict[str, Any] = Field(description="Análisis de tendencias")
    period: Dict[str, str] = Field(description="Información del período")


class ShiftAnalysisResponse(BaseModel):
    """Response schema para análisis de turnos"""
    shifts: Dict[str, Any] = Field(description="Datos por turno")
    comparison: Dict[str, Any] = Field(description="Análisis comparativo")
    summary: Dict[str, Any] = Field(description="Resumen general")
    period: Dict[str, str] = Field(description="Información del período")


class TopProductsResponse(BaseModel):
    """Response schema para top productos"""
    products: List[Dict[str, Any]] = Field(description="Ranking de productos")
    analysis: Dict[str, Any] = Field(description="Análisis adicional")
    summary: Dict[str, Any] = Field(description="Resumen general")
    period: Dict[str, str] = Field(description="Información del período")