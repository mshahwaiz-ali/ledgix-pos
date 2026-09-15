from __future__ import annotations

from collections import OrderedDict

import frappe

from ledgix_saas.migration.erpnext_behavioral_preflight import run as run_preflight
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.migration.erpnext_invoice_behavioral_spike import run as run_invoice_spike
from ledgix_saas.migration.erpnext_pos_behavioral_spike_v2 import run as run_pos_spike
from ledgix_saas.migration.erpnext_stock_purchase_behavioral_spike_v2 import (
    run as run_stock_purchase_spike,
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext behavioral batch on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )


def _run_step(name: str, fn) -> dict:
    try:
        result = fn()
        return {
            "name": name,
            "passed": bool(result.get("passed")),
            "result": result,
        }
    except Exception as exc:
        frappe.db.rollback()
        if hasattr(frappe.local, "message_log"):
            frappe.local.message_log = []
        return {
            "name": name,
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def run() -> dict:
    """Run the Phase 2 core ERPNext behavioral batch on the isolated test site.

    The batch proves native ERPNext paths for invoice-only sales, payments and
    credit notes; purchase/inventory and supplier payment; stock sale/return;
    and POS opening, split payment, closing and consolidation. It is designed
    for reruns and never performs a Ledgix authority cutover.
    """

    _assert_safe_site()

    preflight = run_preflight()
    if not preflight.get("ready_for_sales_invoice_spike"):
        return {
            "site": frappe.local.site,
            "installed_apps": frappe.get_installed_apps(),
            "passed": False,
            "preflight": preflight,
            "failed_steps": ["preflight"],
            "message": "ERPNext integration bootstrap is required before the behavioral batch.",
        }

    steps = OrderedDict()
    for name, fn in (
        ("invoice_only", run_invoice_spike),
        ("purchase_stock_sale_return", run_stock_purchase_spike),
        ("pos_split_payment_open_close", run_pos_spike),
    ):
        steps[name] = _run_step(name, fn)

    failed_steps = [name for name, step in steps.items() if not step.get("passed")]

    decisions = {
        "invoice_fbr_only_profile_native_candidate": steps["invoice_only"].get("passed", False),
        "purchase_inventory_native_candidate": steps["purchase_stock_sale_return"].get("passed", False),
        "stock_sale_return_native_candidate": steps["purchase_stock_sale_return"].get("passed", False),
        "supplier_payment_native_candidate": steps["purchase_stock_sale_return"].get("passed", False),
        "pos_open_close_native_candidate": steps["pos_split_payment_open_close"].get("passed", False),
        "split_payment_native_candidate": steps["pos_split_payment_open_close"].get("passed", False),
        "legacy_ledgix_authority_cutover_performed": False,
    }

    return {
        "site": frappe.local.site,
        "installed_apps": frappe.get_installed_apps(),
        "preflight": preflight,
        "schema_note": (
            "ERPNext 15.121.3 POS Invoice intentionally has no update_stock field; "
            "native POS stock/accounting is proven through closing consolidation into Sales Invoice."
        ),
        "steps": steps,
        "decisions": decisions,
        "failed_steps": failed_steps,
        "passed": not failed_steps,
    }
