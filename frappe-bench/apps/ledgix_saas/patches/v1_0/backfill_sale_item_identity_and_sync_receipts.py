from __future__ import annotations

import frappe
from frappe.modules.utils import reload_doc


SNAPSHOT_FIELDS = ("item_name_snapshot", "item_code_snapshot", "unit_snapshot")


def _backfill_sale_item_identity():
    if not frappe.db.exists("DocType", "Ledgix Sale Item"):
        return

    meta = frappe.get_meta("Ledgix Sale Item")
    if not all(meta.has_field(fieldname) for fieldname in SNAPSHOT_FIELDS):
        return

    rows = frappe.get_all(
        "Ledgix Sale Item",
        fields=["name", "item", *SNAPSHOT_FIELDS],
        limit_page_length=0,
    )
    for row in rows:
        if not row.item:
            continue
        values = {}
        item = frappe.db.get_value(
            "Ledgix Item",
            row.item,
            ["item_code", "item_name", "unit"],
            as_dict=True,
        )
        if not row.item_code_snapshot:
            values["item_code_snapshot"] = (item and item.item_code) or row.item
        if not row.item_name_snapshot:
            values["item_name_snapshot"] = (item and (item.item_name or item.item_code)) or row.item
        if not row.unit_snapshot and item and item.unit:
            values["unit_snapshot"] = item.unit
        if values:
            frappe.db.set_value("Ledgix Sale Item", row.name, values, update_modified=False)


def execute():
    """Backfill item identity snapshots and force the customer-facing print formats.

    Historical rows can only use the current item master as their best available
    identity fallback. New finalized sales freeze these fields at submit time.
    """
    _backfill_sale_item_identity()
    reload_doc("ledgix", "print_format", "ledgix_thermal_receipt", force=True)
    reload_doc("ledgix", "print_format", "ledgix_b2b_invoice", force=True)
