from __future__ import annotations

from collections import OrderedDict
import traceback

import frappe

from ledgix_saas.migration.erpnext_behavioral_preflight import run as run_preflight
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.migration.erpnext_invoice_behavioral_spike import run as run_invoice_spike
from ledgix_saas.migration.erpnext_pos_behavioral_spike_v2 import run as run_pos_spike
from ledgix_saas.migration.erpnext_stock_purchase_behavioral_spike_v2 import (
    run as run_stock_purchase_spike,
)


BATCH_USER = "Administrator"
TRACEBACK_TAIL_LINES = 12


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
        trace_lines = traceback.format_exc().strip().splitlines()
        frappe.db.rollback()
        if hasattr(frappe.local, "message_log"):
            frappe.local.message_log = []
        return {
            "name": name,
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": trace_lines[-TRACEBACK_TAIL_LINES:],
        }


def _blocked_step(name: str, blocked_by: str) -> dict:
    return {
        "name": name,
        "passed": False,
        "blocked": True,
        "blocked_by": blocked_by,
        "error_type": "DependencyBlocked",
        "error": f"Skipped because prerequisite step {blocked_by!r} did not pass.",
    }


def run() -> dict:
    """Run the Phase 2 core ERPNext behavioral batch on the isolated test site.

    The batch proves native ERPNext paths for invoice-only sales, payments and
    credit notes; purchase/inventory and supplier payment; stock sale/return;
    and POS opening, split payment, closing and consolidation. It is designed
    for reruns and never performs a Ledgix authority cutover.
    """

    _assert_safe_site()

    # `bench execute` initializes Frappe with Guest as the session user. Native
    # POS closing validates that the POS Invoice owner matches the cashier, so
    # the isolated integration batch explicitly runs its test documents as the
    # Administrator cashier used by the POS profile/opening entry.
    frappe.set_user(BATCH_USER)

    preflight = run_preflight()
    if not preflight.get("ready_for_sales_invoice_spike"):
        return {
            "site": frappe.local.site,
            "run_as": frappe.session.user,
            "installed_apps": frappe.get_installed_apps(),
            "passed": False,
            "preflight": preflight,
            "failed_steps": ["preflight"],
            "message": "ERPNext integration bootstrap is required before the behavioral batch.",
        }

    steps = OrderedDict()
    steps["invoice_only"] = _run_step("invoice_only", run_invoice_spike)
    steps["purchase_stock_sale_return"] = _run_step(
        "purchase_stock_sale_return", run_stock_purchase_spike
    )

    if steps["purchase_stock_sale_return"].get("passed"):
        steps["pos_split_payment_open_close"] = _run_step(
            "pos_split_payment_open_close", run_pos_spike
        )
    else:
        steps["pos_split_payment_open_close"] = _blocked_step(
            "pos_split_payment_open_close", "purchase_stock_sale_return"
        )

    failed_steps = [name for name, step in steps.items() if not step.get("passed")]
    blocked_steps = [name for name, step in steps.items() if step.get("blocked")]

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
        "run_as": frappe.session.user,
        "installed_apps": frappe.get_installed_apps(),
        "preflight": preflight,
        "schema_note": (
            "ERPNext 15.121.3 POS Invoice intentionally has no update_stock field; "
            "native POS stock/accounting is proven through closing consolidation into Sales Invoice."
        ),
        "steps": steps,
        "decisions": decisions,
        "failed_steps": failed_steps,
        "blocked_steps": blocked_steps,
        "passed": not failed_steps,
    }
