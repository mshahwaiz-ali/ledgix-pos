from __future__ import annotations

from ledgix_saas.services import erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    data = erpnext_reporting.purchase_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext purchases found for selected filters.</div>"
    return get_columns(), data, message, None, erpnext_reporting.report_summary("purchases", data)


def get_columns():
    return [
        {"label": "Purchase Invoice", "fieldname": "purchase", "fieldtype": "Link", "options": "Purchase Invoice", "width": 155},
        {"label": "Supplier Invoice", "fieldname": "invoice_number", "fieldtype": "Data", "width": 130},
        {"label": "Date", "fieldname": "purchase_date", "fieldtype": "Date", "width": 105},
        {"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 105},
        {"label": "Items", "fieldname": "items_count", "fieldtype": "Int", "width": 80},
        {"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 110},
        {"label": "Grand Total", "fieldname": "total_cost", "fieldtype": "Currency", "width": 135},
        {"label": "Avg Cost", "fieldname": "avg_cost", "fieldtype": "Currency", "width": 120},
    ]
