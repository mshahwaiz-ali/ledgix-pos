from __future__ import annotations

"""Ledgix-only metadata for ERPNext-native POS authority in Phase 8.

ERPNext owns POS monetary, payment, stock and shift state. These fields preserve
only Ledgix routing, hold and audit context needed by the retained Ledgix POS UI.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Ledgix"


def _cf(fieldname: str, fieldtype: str, label: str = "", **values) -> dict:
    row = {"fieldname": fieldname, "fieldtype": fieldtype, "module": MODULE}
    if label:
        row["label"] = label
    row.update(values)
    return row


CUSTOM_FIELDS = {
    "POS Invoice": [
        _cf(
            "custom_ledgix_pos_context_section",
            "Section Break",
            "Ledgix POS Context",
            insert_after="custom_ledgix_client_sale_id",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_sale_channel",
            "Select",
            "Sale Channel",
            insert_after="custom_ledgix_pos_context_section",
            options="Retail\nB2B",
            default="Retail",
            read_only=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_checkout_source",
            "Data",
            "Ledgix Checkout Source",
            insert_after="custom_ledgix_sale_channel",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_client_return_id",
            "Data",
            "Ledgix Client Return ID",
            insert_after="custom_ledgix_checkout_source",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_return_reason",
            "Small Text",
            "Ledgix Return Reason",
            insert_after="custom_ledgix_client_return_id",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_hold_id",
            "Data",
            "Ledgix Hold ID",
            insert_after="custom_ledgix_return_reason",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_hold_status",
            "Select",
            "Ledgix Hold Status",
            insert_after="custom_ledgix_hold_id",
            options="\nHeld\nResumed\nCancelled",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_hold_request_json",
            "Long Text",
            "Ledgix Hold Request",
            insert_after="custom_ledgix_hold_status",
            read_only=1,
            no_copy=1,
            description="UI restoration context only; ERPNext draft invoice totals remain authoritative.",
        ),
        _cf(
            "custom_ledgix_price_override_json",
            "Long Text",
            "Ledgix Price Override Audit",
            insert_after="custom_ledgix_hold_request_json",
            read_only=1,
            no_copy=1,
            description="Immutable audit of authorized POS line-rate overrides; ERPNext remains monetary authority.",
        ),
    ],
    "Sales Invoice": [
        _cf(
            "custom_ledgix_hold_id",
            "Data",
            "Ledgix Hold ID",
            insert_after="custom_ledgix_price_override_json",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_hold_status",
            "Select",
            "Ledgix Hold Status",
            insert_after="custom_ledgix_hold_id",
            options="\nHeld\nResumed\nCancelled",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_hold_request_json",
            "Long Text",
            "Ledgix Hold Request",
            insert_after="custom_ledgix_hold_status",
            read_only=1,
            no_copy=1,
            description="UI restoration context only; ERPNext draft invoice totals remain authoritative.",
        ),
    ],
    "POS Opening Entry": [
        _cf(
            "custom_ledgix_opening_notes",
            "Small Text",
            "Ledgix Opening Notes",
            insert_after="pos_profile",
        ),
    ],
    "POS Closing Entry": [
        _cf(
            "custom_ledgix_closing_notes",
            "Small Text",
            "Ledgix Closing Notes",
            insert_after="pos_opening_entry",
        ),
    ],
}


def sync_all() -> dict:
    missing = [doctype for doctype in CUSTOM_FIELDS if not frappe.db.exists("DocType", doctype)]
    if missing:
        frappe.throw("Phase 8 extension schema requires ERPNext DocTypes: " + ", ".join(missing))
    create_custom_fields(CUSTOM_FIELDS, update=True)
    for doctype in CUSTOM_FIELDS:
        frappe.clear_cache(doctype=doctype)
    return {
        "doctypes": len(CUSTOM_FIELDS),
        "custom_fields_expected": sum(len(rows) for rows in CUSTOM_FIELDS.values()),
    }


def after_migrate() -> None:
    sync_all()
