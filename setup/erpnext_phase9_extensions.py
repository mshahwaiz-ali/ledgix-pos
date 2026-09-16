from __future__ import annotations

"""Phase 9 metadata for ERPNext-native FBR source authority.

ERPNext Sales Invoice / POS Invoice remain the transaction authority. Ledgix
owns only FBR transmission/audit metadata and the existing FBR Submission Log.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Ledgix"
FBR_STATUS_OPTIONS = "\n".join(
    [
        "Not Submitted",
        "Not Required",
        "Ready",
        "Pending",
        "Validated",
        "Submitted",
        "Failed",
        "Reconciliation Required",
        "Offline Pending",
        "Skipped",
        "Paused",
        "Manual",
    ]
)


def _cf(fieldname: str, fieldtype: str, label: str = "", **values) -> dict:
    row = {"fieldname": fieldname, "fieldtype": fieldtype, "module": MODULE}
    if label:
        row["label"] = label
    row.update(values)
    return row


def _fbr_runtime_fields() -> list[dict]:
    return [
        _cf(
            "custom_ledgix_fbr_qr_code",
            "Small Text",
            "FBR QR Code",
            insert_after="custom_ledgix_fbr_reference",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_submission_log",
            "Link",
            "FBR Submission Log",
            insert_after="custom_ledgix_fbr_qr_code",
            options="Ledgix FBR Submission Log",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_upload_due_at",
            "Datetime",
            "FBR Upload Due At",
            insert_after="custom_ledgix_fbr_submission_log",
            read_only=1,
            no_copy=1,
        ),
    ]


CUSTOM_FIELDS = {
    "Sales Invoice": _fbr_runtime_fields(),
    "POS Invoice": _fbr_runtime_fields(),
}


def _sync_status_options(doctype: str) -> None:
    field_name = f"{doctype}-custom_ledgix_fbr_status"
    if frappe.db.exists("Custom Field", field_name):
        frappe.db.set_value(
            "Custom Field",
            field_name,
            "options",
            FBR_STATUS_OPTIONS,
            update_modified=False,
        )


def sync_all() -> dict:
    missing = [doctype for doctype in CUSTOM_FIELDS if not frappe.db.exists("DocType", doctype)]
    if missing:
        frappe.throw("Phase 9 FBR schema requires ERPNext DocTypes: " + ", ".join(missing))
    create_custom_fields(CUSTOM_FIELDS, update=True)
    for doctype in CUSTOM_FIELDS:
        _sync_status_options(doctype)
        frappe.clear_cache(doctype=doctype)
    return {
        "doctypes": len(CUSTOM_FIELDS),
        "custom_fields_expected": sum(len(rows) for rows in CUSTOM_FIELDS.values()),
        "status_options": FBR_STATUS_OPTIONS.splitlines(),
    }


def after_migrate() -> None:
    sync_all()
