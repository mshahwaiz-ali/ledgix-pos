from __future__ import annotations

"""ERPNext schema owned by the standalone FBR V1.2 app.

Existing fieldnames are deliberately preserved so an installed Ledgix site can
transition without copying or renaming invoice/customer FBR data.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

CUSTOM_FIELD_MODULE = "FBR V12"
THIRD_SCHEDULE_CHARGE_TYPE = "On Notified Retail Price"
THIRD_SCHEDULE_CHARGE_DOCTYPE = "Sales Taxes and Charges"
THIRD_SCHEDULE_CHARGE_FIELD = "charge_type"

def _cf(fieldname: str, fieldtype: str, label: str = "", **values) -> dict:
    row = {
        "fieldname": fieldname,
        "fieldtype": fieldtype,
        "module": CUSTOM_FIELD_MODULE,
    }
    if label:
        row["label"] = label
    row.update(values)
    return row


CUSTOMER_FBR_FIELDS = [
    _cf(
        "custom_ledgix_fbr_section",
        "Section Break",
        "Ledgix FBR Buyer Details",
        insert_after="tax_id",
        collapsible=1,
    ),
    _cf(
        "custom_ledgix_buyer_registration_type",
        "Select",
        "Buyer Registration Type",
        insert_after="custom_ledgix_fbr_section",
        options="Registered\nUnregistered",
        default="Unregistered",
        in_standard_filter=1,
    ),
    _cf(
        "custom_ledgix_buyer_ntn_cnic",
        "Data",
        "Buyer NTN/CNIC",
        insert_after="custom_ledgix_buyer_registration_type",
        in_standard_filter=1,
    ),
    _cf(
        "custom_ledgix_buyer_strn",
        "Data",
        "Buyer STRN",
        insert_after="custom_ledgix_buyer_ntn_cnic",
    ),
    _cf(
        "custom_ledgix_fbr_column",
        "Column Break",
        insert_after="custom_ledgix_buyer_strn",
    ),
    _cf(
        "custom_ledgix_buyer_province",
        "Data",
        "Buyer Province",
        insert_after="custom_ledgix_fbr_column",
    ),
    _cf(
        "custom_ledgix_buyer_fbr_address",
        "Small Text",
        "Buyer FBR Address",
        insert_after="custom_ledgix_buyer_province",
    ),
    _cf(
        "custom_ledgix_fbr_verification_status",
        "Select",
        "FBR Verification Status",
        insert_after="custom_ledgix_buyer_fbr_address",
        options="Not Checked\nVerified\nFailed\nSkipped",
        default="Not Checked",
        read_only=1,
    ),
    _cf(
        "custom_ledgix_last_fbr_verification_date",
        "Date",
        "Last FBR Verification Date",
        insert_after="custom_ledgix_fbr_verification_status",
        read_only=1,
    ),
]


def _invoice_fbr_fields() -> list[dict]:
    return [
        _cf(
            "custom_ledgix_fbr_section",
            "Section Break",
            "Ledgix FBR",
            insert_after="remarks",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_fbr_status",
            "Select",
            "FBR Status",
            insert_after="custom_ledgix_fbr_section",
            options="Not Submitted\nReady\nSubmitted\nFailed\nReconciliation Required\nManual",
            default="Not Submitted",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_fbr_invoice_number",
            "Data",
            "FBR Invoice Number",
            insert_after="custom_ledgix_fbr_status",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_fbr_reference",
            "Data",
            "FBR Reference",
            insert_after="custom_ledgix_fbr_invoice_number",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_submitted_at",
            "Datetime",
            "FBR Submitted At",
            insert_after="custom_ledgix_fbr_reference",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_column",
            "Column Break",
            insert_after="custom_ledgix_fbr_submitted_at",
        ),
        _cf(
            "custom_ledgix_fbr_error_code",
            "Data",
            "FBR Error Code",
            insert_after="custom_ledgix_fbr_column",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_error_message",
            "Small Text",
            "FBR Error Message",
            insert_after="custom_ledgix_fbr_error_code",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_reconciliation_required",
            "Check",
            "FBR Reconciliation Required",
            insert_after="custom_ledgix_fbr_error_message",
            read_only=1,
            no_copy=1,
            default="0",
        ),
        _cf(
            "custom_ledgix_fbr_submit_trigger",
            "Data",
            "FBR Submit Trigger",
            insert_after="custom_ledgix_fbr_reconciliation_required",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_client_sale_id",
            "Data",
            "Ledgix Client Sale ID",
            insert_after="custom_ledgix_fbr_submit_trigger",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_fbr_snapshot_section",
            "Section Break",
            "Immutable FBR Snapshot",
            insert_after="custom_ledgix_client_sale_id",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_fbr_snapshot_version",
            "Int",
            "FBR Snapshot Version",
            insert_after="custom_ledgix_fbr_snapshot_section",
            read_only=1,
            no_copy=1,
            default="0",
        ),
        _cf(
            "custom_ledgix_fbr_snapshot_json",
            "Long Text",
            "FBR Header Snapshot JSON",
            insert_after="custom_ledgix_fbr_snapshot_version",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
    ]


def _invoice_item_fbr_fields() -> list[dict]:
    return [
        _cf(
            "custom_ledgix_fbr_snapshot_section",
            "Section Break",
            "Ledgix FBR Line Snapshot",
            insert_after="item_tax_template",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_legacy_fbr_item_profile_snapshot",
            "Data",
            "Legacy FBR Item Profile Snapshot",
            insert_after="custom_ledgix_fbr_snapshot_section",
            read_only=1,
            no_copy=1,
            hidden=1,
        ),
        _cf(
            "custom_ledgix_fbr_hs_code",
            "Data",
            "HS Code",
            insert_after="custom_ledgix_legacy_fbr_item_profile_snapshot",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_uom",
            "Data",
            "FBR UOM",
            insert_after="custom_ledgix_fbr_hs_code",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_sales_type",
            "Data",
            "FBR Sales Type",
            insert_after="custom_ledgix_fbr_uom",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_rate_description",
            "Data",
            "FBR Rate Description",
            insert_after="custom_ledgix_fbr_sales_type",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_snapshot_column",
            "Column Break",
            insert_after="custom_ledgix_fbr_rate_description",
        ),
        _cf(
            "custom_ledgix_fbr_scenario_id",
            "Data",
            "FBR Scenario ID",
            insert_after="custom_ledgix_fbr_snapshot_column",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_sro_schedule_number",
            "Data",
            "SRO Schedule Number",
            insert_after="custom_ledgix_fbr_scenario_id",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_sro_item_serial_number",
            "Data",
            "SRO Item Serial Number",
            insert_after="custom_ledgix_fbr_sro_schedule_number",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_tax_basis",
            "Select",
            "FBR Tax Basis",
            insert_after="custom_ledgix_fbr_sro_item_serial_number",
            options="Transaction Value\nNotified Retail Price",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_notified_retail_price",
            "Currency",
            "Notified Retail Price",
            insert_after="custom_ledgix_fbr_tax_basis",
            read_only=1,
            no_copy=1,
            precision="2",
        ),
        _cf(
            "custom_ledgix_fbr_tax_component_section",
            "Section Break",
            "FBR Additional Tax Snapshot",
            insert_after="custom_ledgix_fbr_notified_retail_price",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_fbr_sales_tax_withheld",
            "Currency",
            "Sales Tax Withheld at Source",
            insert_after="custom_ledgix_fbr_tax_component_section",
            read_only=1,
            no_copy=1,
            precision="2",
        ),
        _cf(
            "custom_ledgix_fbr_extra_tax",
            "Currency",
            "Extra Tax",
            insert_after="custom_ledgix_fbr_sales_tax_withheld",
            read_only=1,
            no_copy=1,
            precision="2",
        ),
        _cf(
            "custom_ledgix_fbr_further_tax",
            "Currency",
            "Further Tax",
            insert_after="custom_ledgix_fbr_extra_tax",
            read_only=1,
            no_copy=1,
            precision="2",
        ),
        _cf(
            "custom_ledgix_fbr_fed_payable",
            "Currency",
            "FED Payable",
            insert_after="custom_ledgix_fbr_further_tax",
            read_only=1,
            no_copy=1,
            precision="2",
        ),
        _cf(
            "custom_ledgix_fbr_snapshot_version",
            "Int",
            "FBR Line Snapshot Version",
            insert_after="custom_ledgix_fbr_fed_payable",
            read_only=1,
            no_copy=1,
            default="0",
        ),
        _cf(
            "custom_ledgix_fbr_snapshot_json",
            "Long Text",
            "FBR Line Snapshot JSON",
            insert_after="custom_ledgix_fbr_snapshot_version",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
    ]


def _invoice_fbr_v2_snapshot_fields() -> list[dict]:
    return [
        _cf(
            "custom_ledgix_fbr_v2_snapshot_section",
            "Section Break",
            "FBR V2 Immutable ERPNext Snapshot",
            insert_after="custom_ledgix_fbr_snapshot_json",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_version",
            "Int",
            "FBR V2 Snapshot Version",
            insert_after="custom_ledgix_fbr_v2_snapshot_section",
            read_only=1,
            no_copy=1,
            default="0",
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_hash",
            "Data",
            "FBR V2 Snapshot SHA256",
            insert_after="custom_ledgix_fbr_v2_snapshot_version",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_captured_at",
            "Datetime",
            "FBR V2 Snapshot Captured At",
            insert_after="custom_ledgix_fbr_v2_snapshot_hash",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_json",
            "Long Text",
            "FBR V2 Header Snapshot JSON",
            insert_after="custom_ledgix_fbr_v2_snapshot_captured_at",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
    ]


def _invoice_item_fbr_v2_snapshot_fields() -> list[dict]:
    return [
        _cf(
            "custom_ledgix_fbr_v2_snapshot_section",
            "Section Break",
            "FBR V2 Immutable ERPNext Line Snapshot",
            insert_after="custom_ledgix_fbr_snapshot_json",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_version",
            "Int",
            "FBR V2 Line Snapshot Version",
            insert_after="custom_ledgix_fbr_v2_snapshot_section",
            read_only=1,
            no_copy=1,
            default="0",
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_hash",
            "Data",
            "FBR V2 Line Snapshot SHA256",
            insert_after="custom_ledgix_fbr_v2_snapshot_version",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
        _cf(
            "custom_ledgix_fbr_v2_snapshot_json",
            "Long Text",
            "FBR V2 Line Snapshot JSON",
            insert_after="custom_ledgix_fbr_v2_snapshot_hash",
            read_only=1,
            no_copy=1,
            print_hide=1,
        ),
    ]


CUSTOM_FIELDS = {
    "Customer": CUSTOMER_FBR_FIELDS,
    "Sales Invoice": _invoice_fbr_fields() + _invoice_fbr_v2_snapshot_fields(),
    "POS Invoice": _invoice_fbr_fields() + _invoice_fbr_v2_snapshot_fields(),
    "Sales Invoice Item": _invoice_item_fbr_fields() + _invoice_item_fbr_v2_snapshot_fields(),
    "POS Invoice Item": _invoice_item_fbr_fields() + _invoice_item_fbr_v2_snapshot_fields(),
}



def sync_sales_tax_charge_type_extension() -> dict:
    """Expose the FBR Third Schedule taxable-base charge type without core edits."""

    if not frappe.db.exists("DocType", THIRD_SCHEDULE_CHARGE_DOCTYPE):
        frappe.throw(f"Missing DocType {THIRD_SCHEDULE_CHARGE_DOCTYPE}.")

    base_options = (
        frappe.db.get_value(
            "DocField",
            {
                "parent": THIRD_SCHEDULE_CHARGE_DOCTYPE,
                "fieldname": THIRD_SCHEDULE_CHARGE_FIELD,
            },
            "options",
        )
        or ""
    )
    existing = frappe.db.get_value(
        "Property Setter",
        {
            "doc_type": THIRD_SCHEDULE_CHARGE_DOCTYPE,
            "field_name": THIRD_SCHEDULE_CHARGE_FIELD,
            "property": "options",
        },
        ["name", "value"],
        as_dict=True,
    )

    ordered = []
    for source in (base_options, (existing or {}).get("value") or ""):
        for raw in str(source).splitlines():
            value = raw.strip()
            if value and value not in ordered:
                ordered.append(value)

    if THIRD_SCHEDULE_CHARGE_TYPE not in ordered:
        ordered.append(THIRD_SCHEDULE_CHARGE_TYPE)

    options = "\n" + "\n".join(ordered)
    if existing:
        if str(existing.value or "") != options:
            frappe.db.set_value(
                "Property Setter",
                existing.name,
                "value",
                options,
                update_modified=False,
            )
        setter_name = existing.name
    else:
        setter = make_property_setter(
            THIRD_SCHEDULE_CHARGE_DOCTYPE,
            THIRD_SCHEDULE_CHARGE_FIELD,
            "options",
            options,
            "Text",
        )
        setter_name = setter.name

    setter_meta = frappe.get_meta("Property Setter")
    if setter_meta.has_field("module"):
        if frappe.db.get_value("Property Setter", setter_name, "module") != CUSTOM_FIELD_MODULE:
            frappe.db.set_value(
                "Property Setter",
                setter_name,
                "module",
                CUSTOM_FIELD_MODULE,
                update_modified=False,
            )

    frappe.clear_cache(doctype=THIRD_SCHEDULE_CHARGE_DOCTYPE)
    effective = frappe.get_meta(
        THIRD_SCHEDULE_CHARGE_DOCTYPE,
        cached=False,
    ).get_field(THIRD_SCHEDULE_CHARGE_FIELD)
    if THIRD_SCHEDULE_CHARGE_TYPE not in str(effective.options or "").splitlines():
        frappe.throw(
            f"Failed to register ERPNext charge type {THIRD_SCHEDULE_CHARGE_TYPE}."
        )
    return {
        "property_setter": setter_name,
        "charge_type": THIRD_SCHEDULE_CHARGE_TYPE,
        "effective_options": str(effective.options or ""),
    }


def sync_custom_fields() -> int:
    missing = [doctype for doctype in CUSTOM_FIELDS if not frappe.db.exists("DocType", doctype)]
    if missing:
        frappe.throw(
            "FBR V1.2 ERPNext schema cannot be installed; missing DocTypes: "
            + ", ".join(missing)
        )
    create_custom_fields(CUSTOM_FIELDS, update=True)
    for doctype in CUSTOM_FIELDS:
        frappe.clear_cache(doctype=doctype)
    return sum(len(fields) for fields in CUSTOM_FIELDS.values())


def sync_all() -> dict:
    return {
        "sales_tax_charge_type": sync_sales_tax_charge_type_extension(),
        "custom_fields_expected": sync_custom_fields(),
    }


def after_migrate() -> None:
    sync_all()
