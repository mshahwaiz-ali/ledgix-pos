from __future__ import annotations

"""Read-only Phase 1 probe for ERPNext-native tax configuration.

This probe is deliberately restricted to the canonical local integration site.
It performs no configuration writes and never arms or submits FBR.
"""

import frappe

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.services.erpnext_tax_authority import current_tax_authority


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing FBR redesign Phase 1 native-tax probe on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )


def _safe_all(doctype: str, *, fields: list[str], filters=None, order_by=None) -> list[dict]:
    if not frappe.db.exists("DocType", doctype):
        return []
    if not frappe.db.table_exists(doctype, cached=False):
        return []
    return [
        dict(row)
        for row in frappe.get_all(
            doctype,
            fields=fields,
            filters=filters or {},
            order_by=order_by,
            limit_page_length=0,
        )
    ]


def _sales_tax_templates() -> list[dict]:
    rows = _safe_all(
        "Sales Taxes and Charges Template",
        fields=["name", "title", "company", "tax_category", "is_default", "disabled"],
        order_by="company asc, name asc",
    )
    for row in rows:
        child = _safe_all(
            "Sales Taxes and Charges",
            fields=[
                "idx",
                "charge_type",
                "account_head",
                "description",
                "rate",
                "included_in_print_rate",
            ],
            filters={
                "parent": row["name"],
                "parenttype": "Sales Taxes and Charges Template",
            },
            order_by="idx asc",
        )
        row["taxes"] = child
    return rows


def _item_tax_templates() -> list[dict]:
    rows = _safe_all(
        "Item Tax Template",
        fields=["name", "title", "company", "disabled"],
        order_by="company asc, name asc",
    )
    for row in rows:
        row["taxes"] = _safe_all(
            "Item Tax Template Detail",
            fields=["idx", "tax_type", "tax_rate", "not_applicable"],
            filters={
                "parent": row["name"],
                "parenttype": "Item Tax Template",
            },
            order_by="idx asc",
        )
    return rows


def _item_tax_assignments() -> list[dict]:
    return _safe_all(
        "Item Tax",
        fields=[
            "parent",
            "parenttype",
            "item_tax_template",
            "tax_category",
            "valid_from",
            "minimum_net_rate",
            "maximum_net_rate",
        ],
        order_by="parenttype asc, parent asc, idx asc",
    )


def _tax_rules() -> list[dict]:
    return _safe_all(
        "Tax Rule",
        fields=[
            "name",
            "tax_type",
            "company",
            "tax_category",
            "customer",
            "customer_group",
            "item",
            "item_group",
            "sales_tax_template",
            "from_date",
            "to_date",
            "priority",
        ],
        filters={"tax_type": "Sales"},
        order_by="company asc, priority asc, name asc",
    )


def _pos_profiles() -> list[dict]:
    return _safe_all(
        "POS Profile",
        fields=[
            "name",
            "company",
            "disabled",
            "customer",
            "tax_category",
            "taxes_and_charges",
            "selling_price_list",
        ],
        order_by="company asc, name asc",
    )


def _legacy_counts() -> dict:
    doctypes = (
        "Ledgix Tax Profile",
        "Ledgix Tax Category",
        "Ledgix Tax Rate",
        "Ledgix Item Tax Profile",
    )
    counts = {}
    for doctype in doctypes:
        if not frappe.db.exists("DocType", doctype):
            counts[doctype] = 0
            continue
        if not frappe.db.table_exists(doctype, cached=False):
            counts[doctype] = 0
            continue
        counts[doctype] = frappe.db.count(doctype)
    return counts


def run() -> dict:
    _assert_safe_site()

    accounts_settings = {
        "add_taxes_from_taxes_and_charges_template": bool(
            frappe.db.get_single_value(
                "Accounts Settings",
                "add_taxes_from_taxes_and_charges_template",
            )
        ),
        "add_taxes_from_item_tax_template": bool(
            frappe.db.get_single_value(
                "Accounts Settings",
                "add_taxes_from_item_tax_template",
            )
        ),
        "determine_address_tax_category_from": (
            frappe.db.get_single_value(
                "Accounts Settings",
                "determine_address_tax_category_from",
            )
            or ""
        ),
    }

    sales_templates = _sales_tax_templates()
    item_templates = _item_tax_templates()
    assignments = _item_tax_assignments()
    tax_rules = _tax_rules()
    pos_profiles = _pos_profiles()

    active_sales_templates = [row for row in sales_templates if not row.get("disabled")]
    active_item_templates = [row for row in item_templates if not row.get("disabled")]

    account_heads = {
        str(tax.get("account_head") or "")
        for template in active_sales_templates
        for tax in template.get("taxes") or []
        if tax.get("account_head")
    }
    item_tax_accounts = {
        str(tax.get("tax_type") or "")
        for template in active_item_templates
        for tax in template.get("taxes") or []
        if tax.get("tax_type") and not tax.get("not_applicable")
    }

    unmatched_item_tax_accounts = sorted(item_tax_accounts - account_heads)

    return {
        "site": frappe.local.site,
        "read_only": True,
        "fbr_network_calls": 0,
        "source_native_only_cutover": True,
        "current_tax_authority": current_tax_authority(),
        "accounts_settings": accounts_settings,
        "sales_tax_templates": sales_templates,
        "item_tax_templates": item_templates,
        "item_tax_assignments": assignments,
        "sales_tax_rules": tax_rules,
        "pos_profiles": pos_profiles,
        "legacy_counts": _legacy_counts(),
        "summary": {
            "active_sales_tax_templates": len(active_sales_templates),
            "active_item_tax_templates": len(active_item_templates),
            "item_tax_assignments": len(assignments),
            "sales_tax_rules": len(tax_rules),
            "pos_profiles": len(pos_profiles),
            "unmatched_item_tax_accounts": unmatched_item_tax_accounts,
        },
        "native_primitives": {
            "tax_category": bool(frappe.db.exists("DocType", "Tax Category")),
            "tax_rule": bool(frappe.db.exists("DocType", "Tax Rule")),
            "sales_taxes_and_charges_template": bool(
                frappe.db.exists("DocType", "Sales Taxes and Charges Template")
            ),
            "item_tax_template": bool(
                frappe.db.exists("DocType", "Item Tax Template")
            ),
            "on_item_quantity": "On Item Quantity"
            in (
                (
                    frappe.get_meta("Sales Taxes and Charges")
                    .get_field("charge_type")
                    .options
                    or ""
                ).splitlines()
                if frappe.db.exists("DocType", "Sales Taxes and Charges")
                else []
            ),
            "erpnext_taxable_base_resolver_hook_supported_by_pin": True,
        },
    }
