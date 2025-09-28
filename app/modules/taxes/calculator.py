"""
Helper para cálculo de impuestos
Este módulo será utilizado por el futuro módulo de facturación
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.modules.products.models import Tax, ProductTax
from app.modules.taxes.schemas import TaxCalculation


class TaxCalculator:
    """Helper para calcular impuestos según la legislación colombiana"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_product_taxes(
        self, 
        product_id: UUID, 
        base_amount: Decimal, 
        company_id: str
    ) -> List[TaxCalculation]:
        """
        Calcular todos los impuestos de un producto
        
        Args:
            product_id: ID del producto
            base_amount: Valor base sobre el cual calcular impuestos
            company_id: ID de la empresa (tenant)
            
        Returns:
            Lista de cálculos de impuestos
        """
        # Obtener impuestos del producto
        product_taxes = self.db.query(ProductTax).filter(
            ProductTax.product_id == product_id,
            ProductTax.tenant_id == company_id
        ).all()
        
        calculations = []
        for product_tax in product_taxes:
            tax = product_tax.tax
            tax_amount = self._calculate_tax_amount(base_amount, tax.rate)
            
            calculations.append(TaxCalculation(
                tax_id=tax.id,
                tax_name=tax.name,
                tax_rate=tax.rate,
                base_amount=base_amount,
                tax_amount=tax_amount
            ))
        
        return calculations
    
    def calculate_taxes_by_ids(
        self, 
        tax_ids: List[UUID], 
        base_amount: Decimal, 
        company_id: str
    ) -> List[TaxCalculation]:
        """
        Calcular impuestos específicos por sus IDs
        
        Args:
            tax_ids: Lista de IDs de impuestos
            base_amount: Valor base sobre el cual calcular impuestos
            company_id: ID de la empresa (tenant)
            
        Returns:
            Lista de cálculos de impuestos
        """
        taxes = self.db.query(Tax).filter(
            Tax.id.in_(tax_ids),
            (Tax.company_id == company_id) | (Tax.company_id.is_(None))
        ).all()
        
        calculations = []
        for tax in taxes:
            tax_amount = self._calculate_tax_amount(base_amount, tax.rate)
            
            calculations.append(TaxCalculation(
                tax_id=tax.id,
                tax_name=tax.name,
                tax_rate=tax.rate,
                base_amount=base_amount,
                tax_amount=tax_amount
            ))
        
        return calculations
    
    def calculate_invoice_totals(
        self, 
        line_items: List[Dict]
    ) -> Dict[str, Decimal]:
        """
        Calcular totales de una factura (futuro)
        
        Args:
            line_items: Lista de líneas de factura con formato:
                [
                    {
                        "product_id": UUID,
                        "quantity": int,
                        "unit_price": Decimal,
                        "discount": Decimal (opcional)
                    }
                ]
                
        Returns:
            Diccionario con totales:
            {
                "subtotal": Decimal,
                "total_taxes": Decimal,
                "total": Decimal,
                "tax_breakdown": List[TaxCalculation]
            }
        """
        subtotal = Decimal('0.00')
        all_tax_calculations = []
        
        for item in line_items:
            quantity = Decimal(str(item['quantity']))
            unit_price = Decimal(str(item['unit_price']))
            discount = Decimal(str(item.get('discount', 0)))
            
            # Calcular valor línea
            line_total = (quantity * unit_price) - discount
            subtotal += line_total
            
            # Calcular impuestos de la línea si tiene product_id
            if 'product_id' in item and 'company_id' in item:
                line_taxes = self.calculate_product_taxes(
                    item['product_id'], 
                    line_total, 
                    item['company_id']
                )
                all_tax_calculations.extend(line_taxes)
        
        # Sumar todos los impuestos
        total_taxes = sum(calc.tax_amount for calc in all_tax_calculations)
        total = subtotal + total_taxes
        
        # Agrupar impuestos por tipo
        tax_breakdown = self._group_taxes(all_tax_calculations)
        
        return {
            "subtotal": subtotal,
            "total_taxes": total_taxes,
            "total": total,
            "tax_breakdown": tax_breakdown
        }
    
    def _calculate_tax_amount(self, base_amount: Decimal, tax_rate: Decimal) -> Decimal:
        """
        Calcular el valor del impuesto con redondeo apropiado
        
        Args:
            base_amount: Valor base
            tax_rate: Tasa del impuesto (ej. 0.19 para 19%)
            
        Returns:
            Valor del impuesto redondeado
        """
        tax_amount = base_amount * tax_rate
        # Redondear a 2 decimales usando ROUND_HALF_UP (redondeo comercial)
        return tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def _group_taxes(self, calculations: List[TaxCalculation]) -> List[Dict]:
        """
        Agrupar cálculos de impuestos por tipo/nombre
        
        Args:
            calculations: Lista de cálculos individuales
            
        Returns:
            Lista de impuestos agrupados
        """
        grouped = {}
        
        for calc in calculations:
            key = f"{calc.tax_name}_{calc.tax_rate}"
            if key not in grouped:
                grouped[key] = {
                    "tax_name": calc.tax_name,
                    "tax_rate": calc.tax_rate,
                    "base_amount": Decimal('0.00'),
                    "tax_amount": Decimal('0.00')
                }
            
            grouped[key]["base_amount"] += calc.base_amount
            grouped[key]["tax_amount"] += calc.tax_amount
        
        return list(grouped.values())
    
    def validate_tax_compliance(self, company_id: str) -> Dict[str, bool]:
        """
        Validar cumplimiento tributario básico (futuro)
        
        Returns:
            Diccionario con validaciones
        """
        return {
            "has_iva_taxes": True,  # Placeholder
            "has_withholding_setup": True,  # Placeholder
            "ready_for_invoicing": True  # Placeholder
        }


def get_standard_colombian_taxes() -> List[Dict]:
    """
    Obtener lista de impuestos estándar colombianos
    Útil para interfaces de usuario
    """
    return [
        {
            "name": "IVA 19%",
            "description": "Impuesto al Valor Agregado general",
            "rate": 0.19,
            "applicable_to": "Mayoría de bienes y servicios"
        },
        {
            "name": "IVA 5%",
            "description": "Impuesto al Valor Agregado reducido",
            "rate": 0.05,
            "applicable_to": "Bienes de primera necesidad"
        },
        {
            "name": "IVA 0%",
            "description": "Bienes exentos de IVA",
            "rate": 0.00,
            "applicable_to": "Productos exentos (medicamentos, libros, etc.)"
        },
        {
            "name": "INC 8%",
            "description": "Impuesto Nacional al Consumo",
            "rate": 0.08,
            "applicable_to": "Restaurantes y bares"
        },
        {
            "name": "INC 16%",
            "description": "Impuesto Nacional al Consumo",
            "rate": 0.16,
            "applicable_to": "Licores y cigarrillos"
        }
    ]