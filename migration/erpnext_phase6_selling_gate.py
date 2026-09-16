from __future__ import annotations

import json
import traceback

import frappe
from frappe.utils import cint, flt, nowdate

from ledgix_saas.api import selling as selling_api
from ledgix_saas.migration.erpnext_integration_bootstrap import (
    CURRENCY,
    INTEGRATION_SITE,
    TEST_COMPANY,
)
from ledgix_saas.services import erpnext_selling
from ledgix_saas.setup import (
    erpnext_phase6_extensions,
    erpnext_tax_foundation,
)

GATE_VERSION = "P6-V1"
CUSTOMER = "P6-Customer"
PRICE_LIST = "P6-Selling"
ITEM = "P6-ITEM"
EXCHANGE_ITEM = "P6-EXCHANGE"
TAX_CATEGORY = "P6-Standard-18"
MODE_OF_PAYMENT = "Cash"
TRACEBACK_TAIL = 10


def _money(value) -> float:
    return flt(value, 2)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 6 selling gate on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration Company {TEST_COMPANY!r} is missing.")


def _legacy_counts() -> dict:
    return {
        doctype: frappe.db.count(doctype)
        for doctype in ("Ledgix Sale", "Ledgix Payment", "Ledgix Sales Return")
        if frappe.db.exists("DocType", doctype)
    }


def _ensure_customer() -> str:
    if frappe.db.exists("Customer", CUSTOMER):
        customer = frappe.get_doc("Customer", CUSTOMER)
    else:
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": CUSTOMER,
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": "Pakistan",
            }
        )
    customer.custom_ledgix_buyer_registration_type = "Registered"
    customer.custom_ledgix_buyer_ntn_cnic = "1234567-8"
    customer.custom_ledgix_buyer_province = "Sindh"
    customer.custom_ledgix_buyer_fbr_address = "Phase 6 ERPNext native customer"
    customer.set(
        "credit_limits",
        [{"company": TEST_COMPANY, "credit_limit": 100000}],
    )
    if customer.is_new():
        customer.insert(ignore_permissions=True)
    else:
        customer.save(ignore_permissions=True)
    return customer.name


def _ensure_price_list() -> str:
    if frappe.db.exists("Price List", PRICE_LIST):
        doc = frappe.get_doc("Price List", PRICE_LIST)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Price List",
                "price_list_name": PRICE_LIST,
                "currency": CURRENCY,
            }
        )
    doc.enabled = 1
    doc.selling = 1
    doc.buying = 0
    doc.currency = CURRENCY
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_item(item_code: str) -> str:
    if frappe.db.exists("Item", item_code):
        doc = frappe.get_doc("Item", item_code)
        if cint(doc.is_stock_item):
            frappe.throw(f"Phase 6 gate item {item_code} must remain non-stock.")
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_code.replace("P6-", "Phase 6 ").replace("-", " ").title(),
                "description": f"Phase 6 ERPNext-only selling fixture {item_code}",
                "item_group": "Services",
                "stock_uom": "Nos",
                "is_stock_item": 0,
            }
        )
        doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item_price(item_code: str, rate: float) -> str:
    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": PRICE_LIST,
            "uom": "Nos",
        },
        fields=["name"],
        order_by="creation asc",
        limit_page_length=1,
    )
    if rows:
        doc = frappe.get_doc("Item Price", rows[0].name)
    else:
        doc = frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": PRICE_LIST,
                "uom": "Nos",
                "selling": 1,
                "buying": 0,
                "valid_from": nowdate(),
            }
        )
    doc.price_list_rate = rate
    doc.selling = 1
    doc.buying = 0
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_tax_category() -> str:
    if frappe.db.exists("Ledgix Tax Category", TAX_CATEGORY):
        doc = frappe.get_doc("Ledgix Tax Category", TAX_CATEGORY)
    else:
        doc = frappe.get_doc(
            {"doctype": "Ledgix Tax Category", "category_name": TAX_CATEGORY}
        )
    doc.tax_type = "Sales Tax"
    doc.default_rate = 18
    doc.active = 1
    doc.is_exempt = 0
    doc.is_zero_rated = 0
    doc.description = "Phase 6 native selling standard tax"
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_item_tax_profile(item_code: str) -> str:
    name = frappe.db.get_value(
        "Ledgix Item Tax Profile",
        {"erpnext_item": item_code},
        "name",
    )
    if name:
        doc = frappe.get_doc("Ledgix Item Tax Profile", name)
    else:
        doc = frappe.get_doc(
            {"doctype": "Ledgix Item Tax Profile", "erpnext_item": item_code}
        )
    values = {
        "erpnext_item": item_code,
        "item": None,
        "tax_category": TAX_CATEGORY,
        "taxable": 1,
        "active": 1,
        "needs_review": 0,
        "tax_basis": "Transaction Value",
        "notified_retail_price": 0,
        "hs_code": "0101.21",
        "uom_for_fbr": "Numbers, pieces, units",
        "sales_type": "Goods at standard rate",
        "fbr_rate_description": "18%",
        "scenario_id": "SN001",
        "sro_schedule_number": "",
        "sro_item_serial_number": "",
        "sales_tax_withheld_at_source_per_unit": 0,
        "extra_tax_per_unit": 0,
        "further_tax_per_unit": 0,
        "fed_payable_per_unit": 0,
    }
    for fieldname, value in values.items():
        doc.set(fieldname, value)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return doc.name


