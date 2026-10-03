from __future__ import annotations

"""ERPNext schema owned by the standalone FBR V1 app.

Existing fieldnames are deliberately preserved so an installed Ledgix site can
transition without copying or renaming invoice/customer FBR data.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

CUSTOM_FIELD_MODULE = "FBR V1"
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
            "custom_ledgix_fbr_snapshot_section",
            "Section Break",
            "Immutable FBR Snapshot",
            insert_after="custom_ledgix_fbr_submit_trigger",
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
            "custom_ledgix_fbr_hs_code",
            "Data",
            "HS Code",
            insert_after="custom_ledgix_fbr_snapshot_section",
            read_only=1,
            no_copy=1,
        ),
        _cf(
            "custom_ledgix_fbr_tax_basis",
            "Select",
            "FBR Tax Basis",
            insert_after="custom_ledgix_fbr_hs_code",
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
            "custom_ledgix_fbr_snapshot_version",
            "Int",
            "FBR Line Snapshot Version",
            insert_after="custom_ledgix_fbr_notified_retail_price",
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


CUSTOM_FIELDS = {
    "Customer": CUSTOMER_FBR_FIELDS,
    "Sales Invoice": _invoice_fbr_fields(),
    "POS Invoice": _invoice_fbr_fields(),
    "Sales Invoice Item": _invoice_item_fbr_fields(),
    "POS Invoice Item": _invoice_item_fbr_fields(),
}


# Federal V1 evidence is separate from the retained V2 fields.
for _dt in ("Sales Invoice", "POS Invoice", "Sales Invoice Item", "POS Invoice Item"):
    _fields = CUSTOM_FIELDS[_dt]
    for _name, _type in (("protocol", "Data"), ("hash", "Data")):
        _fields.append(_cf("custom_ledgix_fbr_snapshot_" + _name, _type,
                           "FBR Snapshot " + _name.title(), read_only=1, no_copy=1))
    for _f in _fields:
        if _f["fieldname"].startswith("custom_ledgix_fbr_snapshot_"):
            _f.update(read_only=1, no_copy=1, allow_on_submit=0)
    if not _dt.endswith(" Item"):
        _fields.extend([
            _cf("custom_ledgix_fbr_snapshot_captured_at", "Datetime", "FBR Snapshot Captured At", read_only=1, no_copy=1),
            _cf("custom_ledgix_fbr_pos_device", "Link", "FBR POS Device", options="Ledgix FBR POS Device"),
            _cf("custom_ledgix_fbr_mode_of_payment", "Link", "Fiscal Mode of Payment", options="Mode of Payment"),
            _cf("custom_ledgix_fbr_note_type", "Select", "Fiscal Note Type", options="New\nCredit\nDebit", default="New"),
            _cf("custom_ledgix_fbr_restored_at", "Datetime", "FBR Restoration At", read_only=1, no_copy=1),
        ])
CUSTOM_FIELDS["Mode of Payment"] = [
    _cf("custom_ledgix_fbr_v1_payment_mode", "Select", "Federal V1 Payment Mode",
        options="\n1 - Cash\n2 - Card\n3 - Gift Voucher\n4 - Loyalty Card\n6 - Cheque")
]


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


LEGACY_FISCAL_FIELDS = (
    "custom_ledgix_fbr_extra_tax",
    "custom_ledgix_fbr_fed_payable",
    "custom_ledgix_fbr_further_tax",
    "custom_ledgix_fbr_rate_description",
    "custom_ledgix_fbr_sales_tax_withheld",
    "custom_ledgix_fbr_sales_type",
    "custom_ledgix_fbr_scenario_id",
    "custom_ledgix_fbr_sro_item_serial_number",
    "custom_ledgix_fbr_sro_schedule_number",
    "custom_ledgix_fbr_tax_component_section",
    "custom_ledgix_fbr_uom",
    "custom_ledgix_legacy_fbr_item_profile_snapshot",
    "custom_ledgix_fbr_v2_snapshot_section",
    "custom_ledgix_fbr_v2_snapshot_version",
    "custom_ledgix_fbr_v2_snapshot_hash",
    "custom_ledgix_fbr_v2_snapshot_captured_at",
    "custom_ledgix_fbr_v2_snapshot_json",
    "custom_ledgix_fbr_snapshot_column",
)


def harden_existing_legacy_fields():
    """Update metadata only when present; never create, delete, or clear evidence."""
    changed = 0
    for doctype in ("Sales Invoice", "POS Invoice", "Sales Invoice Item", "POS Invoice Item"):
        for fieldname in LEGACY_FISCAL_FIELDS:
            name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
            if name:
                frappe.db.set_value("Custom Field", name,
                    {"hidden": 1, "read_only": 1, "no_copy": 1, "allow_on_submit": 0},
                    update_modified=False)
                changed += 1
        frappe.clear_cache(doctype=doctype)
    return changed


def sync_custom_fields() -> int:
    missing = [doctype for doctype in CUSTOM_FIELDS if not frappe.db.exists("DocType", doctype)]
    if missing:
        frappe.throw(
            "FBR V1 ERPNext schema cannot be installed; missing DocTypes: "
            + ", ".join(missing)
        )
    create_custom_fields(CUSTOM_FIELDS, update=True)
    harden_existing_legacy_fields()
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
