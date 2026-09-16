from __future__ import annotations

from ledgix_saas.services import erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    data = erpnext_reporting.current_stock_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext stock data found for selected filters.</div>"
    return get_columns(), data, message, None, erpnext_reporting.report_summary("stock", data)


def get_columns():
    return [
        {"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 155},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 190},
        {"label": "Item Group", "fieldname": "category", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": "UOM", "fieldname": "unit", "fieldtype": "Data", "width": 85},
        {"label": "Current Stock", "fieldname": "current_stock", "fieldtype": "Float", "width": 125},
        {"label": "Reorder Level", "fieldname": "minimum_stock", "fieldtype": "Float", "width": 125},
        {"label": "Stock Status", "fieldname": "stock_status", "fieldtype": "Data", "width": 125},
        {"label": "Valuation Rate", "fieldname": "cost_price", "fieldtype": "Currency", "width": 120},
        {"label": "Selling Price", "fieldname": "selling_price", "fieldtype": "Currency", "width": 120},
        {"label": "Stock Value", "fieldname": "stock_value", "fieldtype": "Currency", "width": 130},
        {"label": "Potential Profit", "fieldname": "potential_profit", "fieldtype": "Currency", "width": 135},
    ]
