from __future__ import annotations

import frappe

from ledgix_saas.migration import erpnext_phase4_tax_parity_gate as base
from ledgix_saas.migration.erpnext_phase4_tax_parity_gate_v2 import _price_only_credit_case
from ledgix_saas.setup import erpnext_tax_foundation as tax_foundation


def _failed_case(name: str, exc: Exception) -> dict:
    trace = frappe.get_traceback().splitlines()
    return {
        "name": name,
        "passed": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback_tail": trace[-12:],
        "checks": {},
        "evidence": {},
    }


def _safe_case(name: str, fn):
    savepoint = "ledgix_p4_" + name.replace("-", "_")
    frappe.db.savepoint(savepoint)
    try:
        return fn()
    except Exception as exc:  # integration gate must report the complete matrix
        frappe.db.rollback(save_point=savepoint)
        frappe.clear_messages()
        return _failed_case(name, exc)


def _safe_return_pair(accounts: dict) -> tuple[dict, dict]:
    savepoint = "ledgix_p4_return_pair"
    frappe.db.savepoint(savepoint)
    try:
        return base._return_cases(accounts)
    except Exception as exc:
        frappe.db.rollback(save_point=savepoint)
        frappe.clear_messages()
        failed = _failed_case("return_pair", exc)
        full = dict(failed)
        partial = dict(failed)
        full["name"] = "full_return"
        partial["name"] = "partial_return"
        return full, partial


def run() -> dict:
    """Run all Phase 4 cases even when one behavioral case fails.

    Fixture/account setup remains fail-fast because every case depends on that
    foundation. Once the foundation exists, each scenario uses a DB savepoint so
    an ERPNext validation error in one scenario cannot hide evidence from the
    remaining matrix.
    """

    base._assert_safe_site()
    frappe.set_user("Administrator")

    sync = tax_foundation.sync_all()
    base._ensure_customer()
    fixture_data = base._ensure_fixture_data()
    accounts = base._ensure_tax_accounts()

    cases = {}
    cases["ordinary_taxable_item"] = _safe_case(
        "ordinary_taxable_item", lambda: base._standard_case(accounts)
    )
    cases["tax_inclusive_price"] = _safe_case(
        "tax_inclusive_price", lambda: base._inclusive_case(accounts)
    )
    cases["zero_rated_item"] = _safe_case(
        "zero_rated_item",
        lambda: base._zero_or_exempt_case(accounts, "zero", "zero_rated_item"),
    )
    cases["exempt_item"] = _safe_case(
        "exempt_item",
        lambda: base._zero_or_exempt_case(accounts, "exempt", "exempt_item"),
    )
    cases["third_schedule_notified_retail_price"] = _safe_case(
        "third_schedule_notified_retail_price", lambda: base._third_schedule_case(accounts)
    )
    cases["further_tax"] = _safe_case(
        "further_tax",
        lambda: base._special_component_case(
            accounts, "further_tax", "further_tax", 50, "further_tax"
        ),
    )
    cases["extra_tax"] = _safe_case(
        "extra_tax",
        lambda: base._special_component_case(accounts, "extra_tax", "extra_tax", 25, "extra_tax"),
    )
    cases["fed"] = _safe_case(
        "fed",
        lambda: base._special_component_case(accounts, "fed", "fed_payable", 30, "fed"),
    )
    cases["sales_tax_withheld_at_source"] = _safe_case(
        "sales_tax_withheld_at_source", lambda: base._withheld_case(accounts)
    )
    cases["mixed_tax_invoice"] = _safe_case(
        "mixed_tax_invoice", lambda: base._mixed_case(accounts)
    )

    full_return, partial_return = _safe_return_pair(accounts)
    cases["full_return"] = full_return
    cases["partial_return"] = partial_return

    cases["price_only_credit_note"] = _safe_case(
        "price_only_credit_note", lambda: _price_only_credit_case(accounts)
    )

    foundation = base._foundation_contract(accounts)
    matrix_passed = all(case.get("passed") for case in cases.values())
    foundation_passed = all((foundation.get("checks") or {}).values())
    failed_cases = [name for name, case in cases.items() if not case.get("passed")]

    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": base.TEST_COMPANY,
        "sync": sync,
        "fixture_data": fixture_data,
        "foundation": foundation,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed_cases,
        "decisions": {
            "erpnext_owns_invoice_totals": True,
            "erpnext_owns_tax_gl": True,
            "ordinary_sales_tax": "ERPNext Sales Taxes and Charges row",
            "extra_tax": "ERPNext Sales Taxes and Charges row",
            "further_tax": "ERPNext Sales Taxes and Charges row",
            "fed": "ERPNext Sales Taxes and Charges row",
            "sales_tax_withheld_at_source": (
                "Ledgix immutable/FBR snapshot only in Phase 4; excluded from invoice payable and not blindly mapped to ERPNext supplier TDS"
            ),
            "third_schedule": (
                "Ledgix legal tax-basis metadata -> ERPNext tax row -> ERPNext totals/GL"
            ),
            "fbr_payload_source_cutover_performed": False,
            "legacy_ledgix_tax_engine_retired": False,
            "network_fbr_submission_performed": False,
        },
        "phase4_complete": bool(matrix_passed and foundation_passed and len(cases) == 13),
        "phase5_ready": bool(matrix_passed and foundation_passed and len(cases) == 13),
        "next_phase": "Phase 5 — Master Data Migration",
        "passed": bool(matrix_passed and foundation_passed and len(cases) == 13),
    }
    frappe.db.commit()
    return result
