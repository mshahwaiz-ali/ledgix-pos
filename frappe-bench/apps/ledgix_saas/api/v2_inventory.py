from __future__ import annotations

import frappe

from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.services import erpnext_buying_inventory


@frappe.whitelist()
def get_available_pos_serials(item=None, limit=200, warehouse=None):
    """Return available ERPNext Serial Nos while preserving the POS response shape."""

    require_ledgix_cashier_or_above()
    item_input = str(item or "").strip()
    if not item_input:
        frappe.throw("Valid item is required.")

    item_code = erpnext_buying_inventory._resolve_item(item_input)
    rows = erpnext_buying_inventory.available_serials(
        item_code,
        warehouse=warehouse,
        limit=limit,
    )
    return {
        "item": item_input,
        "erpnext_item": item_code,
        "authority": "ERPNext Serial No",
        "serials": rows,
    }
