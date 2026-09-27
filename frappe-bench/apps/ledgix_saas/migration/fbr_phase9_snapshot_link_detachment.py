from __future__ import annotations

import hashlib
import json
import frappe

MAPPINGS = (
    (
        "Sales Invoice Item",
        "custom_ledgix_fbr_item_profile",
        "custom_ledgix_legacy_fbr_item_profile_snapshot",
    ),
    (
        "POS Invoice Item",
        "custom_ledgix_fbr_item_profile",
        "custom_ledgix_legacy_fbr_item_profile_snapshot",
    ),
    (
        "Item Group",
        "custom_ledgix_default_tax_category",
        "custom_ledgix_legacy_default_tax_category_snapshot",
    ),
)

LEGACY_TAX_DOCTYPES = {
    "Ledgix Tax Profile",
    "Ledgix Tax Category",
    "Ledgix Tax Rate",
    "Ledgix Item Tax Profile",
    "Ledgix Tax Audit Log",
    "Ledgix Invoice Tax Detail",
    "Ledgix Return Tax Detail",
}

def _custom_field_name(doctype, fieldname):
    return frappe.db.get_value(
        "Custom Field",
        {"dt": doctype, "fieldname": fieldname},
        "name",
    )

def _meta(doctype, fieldname):
    field = frappe.get_meta(doctype, cached=False).get_field(fieldname)
    return {
        "exists": bool(field),
        "fieldtype": field.fieldtype if field else None,
        "options": field.options if field else None,
    }

def _values(doctype, fieldname):
    if not frappe.db.has_column(doctype, fieldname):
        return []

    table = f"`tab{doctype}`"
    field = f"`{fieldname}`"
    rows = frappe.db.sql(
        f"SELECT name, IFNULL(CAST({field} AS CHAR), '') AS value "
        f"FROM {table} ORDER BY name",
        as_dict=True,
    )
    return [
        {"name": str(row.name), "value": str(row.value or "")}
        for row in rows
    ]

def _hash(doctype, fieldname):
    rows = _values(doctype, fieldname)
    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return {
        "row_count": len(rows),
        "nonempty_count": sum(1 for row in rows if row["value"]),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }

def _assert_safe_state():
    if not frappe.db.exists("DocType", "Ledgix Legacy Retirement State"):
        frappe.throw("Legacy Retirement State is missing")

    status = (
        frappe.db.get_single_value("Ledgix Legacy Retirement State", "status")
        or ""
    )
    if status != "Frozen":
        frappe.throw(
            f"Legacy retirement must be Frozen before snapshot detachment; got {status!r}"
        )

    profiles = frappe.get_all(
        "Ledgix FBR Integration Profile",
        fields=[
            "name",
            "enabled",
            "mode",
            "submit_trigger",
            "production_post_armed",
        ],
        limit_page_length=0,
    )

    for row in profiles:
        if (
            int(row.enabled or 0)
            or row.mode != "Disabled"
            or row.submit_trigger != "Manual"
            or int(row.production_post_armed or 0)
        ):
            frappe.throw(
                f"V2 profile {row.name} is not Disabled / Manual / unarmed"
            )

def preview():
    frappe.set_user("Administrator")
    _assert_safe_state()

    rows = []
    for doctype, old_field, new_field in MAPPINGS:
        rows.append(
            {
                "doctype": doctype,
                "old_field": old_field,
                "new_field": new_field,
                "old_custom_field": _custom_field_name(doctype, old_field),
                "new_custom_field": _custom_field_name(doctype, new_field),
                "old_meta": _meta(doctype, old_field),
                "new_meta": _meta(doctype, new_field),
                "old_hash": _hash(doctype, old_field),
                "new_hash": _hash(doctype, new_field),
            }
        )

    return {
        "read_only": True,
        "database_write": False,
        "fbr_network_call": False,
        "mappings": rows,
    }

def _external_legacy_links():
    rows = []

    for row in frappe.get_all(
        "Custom Field",
        filters={"fieldtype": "Link"},
        fields=["dt", "fieldname", "options"],
        limit_page_length=0,
    ):
        if row.options in LEGACY_TAX_DOCTYPES and row.dt not in LEGACY_TAX_DOCTYPES:
            rows.append(
                {
                    "kind": "Custom Field",
                    "parent": row.dt,
                    "fieldname": row.fieldname,
                    "options": row.options,
                }
            )

    for row in frappe.get_all(
        "DocField",
        filters={"fieldtype": "Link"},
        fields=["parent", "fieldname", "options"],
        limit_page_length=0,
    ):
        if row.options in LEGACY_TAX_DOCTYPES and row.parent not in LEGACY_TAX_DOCTYPES:
            rows.append(
                {
                    "kind": "DocField",
                    "parent": row.parent,
                    "fieldname": row.fieldname,
                    "options": row.options,
                }
            )

    return rows

def execute():
    frappe.set_user("Administrator")
    _assert_safe_state()

    before = preview()

    try:
        for row in before["mappings"]:
            doctype = row["doctype"]
            old_field = row["old_field"]
            new_field = row["new_field"]

            if not row["old_custom_field"]:
                frappe.throw(
                    f"{doctype}.{old_field} old Custom Field is absent before controlled copy"
                )

            if not row["new_custom_field"]:
                frappe.throw(
                    f"{doctype}.{new_field} replacement Data field is missing"
                )

            if row["new_meta"].get("fieldtype") != "Data":
                frappe.throw(
                    f"{doctype}.{new_field} must be Data before copy"
                )

            table = f"`tab{doctype}`"
            old_col = f"`{old_field}`"
            new_col = f"`{new_field}`"

            frappe.db.sql(
                f"UPDATE {table} SET {new_col} = {old_col}"
            )

            copied = _hash(doctype, new_field)
            if copied != row["old_hash"]:
                frappe.throw(
                    f"{doctype}: replacement snapshot hash does not match legacy values"
                )

        for row in before["mappings"]:
            custom_field_name = row["old_custom_field"]
            if custom_field_name:
                frappe.delete_doc(
                    "Custom Field",
                    custom_field_name,
                    ignore_permissions=True,
                    force=True,
                )
                frappe.clear_cache(doctype=row["doctype"])

        after = []
        for row in before["mappings"]:
            doctype = row["doctype"]
            old_field = row["old_field"]
            new_field = row["new_field"]

            if _custom_field_name(doctype, old_field):
                frappe.throw(
                    f"{doctype}.{old_field} Custom Field metadata still exists"
                )

            if _meta(doctype, old_field).get("exists"):
                frappe.throw(
                    f"{doctype}.{old_field} remains in runtime metadata"
                )

            new_hash = _hash(doctype, new_field)
            if new_hash != row["old_hash"]:
                frappe.throw(
                    f"{doctype}.{new_field} historical value hash changed"
                )

            after.append(
                {
                    "doctype": doctype,
                    "old_field": old_field,
                    "new_field": new_field,
                    "new_meta": _meta(doctype, new_field),
                    "new_hash": new_hash,
                }
            )

        external_links = _external_legacy_links()
        if external_links:
            frappe.throw(
                "External Link dependencies to legacy tax DocTypes remain: "
                + frappe.as_json(external_links)
            )

        frappe.db.commit()

        return {
            "database_write": True,
            "fbr_network_call": False,
            "copied_values_preserved": True,
            "old_custom_field_metadata_removed": True,
            "external_legacy_links": external_links,
            "before": before,
            "after": after,
        }

    except Exception:
        frappe.db.rollback()
        raise
