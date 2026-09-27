from __future__ import annotations

from ledgix_saas.services import erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    if not filters.get("customer"):
        return columns, [], "<div style='padding:20px;text-align:center;color:#667085'>Please select an ERPNext Customer.</div>", None, []
    data = erpnext_reporting.customer_statement_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext customer ledger activity found for selected filters.</div>"
    return columns, data, message, None, erpnext_reporting.report_summary("statement", data)


def get_columns():
    return [
        {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 120},
        {"label": "Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 150},
        {"label": "Reference", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 155},
        {"label": "Invoice No", "fieldname": "invoice_number", "fieldtype": "Data", "width": 130},
        {"label": "Details", "fieldname": "details", "fieldtype": "Data", "width": 235},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Balance", "fieldname": "balance", "fieldtype": "Currency", "width": 125},
    ]
