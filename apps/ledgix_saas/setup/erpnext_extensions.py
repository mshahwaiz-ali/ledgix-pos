from __future__ import annotations

"""Canonical Phase 3 ERPNext extension schema and Ledgix role mapping.

ERPNext owns standard business masters and transactions. This module adds only
Ledgix-specific compliance/product metadata and role grants. It is intentionally
idempotent so patches and after_migrate can safely call the same synchronizer.
"""

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.permissions import setup_custom_perms
from frappe.utils import cint

from ledgix_saas.setup.permissions import PERM_KEYS

CUSTOM_FIELD_MODULE = "Ledgix"
THIRD_SCHEDULE_CHARGE_TYPE = "On Notified Retail Price"
THIRD_SCHEDULE_CHARGE_DOCTYPE = "Sales Taxes and Charges"
THIRD_SCHEDULE_CHARGE_FIELD = "charge_type"
LEDGIX_ROLES = ("Ledgix Cashier", "Ledgix Manager", "Ledgix Admin")
DEFAULT_BUSINESS_PROFILE = "Small Retail"
FEATURE_FIELDS = (
    "enable_sales_invoice",
    "enable_pos",
    "enable_inventory",
    "enable_buying",
    "enable_advanced_inventory",
    "enable_b2b",
    "enable_fbr",
    "enable_accounting_workspace",
)