def _ensure_mode_account() -> str:
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": MODE_OF_PAYMENT, "company": TEST_COMPANY},
        "default_account",
    )
    if not account:
        frappe.throw(
            f"{MODE_OF_PAYMENT} has no Mode of Payment Account for {TEST_COMPANY}. "
            "Phase 2 bootstrap/payment evidence must remain available."
        )
    return account


def _ensure_fixtures() -> dict:
    erpnext_phase6_extensions.sync_all()
    erpnext_tax_foundation.sync_all()
    customer = _ensure_customer()
    price_list = _ensure_price_list()
    _ensure_tax_category()
    items = {}
    prices = {}
    profiles = {}
    for item_code in (ITEM, EXCHANGE_ITEM):
        items[item_code] = _ensure_item(item_code)
        prices[item_code] = _ensure_item_price(item_code, 1000)
        profiles[item_code] = _ensure_item_tax_profile(item_code)
    cash_account = _ensure_mode_account()
    frappe.db.commit()
    return {
        "customer": customer,
        "price_list": price_list,
        "items": items,
        "prices": prices,
        "profiles": profiles,
        "mode_of_payment": MODE_OF_PAYMENT,
        "cash_account": cash_account,
    }


def _client(kind: str) -> str:
    return f"LEDGIX-{GATE_VERSION}-{kind.upper().replace('_', '-')}"


def _invoice(kind: str, *, qty: float = 1, item_code: str = ITEM):
    return erpnext_selling.create_sales_invoice(
        customer=CUSTOMER,
        items=[{"item_code": item_code, "qty": qty, "uom": "Nos"}],
        company=TEST_COMPANY,
        selling_price_list=PRICE_LIST,
        sale_channel="B2B",
        client_sale_id=_client(kind),
        checkout_source="Phase 6 Final Gate",
        submit=True,
    )


def _payment(kind: str, invoice, amount: float):
    return erpnext_selling.post_customer_payment(
        customer=CUSTOMER,
        mode_of_payment=MODE_OF_PAYMENT,
        amount=amount,
        allocations=[
            {
                "reference_name": invoice.name,
                "allocated_amount": amount,
            }
        ],
        company=TEST_COMPANY,
        client_payment_id=_client(f"payment_{kind}"),
        payment_source="Phase 6 Final Gate",
    )


def _gl_balanced(voucher_type: str, voucher_no: str) -> bool:
    rows = frappe.get_all(
        "GL Entry",
        filters={
            "voucher_type": voucher_type,
            "voucher_no": voucher_no,
            "is_cancelled": 0,
        },
        fields=["debit", "credit"],
        limit_page_length=0,
    )
    return abs(sum(flt(row.debit) - flt(row.credit) for row in rows)) < 0.01


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


def _case_idempotency():
    first = _invoice("idempotent_sale")
    second = _invoice("idempotent_sale")
    count = frappe.db.count(
        "Sales Invoice",
        {
            "company": TEST_COMPANY,
            "custom_ledgix_client_sale_id": _client("idempotent_sale"),
            "docstatus": ["!=", 2],
        },
    )
    evidence = {"first": first.name, "second": second.name, "count": count}
    checks = {
        "same_invoice_returned": first.name == second.name,
        "one_active_document": count == 1,
        "duplicate_flag_returned": bool(
            getattr(second.flags, "ledgix_duplicate_client_sale", False)
        ),
    }
    return evidence, checks


