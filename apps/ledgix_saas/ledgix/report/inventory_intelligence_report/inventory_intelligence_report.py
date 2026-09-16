from __future__ import annotations

from frappe.utils import flt

from ledgix_saas.services import erpnext_reporting


def execute(filters=None):
    filters = dict(filters or {})
    response = erpnext_reporting.inventory_intelligence(
        {
            "item": filters.get("item"),
            "from_date": filters.get("from_date"),
            "to_date": filters.get("to_date"),
            "tracking_type": filters.get("tracking_type") or "All",
        }
    )
    rows = []
    for row in response.get("timeline") or []:
        rows.append(
            {
                "posting_date": row.get("date"),
                "event_type": row.get("event_type"),
                "item": row.get("item"),
                "item_name": row.get("item_name"),
                "reference_doctype": row.get("reference_doctype"),
                "reference_name": row.get("reference_name"),
                "warehouse": row.get("warehouse"),
                "qty": row.get("qty"),
                "running_qty": row.get("running_qty"),
                "rate": row.get("cost_rate"),
                "batch_no": row.get("batch_no"),
                "serial_no": row.get("serial_no"),
            }
        )
    summary = response.get("summary") or {}
    report_summary = [
        {"value": flt(summary.get("current_qty")), "label": "Current Qty", "datatype": "Float"},
        {"value": flt(summary.get("net_sold_qty")), "label": "Net Sold", "datatype": "Float"},
        {"value": flt(summary.get("net_revenue")), "label": "Net Revenue", "datatype": "Currency"},
        {"value": flt(summary.get("net_profit")), "label": "Net Profit", "datatype": "Currency"},
    ]
    return get_columns(), rows, None, None, report_summary


def get_columns():
    return [
        {"label": "Date", "fieldname": "posting_date", "fieldtype": "Datetime", "width": 155},
        {"label": "Event", "fieldname": "event_type", "fieldtype": "Data", "width": 100},
        {"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Item", "width": 155},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 175},
        {"label": "Reference Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 135},
        {"label": "Reference", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 150},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": "Running Qty", "fieldname": "running_qty", "fieldtype": "Float", "width": 105},
        {"label": "Valuation Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 115},
        {"label": "Batch", "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 120},
        {"label": "Serial", "fieldname": "serial_no", "fieldtype": "Data", "width": 140},
    ]
