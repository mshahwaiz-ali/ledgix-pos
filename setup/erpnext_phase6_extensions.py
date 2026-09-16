from __future__ import annotations

"""Ledgix-only metadata for native ERPNext selling/payment authority.

Phase 6 must not duplicate ERPNext monetary fields. These extensions only keep
Ledgix routing/idempotency/audit context that ERPNext does not model as a product
concept by default.
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
    "Sales Invoice": [
        _cf(
            "custom_ledgix_selling_context_section",
            "Section Break",
            "Ledgix Selling Context",
            insert_after="custom_ledgix_client_sale_id",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_sale_channel",
            "Select",
            "Sale Channel",
            insert_after="custom_ledgix_selling_context_section",
            options="Retail\nB2B",
            read_only=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_client_return_id",
            "Data",
            "Ledgix Client Return ID",
            insert_after="custom_ledgix_sale_channel",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_exchange_reference",
            "Data",
            "Ledgix Exchange Reference",
            insert_after="custom_ledgix_client_return_id",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_checkout_source",
            "Data",
            "Ledgix Checkout Source",
            insert_after="custom_ledgix_exchange_reference",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_price_override_json",
            "Long Text",
            "Ledgix Price Override Audit",
            insert_after="custom_ledgix_checkout_source",
            read_only=1,
            no_copy=1,
            allow_on_submit=1,
            description=(
                "Immutable compatibility audit of authorized manual B2B line-rate overrides. "
                "ERPNext rate/price fields remain the monetary authority."
            ),
        ),
    ],
    "Payment Entry": [
        _cf(
            "custom_ledgix_payment_context_section",
            "Section Break",
            "Ledgix Payment Context",
            insert_after="mode_of_payment",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_client_payment_id",
            "Data",
            "Ledgix Client Payment ID",
            insert_after="custom_ledgix_payment_context_section",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_payment_source",
            "Data",
            "Ledgix Payment Source",
            insert_after="custom_ledgix_client_payment_id",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_reversal_reason",
            "Small Text",
            "Ledgix Cancellation / Reversal Reason",
            insert_after="custom_ledgix_payment_source",
            read_only=1,
            no_copy=1,
            allow_on_submit=1,
        ),
    ],
}


def schema_ready() -> bool:
    for doctype, fields in CUSTOM_FIELDS.items():
        meta = frappe.get_meta(doctype)
        for field in fields:
            if not meta.has_field(field["fieldname"]):
                return False
    return True


def sync_custom_fields() -> None:
    create_custom_fields(CUSTOM_FIELDS, update=True)
    frappe.clear_cache(doctype="Sales Invoice")
    frappe.clear_cache(doctype="Payment Entry")


def sync_all() -> dict:
    already_ready = schema_ready()
    if not already_ready:
        sync_custom_fields()
    return {
        "sales_invoice_fields": len(CUSTOM_FIELDS["Sales Invoice"]),
        "payment_entry_fields": len(CUSTOM_FIELDS["Payment Entry"]),
        "already_ready": already_ready,
    }


def after_migrate() -> None:
    # Migrate is the authoritative place for schema installation/update. Force
    # update here so changed labels/options/read-only flags are applied too.
    sync_custom_fields()
