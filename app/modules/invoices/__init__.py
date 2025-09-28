"""
Módulo de Facturación (Invoices) - Ally360 ERP

Este módulo maneja la facturación de ventas con las siguientes características:

- Gestión de clientes
- Creación y gestión de facturas de venta
- Integración con inventario (actualizaciones automáticas de stock)
- Integración con sistema de impuestos
- Gestión de pagos (parciales y completos)
- Reportes de ventas
- Generación de PDF (pendiente implementación)
- Envío por email (pendiente implementación)

Arquitectura multi-tenant con roles y permisos:
- owner/admin: CRUD completo
- seller: Crear, leer, actualizar (solo draft)
- accountant: Leer, pagos
- viewer: Solo lectura

Tablas principales:
- customers: Clientes
- invoices: Facturas de venta
- invoice_line_items: Ítems de factura
- payments: Pagos de facturas
- invoice_sequences: Secuencias de numeración por PDV
"""

from .models import Customer, Invoice, InvoiceLineItem, Payment, InvoiceSequence
from .schemas import (
    CustomerCreate, CustomerOut, CustomerUpdate,
    InvoiceCreate, InvoiceOut, InvoiceDetail,
    PaymentCreate, PaymentOut
)
from .service import CustomerService, InvoiceService
from .router import router

__all__ = [
    "Customer", "Invoice", "InvoiceLineItem", "Payment", "InvoiceSequence",
    "CustomerCreate", "CustomerOut", "CustomerUpdate",
    "InvoiceCreate", "InvoiceOut", "InvoiceDetail",
    "PaymentCreate", "PaymentOut",
    "CustomerService", "InvoiceService",
    "router"
]
