"""
Utilities for Reports module

Provides CSV export functionality and common utility functions
for report generation and data formatting.
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Union

from fastapi import Response


def create_csv_response(
    data: List[Dict[str, Any]], 
    filename: str,
    headers: Dict[str, str] = None
) -> Response:
    """
    Create a CSV response from a list of dictionaries.
    
    Args:
        data: List of dictionaries with report data
        filename: Name for the CSV file
        headers: Optional mapping of field names to CSV headers
        
    Returns:
        FastAPI Response with CSV content
    """
    if not data:
        # Return empty CSV with just headers
        csv_content = ""
        if headers:
            csv_content = ",".join(headers.values()) + "\n"
    else:
        output = io.StringIO()
        
        # Use headers mapping if provided, otherwise use keys from first row
        fieldnames = list(headers.keys()) if headers else list(data[0].keys())
        csv_headers = list(headers.values()) if headers else fieldnames
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        # Write header row with custom names
        writer.writerow(dict(zip(fieldnames, csv_headers)))
        
        # Write data rows
        for row in data:
            # Format values for CSV export
            formatted_row = {}
            for key, value in row.items():
                if key in fieldnames:
                    formatted_row[key] = format_csv_value(value)
            writer.writerow(formatted_row)
        
        csv_content = output.getvalue()
        output.close()
    
    # Create response with proper headers
    response = Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )
    
    return response


def format_csv_value(value: Any) -> str:
    """
    Format a value for CSV export.
    
    Args:
        value: Value to format
        
    Returns:
        String representation suitable for CSV
    """
    if value is None:
        return ""
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, (date, datetime)):
        return value.isoformat()
    elif isinstance(value, bool):
        return "Yes" if value else "No"
    elif isinstance(value, (list, dict)):
        return str(value)
    else:
        return str(value)


def prepare_sales_summary_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare sales summary data for CSV export"""
    return [{
        "period_start": report_data["period_start"],
        "period_end": report_data["period_end"],
        "total_sales": report_data["total_sales"],
        "total_amount": report_data["total_amount"],
        "average_ticket": report_data["average_ticket"],
        "total_invoices": report_data["total_invoices"],
        "total_pos_sales": report_data["total_pos_sales"]
    }]


def prepare_sales_by_product_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare sales by product data for CSV export"""
    csv_data = []
    for product in report_data["products"]:
        csv_data.append({
            "product_name": product["product_name"],
            "product_sku": product["product_sku"],
            "category_name": product.get("category_name", ""),
            "brand_name": product.get("brand_name", ""),
            "quantity_sold": product["quantity_sold"],
            "total_amount": product["total_amount"],
            "average_price": product["average_price"],
            "sales_count": product["sales_count"]
        })
    return csv_data


def prepare_sales_by_seller_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare sales by seller data for CSV export"""
    csv_data = []
    for seller in report_data["sellers"]:
        csv_data.append({
            "seller_name": seller["seller_name"],
            "total_sales": seller["total_sales"],
            "total_amount": seller["total_amount"],
            "average_ticket": seller["average_ticket"],
            "commission_rate": seller.get("commission_rate", ""),
            "estimated_commission": seller.get("estimated_commission", "")
        })
    return csv_data


def prepare_top_customers_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare top customers data for CSV export"""
    csv_data = []
    for customer in report_data["customers"]:
        csv_data.append({
            "customer_name": customer["customer_name"],
            "customer_email": customer.get("customer_email", ""),
            "customer_phone": customer.get("customer_phone", ""),
            "total_purchases": customer["total_purchases"],
            "total_amount": customer["total_amount"],
            "average_purchase": customer["average_purchase"],
            "last_purchase_date": customer.get("last_purchase_date", "")
        })
    return csv_data


def prepare_purchases_by_supplier_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare purchases by supplier data for CSV export"""
    csv_data = []
    for supplier in report_data["suppliers"]:
        csv_data.append({
            "supplier_name": supplier["supplier_name"],
            "supplier_email": supplier.get("supplier_email", ""),
            "supplier_phone": supplier.get("supplier_phone", ""),
            "total_bills": supplier["total_bills"],
            "total_amount": supplier["total_amount"],
            "average_bill": supplier["average_bill"],
            "last_bill_date": supplier.get("last_bill_date", "")
        })
    return csv_data


