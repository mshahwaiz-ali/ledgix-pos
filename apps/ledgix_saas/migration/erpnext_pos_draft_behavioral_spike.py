from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.migration import erpnext_pos_behavioral_spike as pos_base
from ledgix_saas.migration import erpnext_pos_behavioral_spike_runtime as pos_runtime
from ledgix_saas.migration.erpnext_integration_bootstrap import CURRENCY, INTEGRATION_SITE, TEST_COMPANY


DRAFT_MARKER = "LEDGIX-ERPNEXT-POS-DRAFT-SPIKE-V1"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext POS draft behavioral spike on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _draft_by_marker():
    name = frappe.db.get_value(
        "POS Invoice",
        {"company": TEST_COMPANY, "remarks": DRAFT_MARKER, "docstatus": 0},
        "name",
    )
    return frappe.get_doc("POS Invoice", name) if name else None


def _gl_count(voucher_no: str) -> int:
    return frappe.db.count(
        "GL Entry",
        {"voucher_type": "POS Invoice", "voucher_no": voucher_no, "is_cancelled": 0},
    )


def _sle_count(voucher_no: str) -> int:
    return frappe.db.count(
        "Stock Ledger Entry",
        {"voucher_type": "POS Invoice", "voucher_no": voucher_no, "is_cancelled": 0},
    )


def _ensure_draft(customer: str, profile: str, warehouse: str):
    existing = _draft_by_marker()
    if existing:
        return existing

    cash_account = pos_runtime._payment_account(pos_base.PRIMARY_MODE, TEST_COMPANY)
    total = flt(pos_base.SELL_RATE * pos_base.POS_QTY, 2)

    invoice = frappe.get_doc(
        {
            "doctype": "POS Invoice",
            "company": TEST_COMPANY,
            "customer": customer,
            "posting_date": nowdate(),
            "currency": CURRENCY,
            "selling_price_list": "Standard Selling",
            "pos_profile": profile,
            "set_warehouse": warehouse,
            "remarks": DRAFT_MARKER,
            "is_pos": 1,
            "items": [
                {
                    "item_code": pos_base.TEST_ITEM,
                    "qty": pos_base.POS_QTY,
                    "uom": "Nos",
                    "rate": pos_base.SELL_RATE,
                    "warehouse": warehouse,
                }
            ],
            "payments": [
                {
                    "mode_of_payment": pos_base.PRIMARY_MODE,
                    "amount": total,
                    "account": cash_account,
                    "type": pos_runtime._payment_type(pos_base.PRIMARY_MODE),
                    "default": 1,
                }
            ],
        }
    )
    invoice.set_missing_values()
    invoice.insert(ignore_permissions=True)
    invoice.reload()
    return invoice


def run() -> dict:
    """Prove that native POS can persist an unfinished draft without financial/stock posting."""

    _assert_safe_site()
    frappe.set_user(pos_base.POS_USER)

    warehouse = pos_base._leaf_warehouse()
    available_before = pos_base._bin_qty(pos_base.TEST_ITEM, warehouse)
    if available_before < pos_base.POS_QTY:
        frappe.throw(
            f"Insufficient stock for POS draft spike: {available_before} available in {warehouse!r}."
        )

    ledgix_before = pos_base._ledgix_counts()
    customer = pos_base._ensure_customer()
    cash_account = pos_base._ensure_cash_mode_account()
    profile = pos_runtime._ensure_pos_profile(customer, warehouse, cash_account)
    opening = pos_base._ensure_opening(profile)
    draft = _ensure_draft(customer, profile, warehouse)

    draft_name = draft.name
    draft_docstatus = draft.docstatus
    draft_grand_total = flt(draft.grand_total)
    gl_entries = _gl_count(draft.name)
    sle_entries = _sle_count(draft.name)
    available_after_save = pos_base._bin_qty(pos_base.TEST_ITEM, warehouse)
    ledgix_after = pos_base._ledgix_counts()

    evidence = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "warehouse": warehouse,
        "pos_profile": profile,
        "opening_entry": opening.name,
        "opening_status_before_cleanup": opening.status,
        "draft": {
            "name": draft_name,
            "docstatus": draft_docstatus,
            "grand_total": draft_grand_total,
            "gl_entries": gl_entries,
            "stock_ledger_entries": sle_entries,
        },
        "stock": {
            "before": available_before,
            "after_draft_save": available_after_save,
        },
        "parallel_ledgix_guard": {
            "before": ledgix_before,
            "after": ledgix_after,
            "unchanged": ledgix_before == ledgix_after,
        },
    }

    checks = {
        "opening_is_open": opening.docstatus == 1 and opening.status == "Open",
        "draft_persisted": bool(frappe.db.exists("POS Invoice", draft_name)),
        "draft_not_submitted": draft_docstatus == 0,
        "draft_has_total": draft_grand_total > 0,
        "draft_has_no_gl": gl_entries == 0,
        "draft_has_no_stock_ledger": sle_entries == 0,
        "draft_does_not_change_stock": abs(available_after_save - available_before) < 0.005,
        "no_parallel_ledgix_docs_created": evidence["parallel_ledgix_guard"]["unchanged"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())

    # Cleanup only the unfinished draft and its dedicated open shift. The proof
    # is captured above; leaving an open cashier session would interfere with
    # later migration spikes.
    if frappe.db.exists("POS Invoice", draft_name):
        frappe.delete_doc("POS Invoice", draft_name, ignore_permissions=True)
    opening.reload()
    if opening.docstatus == 1 and opening.status == "Open":
        opening.cancel()
    evidence["cleanup"] = {
        "draft_deleted": not bool(frappe.db.exists("POS Invoice", draft_name)),
        "opening_docstatus": frappe.db.get_value("POS Opening Entry", opening.name, "docstatus"),
        "opening_status": frappe.db.get_value("POS Opening Entry", opening.name, "status"),
    }
    evidence["checks"]["cleanup_completed"] = (
        evidence["cleanup"]["draft_deleted"] and evidence["cleanup"]["opening_docstatus"] == 2
    )
    evidence["passed"] = all(evidence["checks"].values())

    frappe.db.commit()
    return evidence
