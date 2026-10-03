from __future__ import annotations

"""Canonical Phase 3 ERPNext extension schema and Ledgix role mapping.

ERPNext owns standard business masters and transactions. This module adds only
Ledgix-specific compliance/product metadata and role grants. It is intentionally
idempotent so patches and after_migrate can safely call the same synchronizer.
"""

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import setup_custom_perms
from frappe.utils import cint

from ledgix_saas.setup.permissions import PERM_KEYS

CUSTOM_FIELD_MODULE = "Ledgix"
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


# Federal fiscal schema is owned exclusively by fbr_v1.
CUSTOM_FIELDS = {}


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
    """Historical migration compatibility; schema writes belong to fbr_v1."""
    return frappe.get_attr("fbr_v1.setup.erpnext_fbr_schema.sync_sales_tax_charge_type_extension")()


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



def sync_all() -> dict:
    """Synchronize Ledgix-owned ERPNext extensions only.

    FBR custom fields and the Third Schedule charge type are owned by fbr_v1.
    """

    permission_doctypes_changed = sync_erpnext_role_permissions()
    business_profile = sync_business_profile_defaults()
    frappe.clear_cache()
    return {
        "fbr_schema_owner": "fbr_v1",
        "custom_fields_expected": 0,
        "permission_doctypes_changed": permission_doctypes_changed,
        "business_profile": business_profile,
    }


def after_migrate() -> None:
    sync_all()
