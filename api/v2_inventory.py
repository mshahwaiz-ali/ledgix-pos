from __future__ import annotations

import frappe

from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.api.stock_identity import is_serial_based_item


@frappe.whitelist()
def get_available_pos_serials(item=None, limit=200):
    """Return currently available serial identities for a Serial Based POS item."""
    require_ledgix_cashier_or_above()
    item = str(item or "").strip()
    if not item or not frappe.db.exists("Ledgix Item", item):
        frappe.throw("Valid item is required.")
    if not is_serial_based_item(item):
        frappe.throw("Serial selection is only available for Serial Based items.")

    limit = min(max(int(limit or 200), 1), 500)
    rows = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"item": item, "status": "Available"},
        fields=["name", "serial_no", "purchase", "purchase_date"],
        order_by="purchase_date asc, creation asc, serial_no asc",
        limit_page_length=limit,
    )
    return {
        "item": item,
        "serials": [
            {
                "name": row.name,
                "serial_no": row.serial_no,
                "purchase": row.purchase,
                "purchase_date": row.purchase_date,
            }
            for row in rows
        ],
    }
