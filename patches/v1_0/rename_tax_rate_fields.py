import frappe


def execute():
    rename_or_copy_column("Ledgix Tax Rate", "rate_", "rate")
    rename_or_copy_column("Ledgix Invoice Tax Detail", "tax_rate_", "tax_rate")
    rename_or_copy_column("Ledgix Return Tax Detail", "tax_rate_", "tax_rate")


def rename_or_copy_column(doctype, old_fieldname, new_fieldname):
    table = f"tab{doctype}"
    has_old = frappe.db.has_column(doctype, old_fieldname)
    has_new = frappe.db.has_column(doctype, new_fieldname)

    if has_old and not has_new:
        frappe.db.rename_column(doctype, old_fieldname, new_fieldname)
        return

    if has_old and has_new:
        frappe.db.sql(
            f"""
            UPDATE `{table}`
            SET `{new_fieldname}` = `{old_fieldname}`
            WHERE (`{new_fieldname}` IS NULL OR `{new_fieldname}` = '')
              AND `{old_fieldname}` IS NOT NULL
              AND `{old_fieldname}` != ''
            """
        )
