from __future__ import annotations

"""Small Ledgix-only extensions needed when native ERPNext masters take authority.

Phase 5 deliberately does not copy standard master fields into custom fields. The
fields below only preserve Ledgix product/FBR defaults or one-time provenance
that ERPNext v15 does not model natively.
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
    "Item": [
        _cf(
            "custom_ledgix_master_migration_section",
            "Section Break",
            "Ledgix Migration",
            insert_after="item_code",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_legacy_item",
            "Data",
            "Legacy Ledgix Item",
            insert_after="custom_ledgix_master_migration_section",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_legacy_sku",
            "Data",
            "Legacy SKU",
            insert_after="custom_ledgix_legacy_item",
        ),
        _cf(
            "custom_ledgix_minimum_stock",
            "Float",
            "Legacy Minimum Stock",
            insert_after="custom_ledgix_legacy_sku",
            non_negative=1,
            description="Preserved until a client-specific warehouse reorder policy is configured.",
        ),
    ],
    "Item Group": [
        _cf(
            "custom_ledgix_category_defaults_section",
            "Section Break",
            "Ledgix Category Defaults",
            insert_after="image",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_legacy_category",
            "Data",
            "Legacy Ledgix Category",
            insert_after="custom_ledgix_category_defaults_section",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_category_active",
            "Check",
            "Legacy Category Active",
            insert_after="custom_ledgix_legacy_category",
            default="1",
        ),
        _cf(
            "custom_ledgix_category_description",
            "Small Text",
            "Category Description",
            insert_after="custom_ledgix_category_active",
        ),
        _cf(
            "custom_ledgix_category_icon",
            "Data",
            "Category Icon",
            insert_after="custom_ledgix_category_description",
        ),
        _cf(
            "custom_ledgix_accent_color",
            "Color",
            "Accent Color",
            insert_after="custom_ledgix_category_icon",
        ),
        _cf(
            "custom_ledgix_category_defaults_column",
            "Column Break",
            insert_after="custom_ledgix_accent_color",
        ),
        _cf(
            "custom_ledgix_tax_defaults_enabled",
            "Check",
            "Tax Defaults Enabled",
            insert_after="custom_ledgix_category_defaults_column",
            default="0",
        ),
        _cf(
            "custom_ledgix_default_tax_category",
            "Link",
            "Default Ledgix Tax Category",
            insert_after="custom_ledgix_tax_defaults_enabled",
            options="Ledgix Tax Category",
        ),
        _cf(
            "custom_ledgix_default_taxable",
            "Check",
            "Default Taxable",
            insert_after="custom_ledgix_default_tax_category",
            default="1",
        ),
        _cf(
            "custom_ledgix_default_sales_type",
            "Data",
            "Default FBR Sales Type",
            insert_after="custom_ledgix_default_taxable",
        ),
        _cf(
            "custom_ledgix_default_uom_for_fbr",
            "Data",
            "Default FBR UOM",
            insert_after="custom_ledgix_default_sales_type",
        ),
        _cf(
            "custom_ledgix_default_scenario_id",
            "Data",
            "Default FBR Scenario ID",
            insert_after="custom_ledgix_default_uom_for_fbr",
        ),
    ],
    "Price List": [
        _cf(
            "custom_ledgix_price_list_section",
            "Section Break",
            "Ledgix Retail Defaults",
            insert_after="enabled",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_legacy_price_list",
            "Data",
            "Legacy Ledgix Price List",
            insert_after="custom_ledgix_price_list_section",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_is_default_retail",
            "Check",
            "Default Retail Price List",
            insert_after="custom_ledgix_legacy_price_list",
            default="0",
        ),
        _cf(
            "custom_ledgix_priority",
            "Int",
            "Ledgix Priority",
            insert_after="custom_ledgix_is_default_retail",
            default="0",
        ),
        _cf(
            "custom_ledgix_price_list_notes",
            "Small Text",
            "Ledgix Price List Notes",
            insert_after="custom_ledgix_priority",
        ),
    ],
    "Customer": [
        _cf(
            "custom_ledgix_legacy_customer",
            "Data",
            "Legacy Ledgix Customer",
            insert_after="customer_name",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
    ],
    "Supplier": [
        _cf(
            "custom_ledgix_legacy_supplier",
            "Data",
            "Legacy Ledgix Supplier",
            insert_after="supplier_name",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
    ],
    "Address": [
        _cf(
            "custom_ledgix_legacy_address_source",
            "Data",
            "Legacy Ledgix Address Source",
            insert_after="address_title",
            read_only=1,
            no_copy=1,
        ),
    ],
    "Contact": [
        _cf(
            "custom_ledgix_legacy_contact_source",
            "Data",
            "Legacy Ledgix Contact Source",
            insert_after="first_name",
            read_only=1,
            no_copy=1,
        ),
    ],
    "Mode of Payment": [
        _cf(
            "custom_ledgix_payment_policy_section",
            "Section Break",
            "Ledgix POS Payment Policy",
            insert_after="type",
            collapsible=1,
        ),
        _cf(
            "custom_ledgix_legacy_payment_method",
            "Data",
            "Legacy Ledgix Payment Method",
            insert_after="custom_ledgix_payment_policy_section",
            read_only=1,
            no_copy=1,
            in_standard_filter=1,
        ),
        _cf(
            "custom_ledgix_legacy_method_type",
            "Data",
            "Legacy Method Type",
            insert_after="custom_ledgix_legacy_payment_method",
            read_only=1,
        ),
        _cf(
            "custom_ledgix_sort_order",
            "Int",
            "POS Sort Order",
            insert_after="custom_ledgix_legacy_method_type",
            default="0",
        ),
        _cf(
            "custom_ledgix_requires_reference",
            "Check",
            "Requires Reference",
            insert_after="custom_ledgix_sort_order",
            default="0",
        ),
        _cf(
            "custom_ledgix_allow_change",
            "Check",
            "Allow Change",
            insert_after="custom_ledgix_requires_reference",
            default="0",
        ),
    ],
}


def sync_all() -> dict:
    missing = [doctype for doctype in CUSTOM_FIELDS if not frappe.db.exists("DocType", doctype)]
    if missing:
        frappe.throw("Phase 5 extension schema requires ERPNext DocTypes: " + ", ".join(missing))
    create_custom_fields(CUSTOM_FIELDS, update=True)
    for doctype in CUSTOM_FIELDS:
        frappe.clear_cache(doctype=doctype)
    return {
        "doctypes": len(CUSTOM_FIELDS),
        "custom_fields_expected": sum(len(rows) for rows in CUSTOM_FIELDS.values()),
    }


def after_migrate() -> None:
    sync_all()
