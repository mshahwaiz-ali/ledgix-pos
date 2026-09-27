from __future__ import annotations

import json
import traceback

import frappe
from frappe.utils import flt, nowdate

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


def _case_checkout_discount():
    client_id = "LEDGIX-P6-V1-CHECKOUT-DISCOUNT"
    native_customer = erpnext_selling._resolve_customer(CUSTOMER)
    base = erpnext_selling._native_item_rate(
        item_code=ITEM,
        customer=native_customer,
        company=TEST_COMPANY,
        price_list=PRICE_LIST,
        qty=1,
        posting_date=nowdate(),
    )
    base_rate = flt(base.rate)
    expected_net = _money(base_rate * 0.90)
    before_legacy = frappe.db.count("Ledgix Sale") if frappe.db.exists("DocType", "Ledgix Sale") else 0

    result = selling_compat.complete_b2b_sale(
        customer=CUSTOMER,
        cart_items=[{"item": ITEM, "qty": 1}],
        tenders=[],
        price_list=PRICE_LIST,
        client_sale_id=client_id,
        discount_type="Percent",
        discount_value=10,
    )
    invoice_name = selling_compat._invoice_from_result(result)
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    after_legacy = frappe.db.count("Ledgix Sale") if frappe.db.exists("DocType", "Ledgix Sale") else 0

    evidence = {
        "invoice": invoice.name,
        "base_native_rate": _money(base_rate),
        "expected_net_total": expected_net,
        "invoice_line_rate": _money(invoice.items[0].rate),
        "invoice_net_total": _money(invoice.net_total),
        "legacy_sale_count_before": before_legacy,
        "legacy_sale_count_after": after_legacy,
    }
    checks = {
        "native_invoice_submitted": invoice.docstatus == 1,
        "ten_percent_discount_applied": abs(_money(invoice.net_total) - expected_net) < 0.01,
        "discounted_line_rate_matches": abs(_money(invoice.items[0].rate) - expected_net) < 0.01,
        "no_parallel_ledgix_sale": before_legacy == after_legacy,
    }
    return evidence, checks


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
                "type": "General",
            }
        )

    mode.type = "General"
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


def _case_checkout_retry_recovery():
    client_id = "LEDGIX-P6-V1-INTERRUPTED-CHECKOUT"
    payment_id = f"{client_id}:PAY:1"
    invoice = _invoice(client_id)
    invoice.reload()
    original_outstanding = _money(invoice.outstanding_amount)
    preexisting = frappe.db.get_value(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": payment_id,
            "docstatus": ["!=", 2],
        },
        "name",
    )

    tender = [{"payment_method": "Cash", "amount": 300}]
    first_retry = selling_compat.complete_b2b_sale(
        customer=CUSTOMER,
        cart_items=[{"item": ITEM, "qty": 1}],
        tenders=tender,
        price_list=PRICE_LIST,
        client_sale_id=client_id,
    )
    first_payment = frappe.db.get_value(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": payment_id,
            "docstatus": ["!=", 2],
        },
        "name",
    )
    first_count = frappe.db.count(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": payment_id,
            "docstatus": ["!=", 2],
        },
    )
    invoice.reload()
    outstanding_after_first = _money(invoice.outstanding_amount)

    second_retry = selling_compat.complete_b2b_sale(
        customer=CUSTOMER,
        cart_items=[{"item": ITEM, "qty": 1}],
        tenders=tender,
        price_list=PRICE_LIST,
        client_sale_id=client_id,
    )
    second_payment = frappe.db.get_value(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": payment_id,
            "docstatus": ["!=", 2],
        },
        "name",
    )
    second_count = frappe.db.count(
        "Payment Entry",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_payment_id": payment_id,
            "docstatus": ["!=", 2],
        },
    )

    evidence = {
        "invoice": invoice.name,
        "payment_client_id": payment_id,
        "preexisting_payment": preexisting or "",
        "first_retry_payment": first_payment or "",
        "second_retry_payment": second_payment or "",
        "first_retry_response_payments": first_retry.get("payments") or [],
        "second_retry_response_payments": second_retry.get("payments") or [],
        "original_outstanding": original_outstanding,
        "outstanding_after_first": outstanding_after_first,
        "active_payment_count_after_first": first_count,
        "active_payment_count_after_second": second_count,
    }
    checks = {
        "invoice_reused": selling_compat._invoice_from_result(first_retry) == invoice.name,
        "missing_payment_recovered": bool(first_payment),
        "outstanding_reduced": outstanding_after_first < original_outstanding or bool(preexisting),
        "one_active_payment_after_first": first_count == 1,
        "second_retry_reuses_same_payment": second_payment == first_payment,
        "one_active_payment_after_second": second_count == 1,
        "first_response_reports_payment": first_payment in (first_retry.get("payments") or []),
        "second_response_reports_payment": second_payment in (second_retry.get("payments") or []),
    }
    return evidence, checks


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
        "checkout_discount": _case("checkout_discount", _case_checkout_discount),
        "manual_price_override_audit": _case(
            "manual_price_override_audit", _case_override_audit
        ),
        "interrupted_checkout_payment_recovery": _case(
            "interrupted_checkout_payment_recovery", _case_checkout_retry_recovery
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