def _case_fully_paid():
    invoice = _invoice("fully_paid")
    invoice.reload()
    if flt(invoice.outstanding_amount) > 0.005:
        payment = _payment("fully_paid", invoice, _money(invoice.outstanding_amount))
    else:
        payment_name = frappe.db.get_value(
            "Payment Entry",
            {"custom_ledgix_client_payment_id": _client("payment_fully_paid")},
            "name",
        )
        payment = frappe.get_doc("Payment Entry", payment_name)
    invoice.reload()
    evidence = {
        "invoice": invoice.name,
        "payment": payment.name,
        "grand_total": _money(invoice.grand_total),
        "outstanding": _money(invoice.outstanding_amount),
        "payment_docstatus": payment.docstatus,
    }
    checks = {
        "invoice_submitted": invoice.docstatus == 1,
        "payment_submitted": payment.docstatus == 1,
        "invoice_fully_paid": abs(flt(invoice.outstanding_amount)) < 0.01,
        "invoice_gl_balanced": _gl_balanced("Sales Invoice", invoice.name),
        "payment_gl_balanced": _gl_balanced("Payment Entry", payment.name),
    }
    return evidence, checks


def _case_partially_paid():
    invoice = _invoice("partial", qty=2)
    invoice.reload()
    payment_name = frappe.db.get_value(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": _client("payment_partial")},
        "name",
    )
    if payment_name:
        payment = frappe.get_doc("Payment Entry", payment_name)
    else:
        payment = _payment("partial", invoice, 1000)
    invoice.reload()
    expected = _money(invoice.grand_total - 1000)
    evidence = {
        "invoice": invoice.name,
        "payment": payment.name,
        "grand_total": _money(invoice.grand_total),
        "outstanding": _money(invoice.outstanding_amount),
        "expected_outstanding": expected,
    }
    checks = {
        "payment_submitted": payment.docstatus == 1,
        "partial_outstanding_preserved": abs(_money(invoice.outstanding_amount) - expected) < 0.01,
        "outstanding_positive": flt(invoice.outstanding_amount) > 0,
    }
    return evidence, checks


def _case_unpaid_credit():
    invoice = _invoice("unpaid_credit")
    invoice.reload()
    credit = erpnext_selling.get_customer_receivables(CUSTOMER, company=TEST_COMPANY)
    open_names = {row["invoice"] for row in credit.get("invoices") or []}
    evidence = {
        "invoice": invoice.name,
        "outstanding": _money(invoice.outstanding_amount),
        "credit_limit": _money(credit["credit_limit"]),
        "available_credit": _money(credit["available_credit"]),
        "authority": credit["authority"],
    }
    checks = {
        "invoice_unpaid": abs(_money(invoice.outstanding_amount) - _money(invoice.grand_total)) < 0.01,
        "invoice_in_native_ar_view": invoice.name in open_names,
        "native_authority_marker": credit["authority"] == "ERPNext Sales Invoice + Payment Entry",
        "credit_limit_reduced": flt(credit["available_credit"]) < flt(credit["credit_limit"]),
    }
    return evidence, checks


def _case_multi_allocation():
    first = _invoice("multi_a")
    second = _invoice("multi_b")
    payment_name = frappe.db.get_value(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": _client("payment_multi")},
        "name",
    )
    if payment_name:
        payment = frappe.get_doc("Payment Entry", payment_name)
    else:
        payment = erpnext_selling.post_customer_payment(
            customer=CUSTOMER,
            mode_of_payment=MODE_OF_PAYMENT,
            amount=1500,
            allocations=[
                {"reference_name": first.name, "allocated_amount": 750},
                {"reference_name": second.name, "allocated_amount": 750},
            ],
            company=TEST_COMPANY,
            client_payment_id=_client("payment_multi"),
            payment_source="Phase 6 multi-allocation gate",
        )
    first.reload()
    second.reload()
    refs = [
        (row.reference_name, _money(row.allocated_amount))
        for row in payment.references
        if row.reference_doctype == "Sales Invoice"
    ]
    evidence = {
        "payment": payment.name,
        "references": refs,
        "first_outstanding": _money(first.outstanding_amount),
        "second_outstanding": _money(second.outstanding_amount),
    }
    checks = {
        "one_payment_two_invoices": len(refs) == 2,
        "first_allocation_750": (first.name, 750.0) in refs,
        "second_allocation_750": (second.name, 750.0) in refs,
        "payment_submitted": payment.docstatus == 1,
    }
    return evidence, checks


