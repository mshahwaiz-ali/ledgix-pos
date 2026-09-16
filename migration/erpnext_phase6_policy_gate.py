from __future__ import annotations

import json
import traceback

import frappe
from frappe.utils import flt

from ledgix_saas.api import selling_compat
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.services import erpnext_selling

CUSTOMER = "P6-Customer"
ITEM = "P6-ITEM"
PRICE_LIST = "P6-Selling"
REFERENCE_MODE = "P6 Reference Payment"
TRACEBACK_TAIL = 10


def _money(value) -> float:
    return flt(value, 2)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 6 policy gate on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration Company {TEST_COMPANY!r} is missing.")
    for doctype, name in (
        ("Customer", CUSTOMER),
        ("Item", ITEM),
        ("Price List", PRICE_LIST),
    ):
        if not frappe.db.exists(doctype, name):
            frappe.throw(
                f"Phase 6 core gate fixture {doctype} {name!r} is missing. "
                "Run erpnext_phase6_selling_gate before the policy gate."
            )


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        result = {
            "name": name,
            "evidence": evidence,
            "checks": checks,
            "passed": all(checks.values()),
        }
        frappe.db.commit()
        return result
    except Exception as exc:
        trace = traceback.format_exc().strip().splitlines()
        frappe.db.rollback()
        if hasattr(frappe.local, "message_log"):
            frappe.local.message_log = []
        return {
            "name": name,
            "evidence": {},
            "checks": {},
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": trace[-TRACEBACK_TAIL:],
        }


def _case_override_audit():
    client_id = "LEDGIX-P6-V1-OVERRIDE-AUDIT"
    reason = "Phase 6 authorized manager override"
    before_legacy = frappe.db.count("Ledgix Sale") if frappe.db.exists("DocType", "Ledgix Sale") else 0

    first = selling_compat.complete_b2b_sale(
        customer=CUSTOMER,
        cart_items=[
            {
                "item": ITEM,
                "qty": 1,
                "override_rate": 875,
                "override_reason": reason,
            }
        ],
        tenders=[],
        price_list=PRICE_LIST,
        client_sale_id=client_id,
    )
    invoice_name = selling_compat._invoice_from_result(first)
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    raw = invoice.get("custom_ledgix_price_override_json") or ""
    audit = json.loads(raw) if raw else []

    second = selling_compat.complete_b2b_sale(
        customer=CUSTOMER,
        cart_items=[
            {
                "item": ITEM,
                "qty": 1,
                "override_rate": 825,
                "override_reason": "Idempotent retry must not replace original audit",
            }
        ],
        tenders=[],
        price_list=PRICE_LIST,
        client_sale_id=client_id,
    )
    retry_name = selling_compat._invoice_from_result(second)
    invoice.reload()
    raw_after_retry = invoice.get("custom_ledgix_price_override_json") or ""
    after_legacy = frappe.db.count("Ledgix Sale") if frappe.db.exists("DocType", "Ledgix Sale") else 0

    first_row = audit[0] if audit else {}
    evidence = {
        "invoice": invoice.name,
        "invoice_rate": _money(invoice.items[0].rate),
        "audit": audit,
        "retry_invoice": retry_name,
        "audit_unchanged_after_retry": raw == raw_after_retry,
        "legacy_sale_count_before": before_legacy,
        "legacy_sale_count_after": after_legacy,
    }
    checks = {
        "native_invoice_created": bool(invoice.name and invoice.docstatus == 1),
        "override_rate_is_native_invoice_rate": abs(_money(invoice.items[0].rate) - 875.0) < 0.01,
        "audit_reason_preserved": first_row.get("reason") == reason,
        "audit_rate_preserved": abs(flt(first_row.get("override_rate")) - 875.0) < 0.0001,
        "audit_item_preserved": first_row.get("item") == ITEM,
        "idempotent_retry_same_invoice": retry_name == invoice.name,
        "idempotent_retry_did_not_rewrite_audit": raw == raw_after_retry,
        "no_parallel_ledgix_sale": before_legacy == after_legacy,
    }
    return evidence, checks


def _cash_account() -> str:
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": "Cash", "company": TEST_COMPANY},
        "default_account",
    )
    if not account:
        frappe.throw(
            f"Cash has no Mode of Payment Account for {TEST_COMPANY}; "
            "the Phase 2 payment baseline is required."
        )
    return account