def prepare_purchases_by_category_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare purchases by category data for CSV export"""
    csv_data = []
    for category in report_data["categories"]:
        csv_data.append({
            "category_name": category["category_name"],
            "total_quantity": category["total_quantity"],
            "total_amount": category["total_amount"],
            "average_price": category["average_price"],
            "bills_count": category["bills_count"]
        })
    return csv_data


def prepare_inventory_stock_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare inventory stock data for CSV export"""
    csv_data = []
    for item in report_data["items"]:
        csv_data.append({
            "product_name": item["product_name"],
            "product_sku": item["product_sku"],
            "category_name": item.get("category_name", ""),
            "brand_name": item.get("brand_name", ""),
            "pdv_name": item["pdv_name"],
            "current_stock": item["current_stock"],
            "minimum_stock": item.get("minimum_stock", ""),
            "maximum_stock": item.get("maximum_stock", ""),
            "is_low_stock": item["is_low_stock"],
            "last_movement_date": item.get("last_movement_date", "")
        })
    return csv_data


def prepare_kardex_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare kardex data for CSV export"""
    csv_data = []
    for movement in report_data["movements"]:
        csv_data.append({
            "movement_date": movement["movement_date"],
            "movement_type": movement["movement_type"],
            "quantity": movement["quantity"],
            "reference": movement.get("reference", ""),
            "notes": movement.get("notes", ""),
            "running_balance": movement["running_balance"],
            "unit_cost": movement.get("unit_cost", ""),
            "total_cost": movement.get("total_cost", "")
        })
    return csv_data


def prepare_cash_register_summary_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare cash register summary data for CSV export"""
    csv_data = []
    for register in report_data["registers"]:
        csv_data.append({
            "cash_register_name": register["cash_register_name"],
            "pdv_name": register["pdv_name"],
            "opened_by_name": register["opened_by_name"],
            "closed_by_name": register.get("closed_by_name", ""),
            "opened_at": register["opened_at"],
            "closed_at": register.get("closed_at", ""),
            "opening_balance": register["opening_balance"],
            "closing_balance": register.get("closing_balance", ""),
            "calculated_balance": register["calculated_balance"],
            "difference": register.get("difference", ""),
            "total_sales": register["total_sales"],
            "total_deposits": register["total_deposits"],
            "total_withdrawals": register["total_withdrawals"],
            "total_expenses": register["total_expenses"],
            "movements_count": register["movements_count"]
        })
    return csv_data


def prepare_cash_movements_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare cash movements data for CSV export"""
    csv_data = []
    for movement in report_data["movements"]:
        csv_data.append({
            "movement_date": movement["movement_date"],
            "movement_type": movement["movement_type"],
            "amount": movement["amount"],
            "signed_amount": movement["signed_amount"],
            "reference": movement.get("reference", ""),
            "notes": movement.get("notes", ""),
            "invoice_number": movement.get("invoice_number", ""),
            "created_by_name": movement["created_by_name"]
        })
    return csv_data


def prepare_income_vs_expenses_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare income vs expenses data for CSV export"""
    return [{
        "period_start": report_data["period_start"],
        "period_end": report_data["period_end"],
        "total_income": report_data["total_income"],
        "total_expenses": report_data["total_expenses"],
        "net_profit": report_data["net_profit"],
        "paid_invoices_count": report_data["paid_invoices_count"],
        "paid_bills_count": report_data["paid_bills_count"],
        "pending_invoices_count": report_data["pending_invoices_count"],
        "pending_bills_count": report_data["pending_bills_count"],
        "cash_income": report_data["cash_income"],
        "card_income": report_data["card_income"],
        "transfer_income": report_data["transfer_income"],
        "other_income": report_data["other_income"]
    }]


def prepare_accounts_receivable_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare accounts receivable data for CSV export"""
    csv_data = []
    for invoice in report_data["invoices"]:
        csv_data.append({
            "invoice_number": invoice["invoice_number"],
            "customer_name": invoice["customer_name"],
            "issue_date": invoice["issue_date"],
            "due_date": invoice["due_date"],
            "total_amount": invoice["total_amount"],
            "paid_amount": invoice["paid_amount"],
            "pending_amount": invoice["pending_amount"],
            "days_overdue": invoice["days_overdue"],
            "is_overdue": invoice["is_overdue"]
        })
    return csv_data


def prepare_accounts_payable_csv(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare accounts payable data for CSV export"""
    csv_data = []
    for bill in report_data["bills"]:
        csv_data.append({
            "bill_number": bill["bill_number"],
            "supplier_name": bill["supplier_name"],
            "issue_date": bill["issue_date"],
            "due_date": bill["due_date"],
            "total_amount": bill["total_amount"],
            "paid_amount": bill["paid_amount"],
            "pending_amount": bill["pending_amount"],
            "days_overdue": bill["days_overdue"],
            "is_overdue": bill["is_overdue"]
        })
    return csv_data


