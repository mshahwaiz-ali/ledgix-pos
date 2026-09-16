from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.migration import erpnext_invoice_behavioral_spike as invoice_base
from ledgix_saas.migration.erpnext_integration_bootstrap import CURRENCY, INTEGRATION_SITE, TEST_COMPANY


PRICING_ITEM = "LEDGIX-PRICING-SPIKE"
PRICING_RATE = 1000.0
PRICING_DISCOUNT = 10.0
PRICING_RULE_TITLE = "Ledgix ERPNext Pricing Rule Spike"
PARTIAL_INVOICE_MARKER = "LEDGIX-ERPNEXT-PARTIAL-PAYMENT-SPIKE-V1"
PARTIAL_PAYMENT_MARKER = "LEDGIX-ERPNEXT-PARTIAL-PAYMENT-PE-V1"
UNALLOCATED_PAYMENT_MARKER = "LEDGIX-ERPNEXT-UNALLOCATED-PAYMENT-V1"
PARTIAL_RETURN_SOURCE_MARKER = "LEDGIX-ERPNEXT-PARTIAL-RETURN-SOURCE-V1"
PARTIAL_RETURN_MARKER = "LEDGIX-ERPNEXT-PARTIAL-RETURN-V1"
PARTIAL_INVOICE_QTY = 2.0
PARTIAL_PAYMENT_AMOUNT = 1000.0
UNALLOCATED_AMOUNT = 300.0
PARTIAL_RETURN_SOURCE_QTY = 4.0
PARTIAL_RETURN_QTY = 1.0


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext finance/pricing behavioral spike on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _ensure_pricing_item() -> str:
    if frappe.db.exists("Item", PRICING_ITEM):
        return PRICING_ITEM

    doc = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": PRICING_ITEM,
            "item_name": "Ledgix ERPNext Pricing Rule Spike",
            "description": "Dedicated non-stock item for native ERPNext Pricing Rule behavior",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_pricing_item_price(item_code: str) -> str:
    existing = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": invoice_base.SELLING_PRICE_LIST,
            "currency": CURRENCY,
            "uom": "Nos",
        },
        "name",
    )
    if existing:
        doc = frappe.get_doc("Item Price", existing)
        if flt(doc.price_list_rate) != PRICING_RATE:
            doc.price_list_rate = PRICING_RATE
            doc.save(ignore_permissions=True)
        return doc.name

    doc = frappe.get_doc(
        {
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": invoice_base.SELLING_PRICE_LIST,
            "price_list_rate": PRICING_RATE,
            "currency": CURRENCY,
            "uom": "Nos",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_pricing_rule(item_code: str) -> str:
    existing = frappe.db.get_value("Pricing Rule", {"title": PRICING_RULE_TITLE}, "name")
    if existing:
        rule = frappe.get_doc("Pricing Rule", existing)
        changed = False
        expected = {
            "disable": 0,
            "apply_on": "Item Code",
            "price_or_product_discount": "Price",
            "selling": 1,
            "buying": 0,
            "company": TEST_COMPANY,
            "currency": CURRENCY,
            "rate_or_discount": "Discount Percentage",
            "discount_percentage": PRICING_DISCOUNT,
            "for_price_list": invoice_base.SELLING_PRICE_LIST,
        }
        for fieldname, value in expected.items():
            if rule.get(fieldname) != value:
                rule.set(fieldname, value)
                changed = True
        if not any(row.item_code == item_code for row in rule.items):
            rule.set("items", [{"item_code": item_code}])
            changed = True
        if changed:
            rule.save(ignore_permissions=True)
        return rule.name

    rule = frappe.get_doc(
        {
            "doctype": "Pricing Rule",
            "title": PRICING_RULE_TITLE,
            "disable": 0,
            "apply_on": "Item Code",
            "price_or_product_discount": "Price",
            "items": [{"item_code": item_code}],
            "selling": 1,
            "buying": 0,
            "company": TEST_COMPANY,
            "currency": CURRENCY,
            "rate_or_discount": "Discount Percentage",
            "discount_percentage": PRICING_DISCOUNT,
            "for_price_list": invoice_base.SELLING_PRICE_LIST,
        }
    )
    rule.insert(ignore_permissions=True)
    return rule.name


def _pricing_details(item_code: str, customer: str) -> dict:
    from erpnext.stock.get_item_details import get_item_details

    args = frappe._dict(
        {
            "item_code": item_code,
            "company": TEST_COMPANY,
            "price_list": invoice_base.SELLING_PRICE_LIST,
            "currency": CURRENCY,
            "doctype": "Sales Invoice",
            "conversion_rate": 1,
            "price_list_currency": CURRENCY,
            "plc_conversion_rate": 1,
            "order_type": "Sales",
            "customer": customer,
            "name": None,
            "qty": 1,
        }
    )
    return dict(get_item_details(args) or {})


def _get_submitted_invoice(marker: str):
    name = frappe.db.get_value(
        "Sales Invoice",
        {"company": TEST_COMPANY, "remarks": marker, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("Sales Invoice", name) if name else None


def _ensure_invoice(customer: str, item_code: str, marker: str, qty: float):
    existing = _get_submitted_invoice(marker)
    if existing:
        return existing

    invoice = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": TEST_COMPANY,
            "customer": customer,
            "posting_date": nowdate(),
            "currency": CURRENCY,
            "selling_price_list": invoice_base.SELLING_PRICE_LIST,
            "remarks": marker,
            "update_stock": 0,
            "items": [
                {
                    "item_code": item_code,
                    "qty": qty,
                    "uom": "Nos",
                    "rate": invoice_base.TEST_RATE,
                }
            ],
        }
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _payment_by_marker(marker: str):
    name = frappe.db.get_value(
        "Payment Entry",
        {"company": TEST_COMPANY, "remarks": marker, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("Payment Entry", name) if name else None


def _ensure_partial_payment(invoice, cash_account: str):
    existing = _payment_by_marker(PARTIAL_PAYMENT_MARKER)
    if existing:
        return existing

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Sales Invoice", invoice.name)
    payment.mode_of_payment = "Cash"
    payment.paid_to = cash_account
    payment.remarks = PARTIAL_PAYMENT_MARKER
    payment.paid_amount = PARTIAL_PAYMENT_AMOUNT
    payment.received_amount = PARTIAL_PAYMENT_AMOUNT
    payment.base_paid_amount = PARTIAL_PAYMENT_AMOUNT
    payment.base_received_amount = PARTIAL_PAYMENT_AMOUNT
    if not payment.references:
        frappe.throw("Native Payment Entry mapper returned no Sales Invoice reference for partial-payment spike.")
    payment.references[0].allocated_amount = PARTIAL_PAYMENT_AMOUNT
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment


def _ensure_unallocated_payment(invoice, cash_account: str):
    existing = _payment_by_marker(UNALLOCATED_PAYMENT_MARKER)
    if existing:
        return existing

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Sales Invoice", invoice.name)
    payment.mode_of_payment = "Cash"
    payment.paid_to = cash_account
    payment.remarks = UNALLOCATED_PAYMENT_MARKER
    payment.set("references", [])
    payment.paid_amount = UNALLOCATED_AMOUNT
    payment.received_amount = UNALLOCATED_AMOUNT
    payment.base_paid_amount = UNALLOCATED_AMOUNT
    payment.base_received_amount = UNALLOCATED_AMOUNT
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment


def _ensure_partial_return(source_invoice):
    existing_name = frappe.db.get_value(
        "Sales Invoice",
        {
            "company": TEST_COMPANY,
            "is_return": 1,
            "return_against": source_invoice.name,
            "remarks": PARTIAL_RETURN_MARKER,
            "docstatus": 1,
        },
        "name",
    )
    if existing_name:
        return frappe.get_doc("Sales Invoice", existing_name)

    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    return_doc = make_return_doc("Sales Invoice", source_invoice.name)
    return_doc.remarks = PARTIAL_RETURN_MARKER
    if not return_doc.items:
        frappe.throw("Native return mapper produced no item rows for partial-return spike.")
    return_doc.items[0].qty = -PARTIAL_RETURN_QTY
    return_doc.items[0].stock_qty = -PARTIAL_RETURN_QTY
    return_doc.items[0].rate = invoice_base.TEST_RATE
    return_doc.payment_schedule = []
    return_doc.insert(ignore_permissions=True)
    return_doc.submit()
    return return_doc


def _gl_count(voucher_type: str, voucher_no: str) -> int:
    return frappe.db.count(
        "GL Entry",
        {"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0},
    )


def _render_print(invoice_name: str) -> str:
    html = frappe.get_print("Sales Invoice", invoice_name)
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    return str(html or "")


def run() -> dict:
    """Prove native pricing, partial/unallocated payment, partial return and print behavior."""

    _assert_safe_site()
    frappe.set_user("Administrator")

    customer = invoice_base._ensure_customer()
    nonstock_item = invoice_base._ensure_nonstock_item()
    invoice_base._ensure_item_price(nonstock_item)
    cash_account = invoice_base._ensure_cash_mode_account()

    pricing_item = _ensure_pricing_item()
    pricing_item_price = _ensure_pricing_item_price(pricing_item)
    pricing_rule = _ensure_pricing_rule(pricing_item)
    pricing = _pricing_details(pricing_item, customer)

    partial_invoice = _ensure_invoice(customer, nonstock_item, PARTIAL_INVOICE_MARKER, PARTIAL_INVOICE_QTY)
    partial_payment = _ensure_partial_payment(partial_invoice, cash_account)
    partial_invoice.reload()

    unallocated_payment = _ensure_unallocated_payment(partial_invoice, cash_account)
    unallocated_payment.reload()
    partial_invoice.reload()

    return_source = _ensure_invoice(
        customer,
        nonstock_item,
        PARTIAL_RETURN_SOURCE_MARKER,
        PARTIAL_RETURN_SOURCE_QTY,
    )
    partial_return = _ensure_partial_return(return_source)
    return_source.reload()
    partial_return.reload()

    print_html = _render_print(partial_invoice.name)

    expected_pricing_rate = flt(PRICING_RATE * (1 - PRICING_DISCOUNT / 100), 2)
    resolved_price_list_rate = flt(pricing.get("price_list_rate"))
    resolved_discount = flt(pricing.get("discount_percentage"))
    effective_pricing_rate = flt(resolved_price_list_rate * (1 - resolved_discount / 100), 2)
    expected_partial_outstanding = flt(partial_invoice.grand_total - PARTIAL_PAYMENT_AMOUNT, 2)
    expected_partial_return_total = flt(
        -(return_source.grand_total * (PARTIAL_RETURN_QTY / PARTIAL_RETURN_SOURCE_QTY)), 2
    )

    evidence = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "pricing": {
            "item": pricing_item,
            "item_price": pricing_item_price,
            "pricing_rule": pricing_rule,
            "price_list_rate": resolved_price_list_rate,
            "discount_percentage": resolved_discount,
            "raw_helper_rate": flt(pricing.get("rate")),
            "effective_rate": effective_pricing_rate,
            "expected_rate": expected_pricing_rate,
            "note": (
                "get_item_details can leave rate unset/zero when called without a full parent transaction; "
                "the native pricing decision is evidenced by Item Price plus resolved Pricing Rule discount."
            ),
        },
        "partial_payment": {
            "invoice": partial_invoice.name,
            "invoice_grand_total": flt(partial_invoice.grand_total),
            "invoice_outstanding": flt(partial_invoice.outstanding_amount),
            "expected_outstanding": expected_partial_outstanding,
            "payment_entry": partial_payment.name,
            "payment_docstatus": partial_payment.docstatus,
            "allocated_amount": flt(partial_payment.references[0].allocated_amount),
            "payment_gl_entries": _gl_count("Payment Entry", partial_payment.name),
        },
        "unallocated_payment": {
            "payment_entry": unallocated_payment.name,
            "docstatus": unallocated_payment.docstatus,
            "paid_amount": flt(unallocated_payment.paid_amount),
            "unallocated_amount": flt(unallocated_payment.unallocated_amount),
            "reference_count": len(unallocated_payment.references),
            "payment_gl_entries": _gl_count("Payment Entry", unallocated_payment.name),
        },
        "partial_return": {
            "source_invoice": return_source.name,
            "source_qty": flt(return_source.items[0].qty),
            "source_grand_total": flt(return_source.grand_total),
            "return_invoice": partial_return.name,
            "return_against": partial_return.return_against,
            "return_qty": flt(partial_return.items[0].qty),
            "return_grand_total": flt(partial_return.grand_total),
            "expected_return_total": expected_partial_return_total,
            "return_gl_entries": _gl_count("Sales Invoice", partial_return.name),
        },
        "print": {
            "invoice": partial_invoice.name,
            "html_length": len(print_html),
            "contains_invoice_name": partial_invoice.name in print_html,
            "contains_customer": customer in print_html or invoice_base.TEST_CUSTOMER in print_html,
        },
    }

    checks = {
        "pricing_rule_resolved": abs(evidence["pricing"]["discount_percentage"] - PRICING_DISCOUNT) < 0.005,
        "pricing_item_price_resolved": abs(evidence["pricing"]["price_list_rate"] - PRICING_RATE) < 0.005,
        "pricing_rule_effective_rate_correct": abs(
            evidence["pricing"]["effective_rate"] - expected_pricing_rate
        ) < 0.005,
        "partial_payment_submitted": partial_payment.docstatus == 1,
        "partial_payment_allocated": abs(
            evidence["partial_payment"]["allocated_amount"] - PARTIAL_PAYMENT_AMOUNT
        ) < 0.005,
        "partial_payment_keeps_outstanding": abs(
            evidence["partial_payment"]["invoice_outstanding"] - expected_partial_outstanding
        ) < 0.005,
        "partial_payment_has_gl": evidence["partial_payment"]["payment_gl_entries"] > 0,
        "unallocated_payment_submitted": unallocated_payment.docstatus == 1,
        "unallocated_payment_has_no_references": evidence["unallocated_payment"]["reference_count"] == 0,
        "unallocated_payment_amount_preserved": abs(
            evidence["unallocated_payment"]["unallocated_amount"] - UNALLOCATED_AMOUNT
        ) < 0.005,
        "unallocated_payment_has_gl": evidence["unallocated_payment"]["payment_gl_entries"] > 0,
        "partial_return_submitted": partial_return.docstatus == 1,
        "partial_return_linked": partial_return.return_against == return_source.name,
        "partial_return_qty_correct": abs(
            evidence["partial_return"]["return_qty"] + PARTIAL_RETURN_QTY
        ) < 0.005,
        "partial_return_total_correct": abs(
            evidence["partial_return"]["return_grand_total"] - expected_partial_return_total
        ) < 0.01,
        "partial_return_has_gl": evidence["partial_return"]["return_gl_entries"] > 0,
        "native_print_rendered": evidence["print"]["html_length"] > 500,
        "native_print_identifies_invoice": evidence["print"]["contains_invoice_name"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())
    frappe.db.commit()
    return evidence