def _ensure_reference_mode() -> str:
    account = _cash_account()
    if frappe.db.exists("Mode of Payment", REFERENCE_MODE):
        mode = frappe.get_doc("Mode of Payment", REFERENCE_MODE)
    else:
        mode = frappe.get_doc(
            {
                "doctype": "Mode of Payment",
                "mode_of_payment": REFERENCE_MODE,
                "type": "Bank",
            }
        )

    if mode.meta.has_field("enabled"):
        mode.enabled = 1
    mode.custom_ledgix_legacy_payment_method = "P6-REFERENCE-POLICY"
    mode.custom_ledgix_legacy_method_type = "Card"
    mode.custom_ledgix_requires_reference = 1
    mode.custom_ledgix_allow_change = 0

    found = False
    for row in mode.get("accounts") or []:
        if row.company == TEST_COMPANY:
            row.default_account = account
            found = True
            break
    if not found:
        mode.append(
            "accounts",
            {"company": TEST_COMPANY, "default_account": account},
        )

    if mode.is_new():
        mode.insert(ignore_permissions=True)
    else:
        mode.save(ignore_permissions=True)
    return mode.name


def _invoice(client_id: str):
    return erpnext_selling.create_sales_invoice(
        customer=CUSTOMER,
        items=[{"item_code": ITEM, "qty": 1, "uom": "Nos"}],
        company=TEST_COMPANY,
        selling_price_list=PRICE_LIST,
        sale_channel="B2B",
        client_sale_id=client_id,
        checkout_source="Phase 6 Policy Gate",
        submit=True,
    )


def _case_payment_reference_policy():
    mode = _ensure_reference_mode()
    negative_invoice = _invoice("LEDGIX-P6-V1-POLICY-NEGATIVE")
    positive_invoice = _invoice("LEDGIX-P6-V1-POLICY-POSITIVE")
    frappe.db.commit()

    missing_reference_blocked = False
    missing_reference_error = ""
    try:
        erpnext_selling.post_customer_payment(
            customer=CUSTOMER,
            mode_of_payment=mode,
            amount=100,
            allocations=[
                {
                    "reference_name": negative_invoice.name,
                    "allocated_amount": 100,
                }
            ],
            company=TEST_COMPANY,
            client_payment_id="LEDGIX-P6-V1-POLICY-NO-REFERENCE",
            payment_source="Phase 6 Reference Policy Negative Proof",
        )
    except Exception as exc:
        missing_reference_error = str(exc)
        missing_reference_blocked = "Reference number is required" in missing_reference_error
        frappe.db.rollback()
        if hasattr(frappe.local, "message_log"):
            frappe.local.message_log = []

    payment_id = "LEDGIX-P6-V1-POLICY-WITH-REFERENCE"
    payment_name = frappe.db.get_value(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": payment_id,
            "docstatus": ["!=", 2],
        },
        "name",
    )
    if payment_name:
        payment = frappe.get_doc("Payment Entry", payment_name)
    else:
        positive_invoice.reload()
        allocation = min(250.0, max(flt(positive_invoice.outstanding_amount), 0))
        if allocation <= 0:
            frappe.throw("Positive policy invoice has no outstanding amount for payment proof.")
        payment = erpnext_selling.post_customer_payment(
            customer=CUSTOMER,
            mode_of_payment=mode,
            amount=allocation,
            allocations=[
                {
                    "reference_name": positive_invoice.name,
                    "allocated_amount": allocation,
                }
            ],
            company=TEST_COMPANY,
            client_payment_id=payment_id,
            reference_number="P6-REF-001",
            payment_source="Phase 6 Reference Policy Positive Proof",
        )

    no_reference_count = frappe.db.count(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": "LEDGIX-P6-V1-POLICY-NO-REFERENCE",
            "docstatus": ["!=", 2],
        },
    )
    evidence = {
        "mode_of_payment": mode,
        "missing_reference_blocked": missing_reference_blocked,
        "missing_reference_error": missing_reference_error,
        "failed_payment_rows": no_reference_count,
        "successful_payment": payment.name,
        "successful_reference": payment.reference_no,
        "successful_docstatus": payment.docstatus,
    }
    checks = {
        "missing_reference_rejected": missing_reference_blocked,
        "failed_attempt_not_persisted": no_reference_count == 0,
        "reference_payment_submitted": payment.docstatus == 1,
        "reference_preserved": payment.reference_no == "P6-REF-001",
        "mode_preserved": payment.mode_of_payment == mode,
    }
    return evidence, checks


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")

    cases = {
        "manual_price_override_audit": _case(
            "manual_price_override_audit", _case_override_audit
        ),
        "mode_of_payment_reference_policy": _case(
            "mode_of_payment_reference_policy", _case_payment_reference_policy
        ),
    }
    failed = [name for name, case in cases.items() if not case.get("passed")]
    complete = not failed
    result = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "cases": cases,
        "failed_cases": failed,
        "phase6_policy_complete": complete,
        "passed": complete,
    }
    frappe.db.commit()
    return result