PROFILE_DEFAULTS = {
    "Invoice + FBR Only": {
        "enable_sales_invoice": 1,
        "enable_pos": 0,
        "enable_inventory": 0,
        "enable_buying": 0,
        "enable_advanced_inventory": 0,
        "enable_b2b": 0,
        "enable_fbr": 1,
        "enable_accounting_workspace": 1,
    },
    "Small Retail": {
        "enable_sales_invoice": 1,
        "enable_pos": 1,
        "enable_inventory": 1,
        "enable_buying": 1,
        "enable_advanced_inventory": 0,
        "enable_b2b": 0,
        "enable_fbr": 1,
        "enable_accounting_workspace": 1,
    },
    "Full Retail": {
        "enable_sales_invoice": 1,
        "enable_pos": 1,
        "enable_inventory": 1,
        "enable_buying": 1,
        "enable_advanced_inventory": 1,
        "enable_b2b": 0,
        "enable_fbr": 1,
        "enable_accounting_workspace": 1,
    },
    "B2B": {
        "enable_sales_invoice": 1,
        "enable_pos": 0,
        "enable_inventory": 0,
        "enable_buying": 0,
        "enable_advanced_inventory": 0,
        "enable_b2b": 1,
        "enable_fbr": 1,
        "enable_accounting_workspace": 1,
    },
    "Mixed": {
        "enable_sales_invoice": 1,
        "enable_pos": 1,
        "enable_inventory": 1,
        "enable_buying": 1,
        "enable_advanced_inventory": 1,
        "enable_b2b": 1,
        "enable_fbr": 1,
        "enable_accounting_workspace": 1,
    },
}


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
            "custom_ledgix_fbr_item_profile",
            "Link",
            "FBR Item Profile",
            insert_after="custom_ledgix_fbr_snapshot_section",
            options="Ledgix Item Tax Profile",
            read_only=1,
            no_copy=1,
            hidden=1,
        ),
        _cf(
            "custom_ledgix_fbr_hs_code",
            "Data",
            "HS Code",
            insert_after="custom_ledgix_fbr_item_profile",
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


CUSTOM_FIELDS = {
    "Customer": CUSTOMER_FBR_FIELDS,
    "Sales Invoice": _invoice_fbr_fields(),
    "POS Invoice": _invoice_fbr_fields(),
    "Sales Invoice Item": _invoice_item_fbr_fields(),
    "POS Invoice Item": _invoice_item_fbr_fields(),
}


def _perm(**values) -> dict:
    row = {key: 0 for key in PERM_KEYS}
    row.update(values)
    return row


def _read(report: bool = False) -> dict:
    return _perm(read=1, print=1, report=1 if report else 0, export=1 if report else 0)


def _master(admin: bool = False) -> dict:
    return _perm(
        read=1,
        write=1,
        create=1,
        delete=1 if admin else 0,
        report=1,
        export=1,
        print=1,
        email=1,
    )


def _transaction(*, admin: bool = False, cancel: bool = False) -> dict:
    return _perm(
        read=1,
        write=1,
        create=1,
        delete=1 if admin else 0,
        submit=1,
        cancel=1 if cancel else 0,
        amend=1 if cancel else 0,
        report=1,
        export=1,
        print=1,
        email=1,
    )


# These are additive Custom DocPerm grants. ERPNext's own standard roles remain
# untouched; setup_custom_perms copies the native policy once and we only manage
# the three Ledgix roles below.
ERPNext_ROLE_PERMISSIONS = {
    "Company": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _read(report=True),
    },
    "Account": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(report=True),
        "Ledgix Admin": _read(report=True),
    },
    "Cost Center": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
    "Item": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Item Group": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "UOM": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Price List": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Item Price": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Pricing Rule": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Customer": {
        "Ledgix Cashier": _master(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Customer Group": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
    "Territory": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
    "Address": {
        "Ledgix Cashier": _master(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Contact": {
        "Ledgix Cashier": _master(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Supplier": {
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Supplier Group": {
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
    "Mode of Payment": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
    "Sales Invoice": {
        "Ledgix Cashier": _transaction(),
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "POS Invoice": {
        "Ledgix Cashier": _transaction(),
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Payment Entry": {
        "Ledgix Cashier": _transaction(),
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Purchase Order": {
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Purchase Receipt": {
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Purchase Invoice": {
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Warehouse": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "Stock Entry": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Stock Reconciliation": {
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Stock Ledger Entry": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(report=True),
        "Ledgix Admin": _read(report=True),
    },
    "Batch": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(report=True),
        "Ledgix Admin": _master(admin=True),
    },
    "Serial No": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(report=True),
        "Ledgix Admin": _master(admin=True),
    },
    "Serial and Batch Bundle": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(report=True),
        "Ledgix Admin": _read(report=True),
    },
    "POS Profile": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _master(),
        "Ledgix Admin": _master(admin=True),
    },
    "POS Opening Entry": {
        "Ledgix Cashier": _transaction(),
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "POS Closing Entry": {
        "Ledgix Cashier": _transaction(),
        "Ledgix Manager": _transaction(cancel=True),
        "Ledgix Admin": _transaction(admin=True, cancel=True),
    },
    "Tax Category": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
    "Item Tax Template": {
        "Ledgix Cashier": _read(),
        "Ledgix Manager": _read(),
        "Ledgix Admin": _master(admin=True),
    },
}


def apply_business_profile_defaults(doc) -> None:
    profile = doc.get("business_profile") or DEFAULT_BUSINESS_PROFILE
    if profile not in PROFILE_DEFAULTS:
        frappe.throw(f"Unsupported Ledgix Business Profile: {profile}")
    doc.business_profile = profile
    for fieldname, value in PROFILE_DEFAULTS[profile].items():
        doc.set(fieldname, value)


def get_effective_business_features() -> dict:
    if not frappe.db.exists("DocType", "Ledgix Business Profile"):
        defaults = PROFILE_DEFAULTS[DEFAULT_BUSINESS_PROFILE]
        return {"business_profile": DEFAULT_BUSINESS_PROFILE, **defaults}

    doc = frappe.get_single("Ledgix Business Profile")
    profile = doc.get("business_profile") or DEFAULT_BUSINESS_PROFILE
    return {
        "business_profile": profile,
        **{fieldname: cint(doc.get(fieldname)) for fieldname in FEATURE_FIELDS},
    }



def sync_sales_tax_charge_type_extension() -> dict:
    """Expose the ERPNext custom taxable-base charge type without core edits."""

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
        frappe.throw("ERPNext extension schema cannot be installed; missing DocTypes: " + ", ".join(missing))

    create_custom_fields(CUSTOM_FIELDS, update=True)
    return sum(len(fields) for fields in CUSTOM_FIELDS.values())


def _new_custom_perm(doctype: str, role: str, desired: dict) -> None:
    values = {key: cint(desired.get(key, 0)) for key in PERM_KEYS}
    frappe.get_doc(
        {
            "doctype": "Custom DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            "permlevel": 0,
            "if_owner": 0,
            **values,
        }
    ).insert(ignore_permissions=True)


def sync_erpnext_role_permissions() -> int:
    changed_doctypes = 0
    for doctype, desired_by_role in ERPNext_ROLE_PERMISSIONS.items():
        if not frappe.db.exists("DocType", doctype):
            continue

        setup_custom_perms(doctype)
        current_rows = frappe.get_all(
            "Custom DocPerm",
            filters={"parent": doctype, "permlevel": 0, "if_owner": 0},
            fields=["name", "role", *PERM_KEYS],
        )
        current_by_role = {row.role: row for row in current_rows}
        changed = False

        for role, desired in desired_by_role.items():
            if not frappe.db.exists("Role", role):
                continue
            current = current_by_role.get(role)
            if not current:
                _new_custom_perm(doctype, role, desired)
                changed = True
                continue

            updates = {
                key: cint(desired.get(key, 0))
                for key in PERM_KEYS
                if cint(current.get(key, 0)) != cint(desired.get(key, 0))
            }
            if updates:
                frappe.db.set_value("Custom DocPerm", current.name, updates, update_modified=False)
                changed = True

        if changed:
            validate_permissions_for_doctype(doctype)
            frappe.clear_cache(doctype=doctype)
            changed_doctypes += 1

    return changed_doctypes


def sync_business_profile_defaults() -> str:
    if not frappe.db.exists("DocType", "Ledgix Business Profile"):
        return ""

    doc = frappe.get_single("Ledgix Business Profile")
    changed = False
    if not doc.get("business_profile"):
        doc.business_profile = DEFAULT_BUSINESS_PROFILE
        changed = True
    if doc.get("use_profile_defaults") is None:
        doc.use_profile_defaults = 1
        changed = True
    if cint(doc.get("use_profile_defaults")):
        before = {fieldname: cint(doc.get(fieldname)) for fieldname in FEATURE_FIELDS}
        apply_business_profile_defaults(doc)
        after = {fieldname: cint(doc.get(fieldname)) for fieldname in FEATURE_FIELDS}
        changed = changed or before != after
    if changed:
        doc.save(ignore_permissions=True)
    return doc.business_profile


def backfill_erpnext_item_profile_links() -> int:
    if not frappe.db.exists("DocType", "Ledgix Item Tax Profile"):
        return 0
    meta = frappe.get_meta("Ledgix Item Tax Profile", cached=False)
    if not meta.has_field("erpnext_item"):
        return 0

    updated = 0
    for row in frappe.get_all(
        "Ledgix Item Tax Profile",
        fields=["name", "item", "erpnext_item"],
    ):
        if row.erpnext_item or not row.item:
            continue
        legacy_code = row.item
        if frappe.db.exists("DocType", "Ledgix Item") and frappe.db.exists("Ledgix Item", row.item):
            legacy_code = frappe.db.get_value("Ledgix Item", row.item, "item_code") or row.item
        if frappe.db.exists("Item", legacy_code):
            frappe.db.set_value(
                "Ledgix Item Tax Profile",
                row.name,
                "erpnext_item",
                legacy_code,
                update_modified=False,
            )
            updated += 1
    return updated


def sync_all() -> dict:
    """Install/update the Phase 3 contract without creating duplicate masters."""

    sales_tax_charge_type = sync_sales_tax_charge_type_extension()
    custom_field_count = sync_custom_fields()
    permission_doctypes_changed = sync_erpnext_role_permissions()
    business_profile = sync_business_profile_defaults()
    backfilled_profiles = backfill_erpnext_item_profile_links()
    frappe.clear_cache()
    return {
        "sales_tax_charge_type": sales_tax_charge_type,
        "custom_fields_expected": custom_field_count,
        "permission_doctypes_changed": permission_doctypes_changed,
        "business_profile": business_profile,
        "item_tax_profiles_backfilled": backfilled_profiles,
    }


def after_migrate() -> None:
    sync_all()
