from __future__ import annotations

"""Ledgix routing/idempotency metadata for ERPNext-native Phase 7 authority."""

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
    "Purchase Order": [
        _cf("custom_ledgix_phase7_section", "Section Break", "Ledgix Buying Context", insert_after="order_confirmation_no", collapsible=1),
        _cf("custom_ledgix_client_purchase_id", "Data", "Ledgix Client Purchase ID", insert_after="custom_ledgix_phase7_section", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_buying_source", "Data", "Ledgix Buying Source", insert_after="custom_ledgix_client_purchase_id", read_only=1, no_copy=1),
    ],
    "Purchase Receipt": [
        _cf("custom_ledgix_phase7_section", "Section Break", "Ledgix Buying Context", insert_after="remarks", collapsible=1),
        _cf("custom_ledgix_client_purchase_id", "Data", "Ledgix Client Purchase ID", insert_after="custom_ledgix_phase7_section", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_client_receipt_id", "Data", "Ledgix Client Receipt ID", insert_after="custom_ledgix_client_purchase_id", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_buying_source", "Data", "Ledgix Buying Source", insert_after="custom_ledgix_client_receipt_id", read_only=1, no_copy=1),
    ],
    "Purchase Invoice": [
        _cf("custom_ledgix_phase7_section", "Section Break", "Ledgix Buying Context", insert_after="remarks", collapsible=1),
        _cf("custom_ledgix_client_purchase_id", "Data", "Ledgix Client Purchase ID", insert_after="custom_ledgix_phase7_section", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_client_purchase_invoice_id", "Data", "Ledgix Client Purchase Invoice ID", insert_after="custom_ledgix_client_purchase_id", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_buying_source", "Data", "Ledgix Buying Source", insert_after="custom_ledgix_client_purchase_invoice_id", read_only=1, no_copy=1),
    ],
    "Stock Entry": [
        _cf("custom_ledgix_phase7_section", "Section Break", "Ledgix Stock Context", insert_after="remarks", collapsible=1),
        _cf("custom_ledgix_client_stock_id", "Data", "Ledgix Client Stock ID", insert_after="custom_ledgix_phase7_section", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_stock_source", "Data", "Ledgix Stock Source", insert_after="custom_ledgix_client_stock_id", read_only=1, no_copy=1),
    ],
    "Stock Reconciliation": [
        _cf("custom_ledgix_phase7_section", "Section Break", "Ledgix Stock Context", insert_after="purpose", collapsible=1),
        _cf("custom_ledgix_client_stock_reconciliation_id", "Data", "Ledgix Client Reconciliation ID", insert_after="custom_ledgix_phase7_section", read_only=1, no_copy=1, in_standard_filter=1),
        _cf("custom_ledgix_stock_source", "Data", "Ledgix Stock Source", insert_after="custom_ledgix_client_stock_reconciliation_id", read_only=1, no_copy=1),
    ],
}


def schema_ready() -> bool:
    return all(
        frappe.get_meta(doctype).has_field(field["fieldname"])
        for doctype, fields in CUSTOM_FIELDS.items()
        for field in fields
    )


def sync_custom_fields() -> None:
    create_custom_fields(CUSTOM_FIELDS, update=True)
    for doctype in CUSTOM_FIELDS:
        frappe.clear_cache(doctype=doctype)


def sync_all() -> dict:
    already_ready = schema_ready()
    if not already_ready:
        sync_custom_fields()
    return {
        "doctypes": len(CUSTOM_FIELDS),
        "custom_fields": sum(len(rows) for rows in CUSTOM_FIELDS.values()),
        "already_ready": already_ready,
    }


def after_migrate() -> None:
    sync_custom_fields()
