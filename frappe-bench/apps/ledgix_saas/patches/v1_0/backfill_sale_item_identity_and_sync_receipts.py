"""Retained patch identity; no reconstruction of historical item identity."""
from frappe.modules.utils import reload_doc

def _backfill_sale_item_identity():
    return

def execute():
    reload_doc("ledgix", "print_format", "ledgix_thermal_receipt", force=True)
    reload_doc("ledgix", "print_format", "ledgix_b2b_invoice", force=True)
