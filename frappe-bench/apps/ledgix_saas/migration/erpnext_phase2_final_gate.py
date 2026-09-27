from __future__ import annotations

from collections import OrderedDict
import traceback

import frappe

from ledgix_saas.migration.erpnext_behavioral_batch import run as run_core_batch
from ledgix_saas.migration.erpnext_behavioral_preflight import run as run_preflight
from ledgix_saas.migration.erpnext_finance_pricing_behavioral_spike import run as run_finance_pricing
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.migration.erpnext_pos_draft_behavioral_spike import run as run_pos_draft
from ledgix_saas.migration.erpnext_stock_tracking_behavioral_spike import run as run_stock_tracking
from ledgix_saas.migration.erpnext_tax_architecture_probe import run as run_tax_architecture


BATCH_USER = "Administrator"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 2 final gate on {frappe.local.site!r}; "
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
        trace = traceback.format_exc().strip().splitlines()
        frappe.db.rollback()
        if hasattr(frappe.local, "message_log"):
            frappe.local.message_log = []
        return {
            "name": name,
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": trace[-12:],
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
    """Run the complete Phase 2 capability/gap evidence gate.

    This remains an integration-site-only proof harness. It does not switch any
    production or Ledgix authority. A green result means Phase 3 extension
    schema work can begin with evidence-backed ownership decisions.
    """

    _assert_safe_site()
    frappe.set_user(BATCH_USER)

    preflight = run_preflight()
    if not preflight.get("ready_for_sales_invoice_spike"):
        return {
            "site": frappe.local.site,
            "run_as": frappe.session.user,
            "phase2_complete": False,
            "passed": False,
            "failed_steps": ["preflight"],
            "preflight": preflight,
        }

    steps = OrderedDict()
    steps["core_business_engine"] = _run_step("core_business_engine", run_core_batch)

    if steps["core_business_engine"].get("passed"):
        for name, fn in (
            ("finance_pricing_partial_payment_return_print", run_finance_pricing),
            ("stock_entry_reconciliation_serial_batch", run_stock_tracking),
            ("pos_saved_unfinished_draft", run_pos_draft),
            ("tax_architecture_decision", run_tax_architecture),
        ):
            steps[name] = _run_step(name, fn)
    else:
        for name in (
            "finance_pricing_partial_payment_return_print",
            "stock_entry_reconciliation_serial_batch",
            "pos_saved_unfinished_draft",
            "tax_architecture_decision",
        ):
            steps[name] = _blocked_step(name, "core_business_engine")

    failed_steps = [name for name, step in steps.items() if not step.get("passed")]
    blocked_steps = [name for name, step in steps.items() if step.get("blocked")]
    phase2_complete = not failed_steps

    gap_matrix = {
        "standard_masters": {
            "decision": "USE NATIVE",
            "authority": "ERPNext Item/Item Group/Customer/Supplier/UOM/Price List/Item Price",
        },
        "pricing_rules": {
            "decision": "USE NATIVE",
            "authority": "ERPNext Pricing Rule",
            "evidence_step": "finance_pricing_partial_payment_return_print",
        },
        "invoice_fbr_only": {
            "decision": "USE NATIVE",
            "authority": "ERPNext Sales Invoice + Payment Entry",
            "note": "Non-stock item path requires no fake or negative inventory.",
        },
        "receivables_payments": {
            "decision": "USE NATIVE",
            "authority": "ERPNext invoice outstanding + Payment Entry/payment ledger",
            "evidence_step": "finance_pricing_partial_payment_return_print",
        },
        "returns_credit_notes": {
            "decision": "USE NATIVE",
            "authority": "ERPNext return Sales Invoice/Credit Note",
        },
        "purchase_inventory": {
            "decision": "USE NATIVE",
            "authority": "ERPNext Purchase Order/Receipt/Invoice + Stock Ledger",
        },
        "stock_entry_reconciliation": {
            "decision": "USE NATIVE",
            "authority": "ERPNext Stock Entry + Stock Reconciliation",
            "evidence_step": "stock_entry_reconciliation_serial_batch",
        },
        "serial_batch": {
            "decision": "USE NATIVE",
            "authority": "ERPNext Serial No/Batch/Serial and Batch Bundle",
            "evidence_step": "stock_entry_reconciliation_serial_batch",
        },
        "pos_engine": {
            "decision": "KEEP LEDGIX UI OVER NATIVE ENGINE",
            "authority": "ERPNext POS Invoice + POS Opening/Closing + consolidated Sales Invoice",
            "note": "Native engine and split tender are proven; preserve Ledgix UX until UI parity/branding decision.",
        },
        "pos_hold_unfinished": {
            "decision": "KEEP LEDGIX UI OVER NATIVE DRAFT",
            "authority": "ERPNext draft POS Invoice",
            "evidence_step": "pos_saved_unfinished_draft",
        },
        "financial_tax": {
            "decision": "EXTEND NATIVE",
            "authority": "ERPNext tax rows/accounts after Phase 4 parity",
            "note": "No monetary tax authority cutover until the full tax matrix passes.",
        },
        "fbr_compliance": {
            "decision": "CUSTOM REQUIRED",
            "authority": "Ledgix compliance layer sourced from ERPNext transactions",
            "note": "Keep HS/UOM/Sales Type/SRO/scenario metadata, snapshots, submission logs and reconciliation in Ledgix.",
        },
    }

    return {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "installed_apps": frappe.get_installed_apps(),
        "preflight": preflight,
        "steps": steps,
        "gap_matrix": gap_matrix,
        "failed_steps": failed_steps,
        "blocked_steps": blocked_steps,
        "phase2_complete": phase2_complete,
        "phase3_ready": phase2_complete,
        "next_phase": "Phase 3 — Standard Masters and Ledgix Extension Schema" if phase2_complete else None,
        "legacy_ledgix_authority_cutover_performed": False,
        "passed": phase2_complete,
    }
