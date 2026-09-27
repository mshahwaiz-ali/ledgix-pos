from __future__ import annotations

from ledgix_saas.services import erpnext_reporting


def execute(filters=None):
    filters = filters or {}
    data = erpnext_reporting.stock_movement_rows(filters)
    message = None if data else "<div style='padding:20px;text-align:center;color:#667085'>No ERPNext stock ledger activity found for selected filters.</div>"
    return get_columns(), data, message, None, erpnext_reporting.report_summary("movements", data)


def get_columns():
    return [
        {"label": "Date", "fieldname": "movement_date", "fieldtype": "Datetime", "width": 155},
        {"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 175},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
        {"label": "Flow", "fieldname": "movement_type", "fieldtype": "Data", "width": 85},
        {"label": "Qty", "fieldname": "quantity", "fieldtype": "Float", "width": 90},
        {"label": "Qty After", "fieldname": "qty_after_transaction", "fieldtype": "Float", "width": 105},
        {"label": "Valuation Rate", "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 120},
        {"label": "Reference Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 140},
        {"label": "Reference", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 155},
        {"label": "Batch", "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 125},
        {"label": "Serial", "fieldname": "serial_no", "fieldtype": "Data", "width": 145},
    ]
