from frappe.modules.utils import reload_doc


def execute():
    """Force the latest Ledgix print-format source onto already-migrated sites.

    Earlier V2 print-format sync patches may already be recorded in Patch Log.
    The brand-fallback update changed the source after those patches ran, while
    the JSON modified timestamp remained older than the database record. Frappe
    therefore skips the normal non-DocType import. This one-time patch gives the
    updated thermal receipt and B2B invoice a fresh forced sync without adding
    recurring work to every migrate.
    """
    reload_doc("ledgix", "print_format", "ledgix_thermal_receipt", force=True)
    reload_doc("ledgix", "print_format", "ledgix_b2b_invoice", force=True)
