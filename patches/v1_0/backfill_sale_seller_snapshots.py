from __future__ import annotations

import frappe

from ledgix_saas.services.sales import get_seller_identity


SNAPSHOT_FIELDS = {
    "seller_name_snapshot": "name",
    "seller_address_snapshot": "address",
    "seller_province_snapshot": "province",
    "seller_ntn_cnic_snapshot": "ntn_cnic",
    "seller_strn_snapshot": "strn",
    "seller_phone_snapshot": "phone",
    "seller_email_snapshot": "email",
}


def execute():
    if not frappe.db.exists("DocType", "Ledgix Sale"):
        return

    meta = frappe.get_meta("Ledgix Sale")
    if not all(meta.has_field(fieldname) for fieldname in SNAPSHOT_FIELDS):
        return

    identity = get_seller_identity()
    for sale in frappe.get_all("Ledgix Sale", fields=["name", *SNAPSHOT_FIELDS.keys()]):
        # Existing V2 records that already carry any seller snapshot are historical
        # truth and must not be overwritten by a later migration.
        if any(str(sale.get(fieldname) or "").strip() for fieldname in SNAPSHOT_FIELDS):
            continue

        values = {
            fieldname: identity.get(identity_key) or ""
            for fieldname, identity_key in SNAPSHOT_FIELDS.items()
        }
        frappe.db.set_value("Ledgix Sale", sale.name, values, update_modified=False)

    frappe.db.commit()
