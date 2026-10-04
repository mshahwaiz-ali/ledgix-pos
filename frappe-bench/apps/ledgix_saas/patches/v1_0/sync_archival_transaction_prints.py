"""Idempotent print-only correction; no transaction, fiscal or accounting writes."""
from frappe.modules.utils import reload_doc

def execute():
    reload_doc("ledgix", "print_format", "ledgix_thermal_receipt", force=True)
    reload_doc("ledgix", "print_format", "ledgix_b2b_invoice", force=True)
