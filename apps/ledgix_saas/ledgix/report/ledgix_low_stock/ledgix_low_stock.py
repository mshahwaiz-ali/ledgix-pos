from __future__ import annotations

from ledgix_saas.services import erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    data = erpnext_reporting.low_stock_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext items are at or below their reorder level.</div>"
    return get_columns(), data, message, None, erpnext_reporting.report_summary("low_stock", data)


def get_columns():
    return [
        {"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 190},
        {"label": "Item Group", "fieldname": "category", "fieldtype": "Link", "options": "Item Group", "width": 145},
        {"label": "Current Stock", "fieldname": "current_stock", "fieldtype": "Float", "width": 120},
        {"label": "Reorder Level", "fieldname": "minimum_stock", "fieldtype": "Float", "width": 125},
        {"label": "Shortage Qty", "fieldname": "shortage_qty", "fieldtype": "Float", "width": 120},
        {"label": "Valuation Rate", "fieldname": "cost_price", "fieldtype": "Currency", "width": 120},
        {"label": "Selling Price", "fieldname": "selling_price", "fieldtype": "Currency", "width": 120},
        {"label": "Stock Value", "fieldname": "stock_value", "fieldtype": "Currency", "width": 125},
        {"label": "Potential Sales Gap", "fieldname": "potential_sales_gap", "fieldtype": "Currency", "width": 150},
        {"label": "Risk Status", "fieldname": "risk_status", "fieldtype": "Data", "width": 125},
    ]
