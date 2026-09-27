"""Compatibility endpoints for the retired custom Reports Center.

Ledgix V2 uses native Frappe Query Reports and Workspace shortcuts. Keeping the
old custom report engine would duplicate reporting logic and, historically,
filtered records by the retired stock mode. These method paths stay importable so
older clients receive an explicit migration target instead of stale calculations.
"""

from __future__ import annotations

import frappe

from ledgix_saas.api.security import require_ledgix_manager_or_above


NATIVE_REPORTS = {
    "sales": "Ledgix Sales Report",
    "returns": "Ledgix Sales Return Report",
    "purchases": "Ledgix Purchase Report",
    "current_stock": "Ledgix Current Stock",
    "low_stock": "Ledgix Low Stock",
    "customer_statement": "Ledgix Customer Statement",
}


def _retired(target=None):
    require_ledgix_manager_or_above()
    target = target or "the relevant native Ledgix Query Report"
    frappe.throw(
        f"The custom Ledgix Reports Center was retired in V2. Use {target} from the Ledgix Workspace."
    )


@frappe.whitelist()
def get_reports_boot_data():
    require_ledgix_manager_or_above()
    return {
        "retired": True,
        "message": "The custom Reports Center was retired. Use native Frappe Query Reports from the Ledgix Workspace.",
        "native_reports": NATIVE_REPORTS,
    }


@frappe.whitelist()
def get_sales_report_data(*args, **kwargs):
    return _retired(NATIVE_REPORTS["sales"])


@frappe.whitelist()
def get_purchase_report_data(*args, **kwargs):
    return _retired(NATIVE_REPORTS["purchases"])


@frappe.whitelist()
def get_return_report_data(*args, **kwargs):
    return _retired(NATIVE_REPORTS["returns"])


@frappe.whitelist()
def get_stock_report_data(*args, **kwargs):
    return _retired(NATIVE_REPORTS["current_stock"])


@frappe.whitelist()
def get_profit_report_data(*args, **kwargs):
    return _retired(NATIVE_REPORTS["sales"])


@frappe.whitelist()
def get_customer_statement(*args, **kwargs):
    return _retired(NATIVE_REPORTS["customer_statement"])


@frappe.whitelist()
def get_supplier_statement(*args, **kwargs):
    return _retired("the Purchases list/report with Supplier filters")


@frappe.whitelist()
def search_report_parties(*args, **kwargs):
    return _retired("native Frappe Link filters for Customer or Supplier")


@frappe.whitelist()
def get_inventory_report_data(*args, **kwargs):
    return _retired(NATIVE_REPORTS["current_stock"])


@frappe.whitelist()
def get_item_full_cycle_report_data(*args, **kwargs):
    return _retired("Inventory Intelligence or the native Stock Movement report")
