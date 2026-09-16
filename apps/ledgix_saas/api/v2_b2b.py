from __future__ import annotations

"""Backward-compatible B2B API wrappers.

Phase 6 moves the financial authority to ERPNext. Existing callers may keep the
old module path until the UI cleanup phase, but these endpoints no longer write
Ledgix Sale/Payment or derive receivables from the legacy ledger.
"""

from ledgix_saas.api import selling


get_customer_credit = selling.get_customer_credit
get_customer_open_invoices = selling.get_customer_open_invoices
post_customer_payment = selling.post_customer_payment


@selling.frappe.whitelist()
def refresh_customer_credit(customer):
    # The ERPNext-backed view is authoritative and does not maintain a duplicate
    # cached Ledgix Customer balance, so refresh simply returns the live result.
    return selling.get_customer_credit(customer)


@selling.frappe.whitelist()
def reverse_customer_payment(payment, reason):
    result = selling.cancel_customer_payment(payment, reason)
    # Preserve the old response key for transitional UI callers while making it
    # explicit that ERPNext cancels/reverses the original Payment Entry rather
    # than creating a parallel Ledgix reversal document.
    result["reversal"] = result["payment"]
    result["original_payment"] = payment
    return result
