from frappe.modules.utils import reload_doc


def execute():
    """Force standard V2 print formats from app JSON onto existing sites.

    Standard Print Format records can remain older in a site database when their
    stored modified timestamp outranks the app JSON. Force reload keeps deployed
    sites aligned with the version-controlled thermal receipt and B2B invoice.
    """
    reload_doc("ledgix", "print_format", "ledgix_thermal_receipt", force=True)
    reload_doc("ledgix", "print_format", "ledgix_b2b_invoice", force=True)
