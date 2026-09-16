from __future__ import annotations

from ledgix_saas.services import erpnext_reporting_compat as erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    data = erpnext_reporting.sales_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext sales found for selected filters.</div>"
    return get_columns(), data, message, None, erpnext_reporting.report_summary("sales", data)


def get_columns():
    return [
        {"label": "Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 115},
        {"label": "Invoice", "fieldname": "sale", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 150},
        {"label": "Date", "fieldname": "sale_date", "fieldtype": "Date", "width": 105},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 105},
        {"label": "Items", "fieldname": "items_count", "fieldtype": "Int", "width": 80},
        {"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 105},
        {"label": "Grand Total", "fieldname": "total_amount", "fieldtype": "Currency", "width": 135},
        {"label": "Gross Profit", "fieldname": "total_profit", "fieldtype": "Currency", "width": 130},
        {"label": "Avg Sale Value", "fieldname": "avg_sale_value", "fieldtype": "Currency", "width": 135},
    ]
