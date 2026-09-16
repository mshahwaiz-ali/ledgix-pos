from __future__ import annotations

"""Backward-compatible B2B API wrappers over ERPNext financial authority."""

import frappe

from ledgix_saas.api import selling


@frappe.whitelist()
def get_customer_credit(customer):
    return selling.get_customer_credit(customer)


@frappe.whitelist()
def refresh_customer_credit(customer):
    # ERPNext is live authority; there is no Ledgix receivable cache to refresh.
    return selling.get_customer_credit(customer)


@frappe.whitelist()
def get_customer_open_invoices(customer):
    return selling.get_customer_open_invoices(customer)


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
    # Keep the historical `currency` argument so old UI callers do not break.
    # Phase 6 currently supports the site's native company currency; ERPNext owns
    # any later multi-currency expansion.
    return selling.post_customer_payment(
        customer=customer,
        payment_method=payment_method,
        amount=amount,
        allocations=allocations,
        reference_number=reference_number,
        client_payment_id=client_payment_id,
    )


@frappe.whitelist()
def reverse_customer_payment(payment, reason):
    result = selling.cancel_customer_payment(payment, reason)
    customer = result.get("customer")
    result["reversal"] = result["payment"]
    result["original_payment"] = payment
    result["credit"] = selling.get_customer_credit(customer) if customer else None
    return result
