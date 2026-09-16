from __future__ import annotations

from ledgix_saas.services import erpnext_reporting_compat as erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    data = erpnext_reporting.sales_return_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext returns found for selected filters.</div>"
    return get_columns(), data, message, None, erpnext_reporting.report_summary("returns", data)


def get_columns():
    return [
        {"label": "Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 115},
        {"label": "Credit Note / Return", "fieldname": "sales_return", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 160},
        {"label": "Original Invoice", "fieldname": "original_sale", "fieldtype": "Data", "width": 145},
        {"label": "Date", "fieldname": "return_date", "fieldtype": "Date", "width": 105},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 105},
        {"label": "Items", "fieldname": "items_count", "fieldtype": "Int", "width": 80},
        {"label": "Return Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 110},
        {"label": "Return Amount", "fieldname": "return_amount", "fieldtype": "Currency", "width": 135},
        {"label": "Margin Reversal", "fieldname": "total_profit_reversal", "fieldtype": "Currency", "width": 135},
    ]
