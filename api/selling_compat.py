from __future__ import annotations

"""Compatibility wrappers where the current UI still assumes legacy document types.

The Phase 6 B2B checkout returns a native Sales Invoice. The current POS page's
post-sale print helper is still hard-coded to `Ledgix Sale`, so allowing it to
run with a Sales Invoice name would open a broken print URL. Until the dedicated
print migration phase, suppress that legacy auto-print trigger while preserving
the native invoice identifier in the response.
"""

import frappe

from ledgix_saas.api import selling


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
    result = selling.complete_pos_v2_sale_compat(
        cart_items=cart_items,
        tenders=tenders,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        client_sale_id=client_sale_id,
    )
    if sale_channel == "B2B" and result.get("financial_authority") == "ERPNext":
        invoice = result.get("invoice") or result.get("sale") or result.get("invoice_number")
        result["erpnext_sales_invoice"] = invoice
        # Current page only calls its legacy Ledgix Sale print helper when
        # `result.sale` is truthy. Full Sales Invoice print branding is Phase 10.
        result["sale"] = ""
        result["print_deferred"] = True
    return result