def _case_payment_idempotency():
    invoice = _invoice("payment_idempotency")
    client_id = _client("payment_idempotency")
    existing = frappe.db.get_value(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": client_id, "docstatus": ["!=", 2]},
        "name",
    )
    if existing:
        first = frappe.get_doc("Payment Entry", existing)
    else:
        first = erpnext_selling.post_customer_payment(
            customer=CUSTOMER,
            mode_of_payment=MODE_OF_PAYMENT,
            amount=500,
            allocations=[{"reference_name": invoice.name, "allocated_amount": 500}],
            company=TEST_COMPANY,
            client_payment_id=client_id,
        )
    second = erpnext_selling.post_customer_payment(
        customer=CUSTOMER,
        mode_of_payment=MODE_OF_PAYMENT,
        amount=500,
        allocations=[{"reference_name": invoice.name, "allocated_amount": 500}],
        company=TEST_COMPANY,
        client_payment_id=client_id,
    )
    count = frappe.db.count(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": client_id, "docstatus": ["!=", 2]},
    )
    evidence = {"first": first.name, "second": second.name, "count": count}
    checks = {
        "same_payment_returned": first.name == second.name,
        "one_active_payment": count == 1,
        "duplicate_flag_returned": bool(
            getattr(second.flags, "ledgix_duplicate_client_payment", False)
        ),
    }
    return evidence, checks


def _case_payment_cancel():
    invoice = _invoice("cancel_payment")
    invoice.reload()
    active = frappe.db.get_value(
        "Payment Entry",
        {
            "custom_ledgix_client_payment_id": _client("payment_cancel_payment"),
            "docstatus": 1,
        },
        "name",
    )
    payment = frappe.get_doc("Payment Entry", active) if active else _payment(
        "cancel_payment", invoice, 600
    )
    if payment.docstatus == 1:
        payment = erpnext_selling.cancel_payment_entry(payment.name, "Phase 6 cancellation proof")
    invoice.reload()
    reason = frappe.db.get_value("Payment Entry", payment.name, "custom_ledgix_reversal_reason")
    evidence = {
        "payment": payment.name,
        "docstatus": payment.docstatus,
        "invoice_outstanding": _money(invoice.outstanding_amount),
        "invoice_grand_total": _money(invoice.grand_total),
        "reason": reason,
    }
    checks = {
        "payment_cancelled": payment.docstatus == 2,
        "outstanding_restored": abs(_money(invoice.outstanding_amount) - _money(invoice.grand_total)) < 0.01,
        "reason_preserved": reason == "Phase 6 cancellation proof",
    }
    return evidence, checks


def _case_full_return():
    source = _invoice("full_return_source")
    note = erpnext_selling.create_sales_return(
        sales_invoice=source.name,
        return_items=[
            {"sales_invoice_item": source.items[0].name, "return_qty": 1}
        ],
        reason="Phase 6 full return",
        client_return_id=_client("full_return"),
    )
    evidence = {
        "source": source.name,
        "credit_note": note.name,
        "return_against": note.return_against,
        "grand_total": _money(note.grand_total),
        "qty": flt(note.items[0].qty),
    }
    checks = {
        "credit_note_submitted": note.docstatus == 1,
        "linked_to_source": note.return_against == source.name,
        "negative_total": flt(note.grand_total) < 0,
        "full_negative_qty": abs(flt(note.items[0].qty) + 1) < 0.001,
        "fbr_snapshot_present": bool(note.items[0].custom_ledgix_fbr_snapshot_json),
    }
    return evidence, checks


def _case_partial_return():
    source = _invoice("partial_return_source", qty=2)
    note = erpnext_selling.create_sales_return(
        sales_invoice=source.name,
        return_items=[
            {"sales_invoice_item": source.items[0].name, "return_qty": 1}
        ],
        reason="Phase 6 partial return",
        client_return_id=_client("partial_return"),
    )
    evidence = {
        "source": source.name,
        "source_qty": flt(source.items[0].qty),
        "credit_note": note.name,
        "return_qty": flt(note.items[0].qty),
        "grand_total": _money(note.grand_total),
    }
    checks = {
        "credit_note_submitted": note.docstatus == 1,
        "linked_to_source": note.return_against == source.name,
        "partial_qty_minus_one": abs(flt(note.items[0].qty) + 1) < 0.001,
        "credit_less_than_source": abs(flt(note.grand_total)) < abs(flt(source.grand_total)),
    }
    return evidence, checks


