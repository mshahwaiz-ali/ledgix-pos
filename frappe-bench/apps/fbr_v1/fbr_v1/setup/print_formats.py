from __future__ import annotations

"""Keep FBR V1 native Print Formats synchronized with app JSON.

Standard Frappe documents can remain newer in the database than their exported
JSON metadata, which means a normal migrate may retain stale Jinja. FBR V1
print formats are executable runtime contracts, so reload them forcefully after
migrate and fail closed if the database copy is not the expected revision.
"""

import frappe


PRINT_FORMATS = (
    ("Ledgix ERPNext Tax Invoice", "ledgix_erpnext_tax_invoice", "Sales Invoice"),
    ("Ledgix ERPNext POS Receipt", "ledgix_erpnext_pos_receipt", "POS Invoice"),
)


def sync_native_print_formats() -> None:
    for format_name, docname, expected_doctype in PRINT_FORMATS:
        frappe.reload_doc("fbr_v1", "print_format", docname, force=True)
        row = frappe.db.get_value(
            "Print Format",
            format_name,
            ["doc_type", "html", "disabled", "module"],
            as_dict=True,
        )
        if not row:
            frappe.throw(f"Required FBR V1 Print Format {format_name!r} was not imported.")
        if row.module != "FBR V1":
            frappe.throw(f"Required current V1 Print Format {format_name!r} has unexpected module ownership.")
        html = str(row.html or "")
        if "get_native_invoice_print_context" not in html:
            frappe.throw(f"Required current V1 Print Format {format_name!r} lacks the current context reader.")
        if row.doc_type != expected_doctype:
            frappe.throw(
                f"FBR V1 Print Format {format_name!r} targets {row.doc_type!r}; "
                f"expected {expected_doctype!r}."
            )
        if int(row.disabled or 0):
            frappe.throw(f"Required FBR V1 Print Format {format_name!r} is disabled.")
        if "p['items']" not in html or "p.items" in html:
            frappe.throw(
                f"FBR V1 Print Format {format_name!r} is stale; expected collision-safe Jinja items access."
            )


def after_migrate() -> None:
    sync_native_print_formats()
