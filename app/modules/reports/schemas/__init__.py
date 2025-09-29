"""
Pydantic schemas for Reports module

Defines request and response models for all report endpoints.
All schemas include proper validation and documentation for OpenAPI.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


# Base filters for common report parameters
class BaseDateRangeFilter(BaseModel):
    """Base filter for date range queries"""
    start_date: date = Field(..., description="Start date for the report period")
    end_date: date = Field(..., description="End date for the report period")
    pdv_id: Optional[UUID] = Field(None, description="Optional PDV filter")
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be greater than or equal to start_date')
        return v


class PaginationParams(BaseModel):
    """Pagination parameters for paginated reports"""
    limit: int = Field(100, ge=1, le=1000, description="Number of records per page")
    offset: int = Field(0, ge=0, description="Number of records to skip")


class ExportParams(BaseModel):
    """Export format parameters"""
    export: Optional[str] = Field(None, pattern="^(csv)$", description="Export format: csv")


# Sales Report Schemas
class SalesSummaryFilter(BaseDateRangeFilter):
    """Filters for sales summary report"""
    customer_id: Optional[UUID] = Field(None, description="Filter by specific customer")
    seller_id: Optional[UUID] = Field(None, description="Filter by specific seller")


class SalesSummaryResponse(BaseModel):
    """Response for sales summary report"""
    period_start: date
    period_end: date
    total_sales: int = Field(description="Total number of sales")
    total_amount: Decimal = Field(description="Total sales amount")
    average_ticket: Decimal = Field(description="Average sale amount")
    total_invoices: int = Field(description="Total invoices count")
    total_pos_sales: int = Field(description="Total POS sales count")


class SalesByProductItem(BaseModel):
    """Individual item in sales by product report"""
    product_id: UUID
    product_name: str
    product_sku: str
    category_name: Optional[str]
    brand_name: Optional[str]
    quantity_sold: Decimal
    total_amount: Decimal
    average_price: Decimal
    sales_count: int


class SalesByProductResponse(BaseModel):
    """Response for sales by product report"""
    period_start: date
    period_end: date
    products: List[SalesByProductItem]
    total_products: int
    summary: SalesSummaryResponse


class SalesBySellerItem(BaseModel):
    """Individual item in sales by seller report"""
    seller_id: UUID
    seller_name: str
    total_sales: int
    total_amount: Decimal
    average_ticket: Decimal
    commission_rate: Optional[Decimal]
    estimated_commission: Optional[Decimal]


class SalesBySellerResponse(BaseModel):
    """Response for sales by seller report"""
    period_start: date
    period_end: date
    sellers: List[SalesBySellerItem]
    total_sellers: int
    summary: SalesSummaryResponse


class TopCustomersItem(BaseModel):
    """Individual item in top customers report"""
    customer_id: UUID
    customer_name: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    total_purchases: int
    total_amount: Decimal
    average_purchase: Decimal
    last_purchase_date: Optional[date]


class TopCustomersResponse(BaseModel):
    """Response for top customers report"""
    period_start: date
    period_end: date
    customers: List[TopCustomersItem]
    total_customers: int


# Purchase Report Schemas
class PurchasesBySupplierFilter(BaseDateRangeFilter):
    """Filters for purchases by supplier report"""
    supplier_id: Optional[UUID] = Field(None, description="Filter by specific supplier")


class PurchasesBySupplierItem(BaseModel):
    """Individual item in purchases by supplier report"""
    supplier_id: UUID
    supplier_name: str
    supplier_email: Optional[str]
    supplier_phone: Optional[str]
    total_bills: int
    total_amount: Decimal
    average_bill: Decimal
    last_bill_date: Optional[date]


class PurchasesBySupplierResponse(BaseModel):
    """Response for purchases by supplier report"""
    period_start: date
    period_end: date
    suppliers: List[PurchasesBySupplierItem]
    total_suppliers: int
    total_amount: Decimal


class PurchasesByCategoryItem(BaseModel):
    """Individual item in purchases by category report"""
    category_id: Optional[UUID]
    category_name: str
    total_quantity: Decimal
    total_amount: Decimal
    average_price: Decimal
    bills_count: int


class PurchasesByCategoryResponse(BaseModel):
    """Response for purchases by category report"""
    period_start: date
    period_end: date
    categories: List[PurchasesByCategoryItem]
    total_categories: int
    total_amount: Decimal


# Inventory Report Schemas
class InventoryStockFilter(BaseModel):
    """Filters for inventory stock report"""
    pdv_id: Optional[UUID] = Field(None, description="Filter by specific PDV")
    category_id: Optional[UUID] = Field(None, description="Filter by product category")
    brand_id: Optional[UUID] = Field(None, description="Filter by product brand")
    low_stock_only: bool = Field(False, description="Show only products with low stock")


class InventoryStockItem(BaseModel):
    """Individual item in inventory stock report"""
    product_id: UUID
    product_name: str
    product_sku: str
    category_name: Optional[str]
    brand_name: Optional[str]
    pdv_name: str
    current_stock: Decimal
    minimum_stock: Optional[Decimal]
    maximum_stock: Optional[Decimal]
    is_low_stock: bool
    last_movement_date: Optional[datetime]


class InventoryStockResponse(BaseModel):
    """Response for inventory stock report"""
    as_of_date: datetime
    items: List[InventoryStockItem]
    total_items: int
    low_stock_count: int


class KardexFilter(BaseModel):
    """Filters for kardex report"""
    product_id: UUID = Field(..., description="Product ID for kardex")
    pdv_id: Optional[UUID] = Field(None, description="Optional PDV filter")
    start_date: Optional[date] = Field(None, description="Start date for movements")
    end_date: Optional[date] = Field(None, description="End date for movements")


class KardexMovementItem(BaseModel):
    """Individual movement in kardex report"""
    movement_date: datetime
    movement_type: str  # IN, OUT, ADJUSTMENT
    quantity: int
    reference: Optional[str]
    notes: Optional[str]
    running_balance: Decimal
    unit_cost: Optional[Decimal]
    total_cost: Optional[Decimal]


class KardexResponse(BaseModel):
    """Response for kardex report"""
    product_id: UUID
    product_name: str
    product_sku: str
    pdv_name: Optional[str]
    period_start: Optional[date]
    period_end: Optional[date]
    movements: List[KardexMovementItem]
    initial_balance: Decimal
    final_balance: Decimal
    total_in: Decimal
    total_out: Decimal


class LowStockResponse(BaseModel):
    """Response for low stock report"""
    as_of_date: datetime
    items: List[InventoryStockItem]
    total_low_stock_items: int


# Cash Register Report Schemas
class CashRegisterSummaryFilter(BaseDateRangeFilter):
    """Filters for cash register summary report"""
    cash_register_id: Optional[UUID] = Field(None, description="Filter by specific cash register")
    status: Optional[str] = Field(None, pattern="^(open|closed)$", description="Filter by status")


class CashRegisterSummaryItem(BaseModel):
    """Individual item in cash register summary report"""
    cash_register_id: UUID
    cash_register_name: str
    pdv_name: str
    opened_by_name: str
    closed_by_name: Optional[str]
    opened_at: datetime
    closed_at: Optional[datetime]
    opening_balance: Decimal
    closing_balance: Optional[Decimal]
    calculated_balance: Decimal
    difference: Optional[Decimal]
    total_sales: Decimal
    total_deposits: Decimal
    total_withdrawals: Decimal
    total_expenses: Decimal
    total_adjustments: Decimal
    movements_count: int


class CashRegisterSummaryResponse(BaseModel):
    """Response for cash register summary report"""
    period_start: date
    period_end: date
    registers: List[CashRegisterSummaryItem]
    total_registers: int
    total_opening_balance: Decimal
    total_closing_balance: Decimal
    total_calculated_balance: Decimal
    total_difference: Decimal


class CashMovementItem(BaseModel):
    """Individual movement in cash register movements report"""
    movement_id: UUID
    movement_date: datetime
    movement_type: str
    amount: Decimal
    signed_amount: Decimal
    reference: Optional[str]
    notes: Optional[str]
    invoice_number: Optional[str]
    created_by_name: str


class CashMovementsResponse(BaseModel):
    """Response for cash register movements report"""
    cash_register_id: UUID
    cash_register_name: str
    movements: List[CashMovementItem]
    total_movements: int
    summary_by_type: dict  # Type: total amount


# Financial Report Schemas
class IncomeVsExpensesFilter(BaseDateRangeFilter):
    """Filters for income vs expenses report"""
    include_pending: bool = Field(False, description="Include unpaid invoices/bills")


class IncomeVsExpensesResponse(BaseModel):
    """Response for income vs expenses report"""
    period_start: date
    period_end: date
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    paid_invoices_count: int
    paid_bills_count: int
    pending_invoices_count: int
    pending_bills_count: int
    cash_income: Decimal
    card_income: Decimal
    transfer_income: Decimal
    other_income: Decimal


class AccountsReceivableItem(BaseModel):
    """Individual item in accounts receivable report"""
    invoice_id: UUID
    invoice_number: str
    customer_id: UUID
    customer_name: str
    issue_date: date
    due_date: date
    total_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    days_overdue: int
    is_overdue: bool


class AccountsReceivableResponse(BaseModel):
    """Response for accounts receivable report"""
    as_of_date: date
    invoices: List[AccountsReceivableItem]
    total_invoices: int
    total_pending_amount: Decimal
    overdue_invoices_count: int
    overdue_amount: Decimal
    current_amount: Decimal


class AccountsPayableItem(BaseModel):
    """Individual item in accounts payable report"""
    bill_id: UUID
    bill_number: str
    supplier_id: UUID
    supplier_name: str
    issue_date: date
    due_date: date
    total_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    days_overdue: int
    is_overdue: bool


class AccountsPayableResponse(BaseModel):
    """Response for accounts payable report"""
    as_of_date: date
    bills: List[AccountsPayableItem]
    total_bills: int
    total_pending_amount: Decimal
    overdue_bills_count: int
    overdue_amount: Decimal
    current_amount: Decimal


# Generic paginated response wrapper
class PaginatedResponse(BaseModel):
    """Generic wrapper for paginated responses"""
    data: BaseModel
    pagination: dict = Field(description="Pagination metadata")
    
    class Config:
        arbitrary_types_allowed = True