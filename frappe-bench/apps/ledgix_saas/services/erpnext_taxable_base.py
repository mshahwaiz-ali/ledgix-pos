"""Historical parity-gate compatibility. Federal V1 owns the implementation."""
import frappe
from ledgix_saas.services.fbr_v1_bridge import stamp_taxable_base_inputs as stamp_fbr_taxable_base_inputs

CHARGE_TYPE = "On Notified Retail Price"


def resolve_notified_retail_price(doc, item, tax):
    return frappe.get_attr("fbr_v1.services.erpnext_taxable_base.resolve_notified_retail_price")(doc, item, tax)