def _case_refund():
    source = _invoice("refund_source")
    source.reload()
    if flt(source.outstanding_amount) > 0.005:
        _payment("refund_source", source, _money(source.outstanding_amount))
        source.reload()
    note = erpnext_selling.create_sales_return(
        sales_invoice=source.name,
        return_items=[
            {"sales_invoice_item": source.items[0].name, "return_qty": 1}
        ],
        reason="Phase 6 refund return",
        client_return_id=_client("refund_credit"),
    )
    note.reload()
    refund_id = _client("refund_payment")
    active = frappe.db.get_value(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": refund_id, "docstatus": 1},
        "name",
    )
    if active:
        refund = frappe.get_doc("Payment Entry", active)
    else:
        refund = erpnext_selling.refund_credit_note(
            credit_note=note.name,
            mode_of_payment=MODE_OF_PAYMENT,
            client_payment_id=refund_id,
        )
    note.reload()
    allocated = _money(refund.references[0].allocated_amount) if refund.references else 0
    evidence = {
        "source": source.name,
        "credit_note": note.name,
        "refund": refund.name,
        "payment_type": refund.payment_type,
        "credit_outstanding": _money(note.outstanding_amount),
        "reference_allocation": allocated,
    }
    checks = {
        "refund_submitted": refund.docstatus == 1,
        "refund_is_pay": refund.payment_type == "Pay",
        "negative_credit_allocation": allocated < 0,
        "credit_note_settled": abs(flt(note.outstanding_amount)) < 0.01,
    }
    return evidence, checks


def _case_exchange():
    source = _invoice("exchange_source")
    result = erpnext_selling.create_exchange(
        sales_invoice=source.name,
        return_items=[
            {"sales_invoice_item": source.items[0].name, "return_qty": 1}
        ],
        replacement_items=[{"item_code": EXCHANGE_ITEM, "qty": 1, "uom": "Nos"}],
        reason="Phase 6 equal-value exchange",
        exchange_reference=_client("exchange_reference"),
        client_return_id=_client("exchange_return"),
        client_sale_id=_client("exchange_replacement"),
        selling_price_list=PRICE_LIST,
    )
    credit = result["credit_note"]
    replacement = result["replacement_invoice"]
    evidence = {
        "source": source.name,
        "credit_note": credit.name,
        "replacement_invoice": replacement.name,
        "exchange_reference": credit.custom_ledgix_exchange_reference,
        "credit_total": _money(credit.grand_total),
        "replacement_total": _money(replacement.grand_total),
    }
    checks = {
        "credit_note_submitted": credit.docstatus == 1,
        "replacement_submitted": replacement.docstatus == 1,
        "shared_exchange_reference": (
            credit.custom_ledgix_exchange_reference
            == replacement.custom_ledgix_exchange_reference
            == _client("exchange_reference")
        ),
        "equal_value_pair_nets_zero": abs(flt(credit.grand_total) + flt(replacement.grand_total)) < 0.01,
    }
    return evidence, checks


def _case_compatibility_api():
    result = selling_api.complete_b2b_sale(
        customer=CUSTOMER,
        cart_items=[{"item": ITEM, "qty": 1}],
        tenders=[],
        price_list=PRICE_LIST,
        client_sale_id=_client("compat_api"),
    )
    evidence = {
        "invoice": result.get("invoice") or result.get("sale"),
        "authority": result.get("financial_authority"),
        "duplicate": result.get("duplicate"),
    }
    checks = {
        "api_success": bool(result.get("success")),
        "erpnext_authority": result.get("financial_authority") == "ERPNext",
        "native_sales_invoice": bool(frappe.db.exists("Sales Invoice", result.get("sale"))),
    }
    return evidence, checks


def _case_native_receivables():
    credit = erpnext_selling.get_customer_receivables(CUSTOMER, company=TEST_COMPANY)
    evidence = {
        "authority": credit["authority"],
        "outstanding": _money(credit["outstanding"]),
        "invoice_credit": _money(credit["invoice_credit"]),
        "unallocated_credit": _money(credit["unallocated_credit"]),
        "open_invoice_count": len(credit.get("invoices") or []),
        "credit_note_count": len(credit.get("credits") or []),
    }
    checks = {
        "native_authority": credit["authority"] == "ERPNext Sales Invoice + Payment Entry",
        "has_native_open_invoices": len(credit.get("invoices") or []) > 0,
        "values_are_erpnext_derived": "Ledgix" not in credit["authority"],
    }
    return evidence, checks


