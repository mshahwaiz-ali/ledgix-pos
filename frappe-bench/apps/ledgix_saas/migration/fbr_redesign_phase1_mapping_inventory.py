from __future__ import annotations

from collections import Counter, defaultdict

import frappe

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.migration.fbr_redesign_phase1_native_tax_probe import (
    _item_tax_templates,
    _pos_profiles,
    _sales_tax_templates,
    _safe_all,
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing FBR redesign Phase 1 mapping inventory on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )


def _nonzero(value) -> bool:
    try:
        return abs(float(value or 0)) > 0.000001
    except Exception:
        return False


def run() -> dict:
    # Read-only classification of legacy tax mappings versus ERPNext-native masters.
    _assert_safe_site()

    categories = _safe_all(
        "Ledgix Tax Category",
        fields=[
            "name",
            "category_name",
            "tax_type",
            "default_rate",
            "active",
            "is_exempt",
            "is_zero_rated",
            "description",
        ],
        order_by="category_name asc",
    )

    profiles = _safe_all(
        "Ledgix Item Tax Profile",
        fields=[
            "name",
            "erpnext_item",
            "item",
            "tax_category",
            "taxable",
            "active",
            "needs_review",
            "default_tax_rate",
            "tax_basis",
            "notified_retail_price",
            "hs_code",
            "uom_for_fbr",
            "sales_type",
            "fbr_rate_description",
            "scenario_id",
            "sro_schedule_number",
            "sro_item_serial_number",
            "sales_tax_withheld_at_source_per_unit",
            "extra_tax_per_unit",
            "further_tax_per_unit",
            "fed_payable_per_unit",
        ],
        order_by="tax_category asc, erpnext_item asc, name asc",
    )

    categories_by_name = {row["name"]: row for row in categories}
    active_profiles = [row for row in profiles if int(row.get("active") or 0)]

    duplicate_items = defaultdict(list)
    category_usage = Counter()
    category_items = defaultdict(list)
    signatures = Counter()

    missing_item_links = []
    missing_items = []
    needs_review = []
    third_schedule = []
    special_tax = []
    unknown_category = []

    for row in active_profiles:
        item_code = str(row.get("erpnext_item") or "").strip()
        category_name = str(row.get("tax_category") or "").strip()

        if item_code:
            duplicate_items[item_code].append(row["name"])
            category_items[category_name or "<blank>"].append(item_code)
        else:
            missing_item_links.append(row["name"])

        if item_code and not frappe.db.exists("Item", item_code):
            missing_items.append({"profile": row["name"], "item": item_code})

        if int(row.get("needs_review") or 0):
            needs_review.append(row["name"])

        if str(row.get("tax_basis") or "") == "Notified Retail Price":
            third_schedule.append(
                {
                    "profile": row["name"],
                    "item": item_code,
                    "notified_retail_price": row.get("notified_retail_price") or 0,
                }
            )

        specials = {
            "sales_tax_withheld_at_source_per_unit": (
                row.get("sales_tax_withheld_at_source_per_unit") or 0
            ),
            "extra_tax_per_unit": row.get("extra_tax_per_unit") or 0,
            "further_tax_per_unit": row.get("further_tax_per_unit") or 0,
            "fed_payable_per_unit": row.get("fed_payable_per_unit") or 0,
        }
        has_special = any(_nonzero(value) for value in specials.values())
        if has_special:
            special_tax.append(
                {"profile": row["name"], "item": item_code, **specials}
            )

        category = categories_by_name.get(category_name)
        if category is None:
            unknown_category.append(
                {"profile": row["name"], "category": category_name}
            )
            category_rate = None
            is_exempt = False
            is_zero_rated = False
        else:
            category_rate = float(category.get("default_rate") or 0)
            is_exempt = bool(int(category.get("is_exempt") or 0))
            is_zero_rated = bool(int(category.get("is_zero_rated") or 0))

        signature = (
            category_name,
            bool(int(row.get("taxable") or 0)),
            category_rate,
            is_exempt,
            is_zero_rated,
            str(row.get("tax_basis") or ""),
            has_special,
        )
        signatures[signature] += 1
        category_usage[category_name or "<blank>"] += 1

    duplicate_items = {
        item: names
        for item, names in duplicate_items.items()
        if len(names) > 1
    }

    company = "Ledgix ERPNext Integration"

    company_legacy_tax_account_fields = {}
    if frappe.db.exists("Company", company):
        company_doc = frappe.get_doc("Company", company)
        for fieldname in (
            "custom_ledgix_sales_tax_account",
            "custom_ledgix_extra_tax_account",
            "custom_ledgix_further_tax_account",
            "custom_ledgix_fed_account",
            "custom_ledgix_sales_tax_withheld_account",
        ):
            company_legacy_tax_account_fields[fieldname] = (
                company_doc.get(fieldname) or ""
            )

    gst_account = {}
    if frappe.db.exists("Account", "GST - LEI"):
        gst_account = dict(
            frappe.db.get_value(
                "Account",
                "GST - LEI",
                [
                    "name",
                    "company",
                    "account_type",
                    "root_type",
                    "is_group",
                    "disabled",
                ],
                as_dict=True,
            )
            or {}
        )

    return {
        "site": frappe.local.site,
        "read_only": True,
        "counts": {
            "legacy_categories_total": len(categories),
            "legacy_item_tax_profiles_total": len(profiles),
            "legacy_item_tax_profiles_active": len(active_profiles),
            "missing_erpnext_item_link": len(missing_item_links),
            "missing_erpnext_item_master": len(missing_items),
            "needs_review": len(needs_review),
            "duplicate_active_profiles_per_item": len(duplicate_items),
            "third_schedule_profiles": len(third_schedule),
            "special_tax_profiles": len(special_tax),
            "unknown_category_profiles": len(unknown_category),
        },
        "legacy_categories": categories,
        "category_usage": dict(sorted(category_usage.items())),
        "category_items": {
            key: sorted(values)
            for key, values in sorted(category_items.items())
        },
        "mapping_signatures": [
            {
                "category": signature[0],
                "taxable": signature[1],
                "category_rate": signature[2],
                "is_exempt": signature[3],
                "is_zero_rated": signature[4],
                "tax_basis": signature[5],
                "has_special_per_unit_tax": signature[6],
                "profile_count": count,
            }
            for signature, count in sorted(
                signatures.items(),
                key=lambda entry: str(entry[0]),
            )
        ],
        "exceptions": {
            "missing_item_links": sorted(missing_item_links),
            "missing_items": missing_items,
            "needs_review": sorted(needs_review),
            "duplicate_active_profiles_per_item": dict(
                sorted(duplicate_items.items())
            ),
            "third_schedule": third_schedule,
            "special_tax": special_tax,
            "unknown_category": unknown_category,
        },
        "native_state": {
            "item_tax_templates": _item_tax_templates(),
            "sales_tax_templates": _sales_tax_templates(),
            "gst_account": gst_account,
            "company_legacy_tax_account_fields": company_legacy_tax_account_fields,
            "pos_profiles": _pos_profiles(),
            "accounts_settings": {
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
            },
        },
    }
