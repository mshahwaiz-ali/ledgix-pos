from __future__ import annotations

"""Compatibility wrappers while the current POS page still uses legacy master IDs.

Phase 6 keeps the UI contract stable but removes competing B2B financial and
pricing authority. Retail remains delegated to the existing backend until the
POS cutover phase. Public B2B write/preview routes pass through this module so
manual rate overrides always require and preserve an audit reason.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from ledgix_saas.api import selling
from ledgix_saas.services import erpnext_selling


def _decorate_native_credit(result: dict, customer: str | None) -> dict:
    if not customer or not result.get("customer"):
        return result
    credit = erpnext_selling.get_customer_receivables(customer)
    customer_row = dict(result.get("customer") or {})
    customer_row.update(
        {
            "outstanding": flt(credit.get("outstanding"), 2),
            "available_credit": flt(credit.get("available_credit"), 2),
            "overdue": flt(credit.get("overdue"), 2),
        }
    )
    result["customer"] = customer_row
    result["financial_authority"] = "ERPNext"
    return result


def _price_override_audit(cart_items) -> list[dict]:
    rows = frappe.parse_json(cart_items) if isinstance(cart_items, str) else cart_items
    audit = []
    for raw in rows or []:
        override = raw.get("override_rate")
        if override in (None, ""):
            continue
        reason = str(raw.get("override_reason") or "").strip()
        if not reason:
            frappe.throw(_("Authorized B2B price override requires a reason."))
        audit.append(
            {
                "item": raw.get("item") or raw.get("item_code"),
                "override_rate": flt(override, 6),
                "reason": reason,
            }
        )
    return audit


def _persist_override_audit(invoice: str | None, audit: list[dict]) -> None:
    if not invoice or not audit:
        return
    payload = json.dumps(audit, sort_keys=True, separators=(",", ":"))
    current = frappe.db.get_value(
        "Sales Invoice", invoice, "custom_ledgix_price_override_json"
    )
    # An idempotent retry must never rewrite the original authorized audit trail.
    if not current:
        frappe.db.set_value(
            "Sales Invoice",
            invoice,
            "custom_ledgix_price_override_json",
            payload,
            update_modified=False,
        )


def _invoice_from_result(result: dict | None) -> str:
    result = result or {}
    invoice = result.get("invoice") or result.get("invoice_number") or result.get("sale")
    if isinstance(invoice, dict):
        invoice = invoice.get("invoice") or invoice.get("name")
    return str(invoice or "")


def _ensure_checkout_payments(result: dict, tenders, client_sale_id: str | None) -> dict:
    """Recover deterministic checkout tenders after an interrupted B2B retry.

    The underlying invoice and Payment Entry services are independently
    idempotent. If the first request committed the Sales Invoice (or only some
    tenders) before the client retried, reuse existing ``client_sale_id:PAY:n``
    entries and create only the missing ones.
    """

    result = dict(result or {})
    client_sale_id = str(client_sale_id or "").strip()
    invoice_name = _invoice_from_result(result)
    if not client_sale_id or not invoice_name:
        return result

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    payment_names = []
    for index, tender in enumerate(_parse_tenders(tenders), start=1):
        amount = flt(tender.get("amount"))
        method = tender.get("payment_method") or tender.get("mode_of_payment")
        if amount <= 0 or not method:
            continue

        payment_client_id = f"{client_sale_id}:PAY:{index}"
        existing = frappe.db.get_value(
            "Payment Entry",
            {
                "company": invoice.company,
                "custom_ledgix_client_payment_id": payment_client_id,
                "docstatus": ["!=", 2],
            },
            "name",
        )
        if existing:
            payment_names.append(existing)
            continue

        invoice.reload()
        allocation = min(amount, max(flt(invoice.outstanding_amount), 0))
        if allocation <= 0:
            continue
        payment = erpnext_selling.post_customer_payment(
            customer=invoice.customer,
            mode_of_payment=method,
            amount=amount,
            allocations=[
                {"reference_name": invoice.name, "allocated_amount": allocation}
            ],
            company=invoice.company,
            client_payment_id=payment_client_id,
            reference_number=tender.get("reference_number")
            or tender.get("reference_no"),
            payment_source="Ledgix POS B2B Checkout",
        )
        payment_names.append(payment.name)

    invoice.reload()
    result["payments"] = payment_names
    result["paid_amount"] = flt(invoice.grand_total - invoice.outstanding_amount, 2)
    result["remaining_amount"] = max(flt(invoice.outstanding_amount, 2), 0)
    result["payment_status"] = (
        "Paid"
        if abs(flt(invoice.outstanding_amount)) <= 0.005
        else "Partial"
        if flt(invoice.outstanding_amount) < flt(invoice.grand_total) - 0.005
        else "Unpaid"
    )
    return result


def _parse_tenders(tenders) -> list[dict]:
    rows = frappe.parse_json(tenders) if isinstance(tenders, str) else tenders
    return [dict(row) for row in (rows or [])]


@frappe.whitelist()
def preview_b2b_invoice(
    customer,
    items=None,
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    _price_override_audit(items)
    return selling.preview_b2b_invoice(
        customer=customer,
        items=items,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        due_date=due_date,
    )


@frappe.whitelist()
def create_b2b_invoice(
    customer,
    items=None,
    price_list=None,
    client_sale_id=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    audit = _price_override_audit(items)
    result = selling.create_b2b_invoice(
        customer=customer,
        items=items,
        price_list=price_list,
        client_sale_id=client_sale_id,
        discount_type=discount_type,
        discount_value=discount_value,
        due_date=due_date,
    )
    _persist_override_audit(_invoice_from_result(result), audit)
    return result


@frappe.whitelist()
def complete_b2b_sale(
    customer,
    cart_items=None,
    tenders=None,
    price_list=None,
    client_sale_id=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    audit = _price_override_audit(cart_items)
    result = selling.complete_b2b_sale(
        customer=customer,
        cart_items=cart_items,
        tenders=tenders,
        price_list=price_list,
        client_sale_id=client_sale_id,
        discount_type=discount_type,
        discount_value=discount_value,
        due_date=due_date,
    )
    result = _ensure_checkout_payments(result, tenders, client_sale_id)
    _persist_override_audit(_invoice_from_result(result), audit)
    return result


@frappe.whitelist()
def create_exchange(
    sales_invoice,
    return_items=None,
    replacement_items=None,
    reason=None,
    exchange_reference=None,
    client_return_id=None,
    client_sale_id=None,
    price_list=None,
):
    audit = _price_override_audit(replacement_items)
    result = selling.create_exchange(
        sales_invoice=sales_invoice,
        return_items=return_items,
        replacement_items=replacement_items,
        reason=reason,
        exchange_reference=exchange_reference,
        client_return_id=client_return_id,
        client_sale_id=client_sale_id,
        price_list=price_list,
    )
    replacement = (result or {}).get("replacement_invoice") or {}
    invoice = replacement.get("invoice") if isinstance(replacement, dict) else replacement
    _persist_override_audit(str(invoice or ""), audit)
    return result


@frappe.whitelist()
def get_pos_v2_boot(customer=None, sale_channel="Retail"):
    from ledgix_saas.api.v2_pos import get_pos_v2_boot as legacy_boot

    result = legacy_boot(customer=customer, sale_channel=sale_channel)
    if sale_channel == "B2B":
        _decorate_native_credit(result, customer)
    return result


@frappe.whitelist()
def search_pos_v2_items(
    query=None,
    category=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    limit=80,
):
    """Keep catalog metadata compatible while ERPNext owns B2B line pricing."""

    from ledgix_saas.api.v2_pos import search_pos_v2_items as legacy_search

    result = legacy_search(
        query=query,
        category=category,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        limit=limit,
    )
    if sale_channel != "B2B":
        return result

    native_customer = erpnext_selling._resolve_customer(customer)
    native_price_list = erpnext_selling._resolve_price_list(
        result.get("price_list") or price_list
    )
    posting_date = nowdate()
    for row in result.get("items") or []:
        native_item = erpnext_selling._resolve_item(row.get("name") or row.get("item_code"))
        details = erpnext_selling._native_item_rate(
            item_code=native_item,
            customer=native_customer,
            company=erpnext_selling._company(None),
            price_list=native_price_list,
            qty=1,
            posting_date=posting_date,
        )
        row["rate"] = flt(details.rate, 2)
        row["list_rate"] = flt(details.price_list_rate, 2)
        row["erpnext_item"] = native_item
        row["pricing_authority"] = "ERPNext"
    result["erpnext_price_list"] = native_price_list
    result["pricing_authority"] = "ERPNext"
    return result


@frappe.whitelist()
def preview_pos_v2_checkout(
    cart_items=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    discount_type="Amount",
    discount_value=0,
):
    if sale_channel == "B2B":
        _price_override_audit(cart_items)
    return selling.preview_pos_v2_checkout_compat(
        cart_items=cart_items,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
    )


@frappe.whitelist()
def complete_pos_v2_sale(
    cart_items=None,
    tenders=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    client_sale_id=None,
):
    if sale_channel == "B2B":
        result = complete_b2b_sale(
            customer=customer,
            cart_items=cart_items,
            tenders=tenders,
            price_list=price_list,
            client_sale_id=client_sale_id,
            discount_type=discount_type,
            discount_value=discount_value,
        )
        invoice = _invoice_from_result(result)
        result["erpnext_sales_invoice"] = invoice
        # Current page only calls its legacy Ledgix Sale print helper when
        # `result.sale` is truthy. Full Sales Invoice print branding is Phase 10.
        result["sale"] = ""
        result["print_deferred"] = True
        return result

    return selling.complete_pos_v2_sale_compat(
        cart_items=cart_items,
        tenders=tenders,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        client_sale_id=client_sale_id,
    )