def _case_no_stock():
    counts = {
        item: frappe.db.count(
            "Stock Ledger Entry", {"item_code": item, "is_cancelled": 0}
        )
        for item in (ITEM, EXCHANGE_ITEM)
    }
    evidence = {"stock_ledger_entries": counts}
    checks = {"no_stock_effect": all(count == 0 for count in counts.values())}
    return evidence, checks


def _case_fbr_snapshots():
    invoice = _invoice("snapshot")
    raw = invoice.items[0].custom_ledgix_fbr_snapshot_json
    snapshot = json.loads(raw) if raw else {}
    evidence = {
        "invoice": invoice.name,
        "profile": snapshot.get("item_profile"),
        "hs_code": snapshot.get("hs_code"),
        "sales_tax": _money(snapshot.get("sales_tax")),
    }
    checks = {
        "snapshot_present": bool(raw),
        "erpnext_item_profile_used": bool(snapshot.get("item_profile")),
        "hs_code_preserved": snapshot.get("hs_code") == "0101.21",
        "sales_tax_present": flt(snapshot.get("sales_tax")) > 0,
    }
    return evidence, checks


def run() -> dict:
    """Prove Phase 6 B2B selling/payment/return authority on ERPNext."""

    _assert_safe_site()
    frappe.set_user("Administrator")
    fixtures = _ensure_fixtures()
    legacy_before = _legacy_counts()

    cases = {
        "b2b_client_idempotency": _case("b2b_client_idempotency", _case_idempotency),
        "fully_paid": _case("fully_paid", _case_fully_paid),
        "partially_paid": _case("partially_paid", _case_partially_paid),
        "unpaid_credit_sale": _case("unpaid_credit_sale", _case_unpaid_credit),
        "multi_invoice_allocation": _case("multi_invoice_allocation", _case_multi_allocation),
        "payment_idempotency": _case("payment_idempotency", _case_payment_idempotency),
        "payment_cancel_reversal": _case("payment_cancel_reversal", _case_payment_cancel),
        "full_credit_note": _case("full_credit_note", _case_full_return),
        "partial_credit_note": _case("partial_credit_note", _case_partial_return),
        "refund": _case("refund", _case_refund),
        "exchange": _case("exchange", _case_exchange),
        "b2b_compatibility_api": _case("b2b_compatibility_api", _case_compatibility_api),
        "native_receivables": _case("native_receivables", _case_native_receivables),
        "no_stock_effect": _case("no_stock_effect", _case_no_stock),
        "fbr_snapshot_preserved": _case("fbr_snapshot_preserved", _case_fbr_snapshots),
    }

    legacy_after = _legacy_counts()
    parallel_check = legacy_before == legacy_after
    cases["no_parallel_ledgix_financial_docs"] = {
        "name": "no_parallel_ledgix_financial_docs",
        "evidence": {"before": legacy_before, "after": legacy_after},
        "checks": {"legacy_financial_counts_unchanged": parallel_check},
        "passed": parallel_check,
    }
    cases["retail_pos_deferred_to_phase8"] = {
        "name": "retail_pos_deferred_to_phase8",
        "evidence": {
            "phase6_scope": "B2B Sales Invoice / Payment Entry / Credit Note",
            "retail_scope": "Legacy retail POS backend intentionally retained until Phase 8",
        },
        "checks": {"retail_cutover_not_claimed": True},
        "passed": True,
    }

    failed = [name for name, case in cases.items() if not case.get("passed")]
    complete = not failed
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "fixtures": fixtures,
        "legacy_counts_before": legacy_before,
        "legacy_counts_after": legacy_after,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "decisions": {
            "new_b2b_sales_authority": "ERPNext Sales Invoice",
            "new_b2b_payment_authority": "ERPNext Payment Entry",
            "receivables_authority": "ERPNext Sales Invoice + Payment Entry",
            "returns_authority": "ERPNext Sales Invoice Credit Note",
            "retail_pos_backend_cutover_performed": False,
            "fbr_submission_cutover_performed": False,
            "legacy_sale_payment_doctypes_retired": False,
        },
        "phase6_complete": complete,
        "phase7_ready": complete,
        "next_phase": "Phase 7 — Buying and Inventory Cutover",
        "passed": complete,
    }
    frappe.db.commit()
    return result