# CSV Headers mapping for better column names
CSV_HEADERS = {
    "sales_summary": {
        "period_start": "Fecha Inicio",
        "period_end": "Fecha Fin",
        "total_sales": "Total Ventas",
        "total_amount": "Monto Total",
        "average_ticket": "Ticket Promedio",
        "total_invoices": "Total Facturas",
        "total_pos_sales": "Ventas POS"
    },
    "sales_by_product": {
        "product_name": "Producto",
        "product_sku": "SKU",
        "category_name": "Categoría",
        "brand_name": "Marca",
        "quantity_sold": "Cantidad Vendida",
        "total_amount": "Monto Total",
        "average_price": "Precio Promedio",
        "sales_count": "Número de Ventas"
    },
    "sales_by_seller": {
        "seller_name": "Vendedor",
        "total_sales": "Total Ventas",
        "total_amount": "Monto Total",
        "average_ticket": "Ticket Promedio",
        "commission_rate": "Tasa Comisión",
        "estimated_commission": "Comisión Estimada"
    },
    "top_customers": {
        "customer_name": "Cliente",
        "customer_email": "Email",
        "customer_phone": "Teléfono",
        "total_purchases": "Total Compras",
        "total_amount": "Monto Total",
        "average_purchase": "Compra Promedio",
        "last_purchase_date": "Última Compra"
    },
    "purchases_by_supplier": {
        "supplier_name": "Proveedor",
        "supplier_email": "Email",
        "supplier_phone": "Teléfono",
        "total_bills": "Total Facturas",
        "total_amount": "Monto Total",
        "average_bill": "Factura Promedio",
        "last_bill_date": "Última Factura"
    },
    "purchases_by_category": {
        "category_name": "Categoría",
        "total_quantity": "Cantidad Total",
        "total_amount": "Monto Total",
        "average_price": "Precio Promedio",
        "bills_count": "Número de Facturas"
    },
    "inventory_stock": {
        "product_name": "Producto",
        "product_sku": "SKU",
        "category_name": "Categoría",
        "brand_name": "Marca",
        "pdv_name": "PDV",
        "current_stock": "Stock Actual",
        "minimum_stock": "Stock Mínimo",
        "maximum_stock": "Stock Máximo",
        "is_low_stock": "Stock Bajo",
        "last_movement_date": "Último Movimiento"
    },
    "kardex": {
        "movement_date": "Fecha",
        "movement_type": "Tipo",
        "quantity": "Cantidad",
        "reference": "Referencia",
        "notes": "Notas",
        "running_balance": "Saldo",
        "unit_cost": "Costo Unitario",
        "total_cost": "Costo Total"
    },
    "cash_register_summary": {
        "cash_register_name": "Caja",
        "pdv_name": "PDV",
        "opened_by_name": "Abierto Por",
        "closed_by_name": "Cerrado Por",
        "opened_at": "Fecha Apertura",
        "closed_at": "Fecha Cierre",
        "opening_balance": "Saldo Apertura",
        "closing_balance": "Saldo Cierre",
        "calculated_balance": "Saldo Calculado",
        "difference": "Diferencia",
        "total_sales": "Total Ventas",
        "total_deposits": "Total Depósitos",
        "total_withdrawals": "Total Retiros",
        "total_expenses": "Total Gastos",
        "movements_count": "Número Movimientos"
    },
    "cash_movements": {
        "movement_date": "Fecha",
        "movement_type": "Tipo",
        "amount": "Monto",
        "signed_amount": "Monto con Signo",
        "reference": "Referencia",
        "notes": "Notas",
        "invoice_number": "Número Factura",
        "created_by_name": "Creado Por"
    },
    "income_vs_expenses": {
        "period_start": "Fecha Inicio",
        "period_end": "Fecha Fin",
        "total_income": "Total Ingresos",
        "total_expenses": "Total Egresos",
        "net_profit": "Ganancia Neta",
        "paid_invoices_count": "Facturas Pagadas",
        "paid_bills_count": "Bills Pagadas",
        "pending_invoices_count": "Facturas Pendientes",
        "pending_bills_count": "Bills Pendientes",
        "cash_income": "Ingresos Efectivo",
        "card_income": "Ingresos Tarjeta",
        "transfer_income": "Ingresos Transferencia",
        "other_income": "Otros Ingresos"
    },
    "accounts_receivable": {
        "invoice_number": "Número Factura",
        "customer_name": "Cliente",
        "issue_date": "Fecha Emisión",
        "due_date": "Fecha Vencimiento",
        "total_amount": "Monto Total",
        "paid_amount": "Monto Pagado",
        "pending_amount": "Monto Pendiente",
        "days_overdue": "Días Vencido",
        "is_overdue": "Vencido"
    },
    "accounts_payable": {
        "bill_number": "Número Factura",
        "supplier_name": "Proveedor",
        "issue_date": "Fecha Emisión",
        "due_date": "Fecha Vencimiento",
        "total_amount": "Monto Total",
        "paid_amount": "Monto Pagado",
        "pending_amount": "Monto Pendiente",
        "days_overdue": "Días Vencido",
        "is_overdue": "Vencido"
    }
}