from __future__ import annotations

"""Backward-compatible B2B API wrappers over ERPNext financial authority."""

import frappe

from ledgix_saas.api import selling
from ledgix_saas.services import erpnext_selling


def _compat_credit(result):
    result = dict(result or {})
    invoices = []
    for raw in result.get("invoices") or []:
        row = dict(raw)
        # Preserve the historic identifiers used by transitional B2B consumers
        # without recreating the old Ledgix receivable ledger.
        row.setdefault("sale", row.get("invoice"))
        row.setdefault("gross", row.get("grand_total"))
        row.setdefault("net_balance", row.get("outstanding"))
        invoices.append(row)
    result["invoices"] = invoices
    return result


def _compat_allocations(allocations):
    rows = frappe.parse_json(allocations) if isinstance(allocations, str) else allocations
    normalized = []
    for raw in rows or []:
        row = dict(raw)
        if not row.get("reference_name") and not row.get("invoice") and row.get("sale"):
            row["reference_name"] = row["sale"]
        normalized.append(row)
    return normalized


def _validate_company_currency(currency) -> None:
    requested = str(currency or "").strip()
    if not requested:
        return
    company = erpnext_selling._company(None)
    company_currency = erpnext_selling._currency(company)
    if requested != company_currency:
        frappe.throw(
            f"Phase 6 B2B payment compatibility supports {company_currency} for {company}; "
            f"received {requested}. Use native ERPNext multi-currency Payment Entry for other currencies."
        )


@frappe.whitelist()
def get_customer_credit(customer):
    return _compat_credit(selling.get_customer_credit(customer))


@frappe.whitelist()
def refresh_customer_credit(customer):
    # ERPNext is live authority; there is no Ledgix receivable cache to refresh.
    return _compat_credit(selling.get_customer_credit(customer))


@frappe.whitelist()
def get_customer_open_invoices(customer):
    return _compat_credit(selling.get_customer_open_invoices(customer))


@frappe.whitelist()
def post_customer_payment(
    customer,
    payment_method,
    amount,
    allocations=None,
    reference_number=None,
    currency="PKR",
    client_payment_id=None,
):
    # Keep the historical argument for old callers, but never silently post a
    # different currency as the company's native currency.
    _validate_company_currency(currency)
    return selling.post_customer_payment(
        customer=customer,
        payment_method=payment_method,
        amount=amount,
        allocations=_compat_allocations(allocations),
        reference_number=reference_number,
        client_payment_id=client_payment_id,
    )


@frappe.whitelist()
def reverse_customer_payment(payment, reason):
    result = selling.cancel_customer_payment(payment, reason)
    customer = result.get("customer")
    result["reversal"] = result["payment"]
    result["original_payment"] = payment
    result["credit"] = (
        _compat_credit(selling.get_customer_credit(customer)) if customer else None
    )
    return result
