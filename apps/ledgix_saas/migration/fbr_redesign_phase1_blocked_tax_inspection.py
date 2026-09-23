from __future__ import annotations

import frappe

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


PROFILE_NAMES = (
    "ITEM-TAX-00006",
    "ITEM-TAX-00007",
    "ITEM-TAX-00008",
    "ITEM-TAX-00009",
    "ITEM-TAX-00010",
    "ITEM-TAX-00012",
    "ITEM-TAX-00091",
    "ITEM-TAX-00092",
    "ITEM-TAX-00093",
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing blocked-tax inspection on {frappe.local.site!r}; "
            f"restricted to {INTEGRATION_SITE!r}."
        )


def _table_exists(doctype: str) -> bool:
    return frappe.db.table_exists(doctype, cached=False)


def run() -> dict:
    _assert_safe_site()

    rows = []

    for profile_name in PROFILE_NAMES:
        if not frappe.db.exists("Ledgix Item Tax Profile", profile_name):
            rows.append({"profile": profile_name, "missing": True})
            continue

        p = frappe.get_doc("Ledgix Item Tax Profile", profile_name)
        item_code = str(p.erpnext_item or "").strip()

        item_state = {}
        if item_code and frappe.db.exists("Item", item_code):
            item = frappe.get_doc("Item", item_code)
            item_state = {
                "name": item.name,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "stock_uom": item.stock_uom,
                "sales_uom": item.sales_uom,
                "disabled": item.disabled,
                "is_stock_item": item.is_stock_item,
                "is_sales_item": item.is_sales_item,
                "standard_rate": item.standard_rate,
                "existing_item_taxes": [
                    {
                        "item_tax_template": row.item_tax_template,
                        "tax_category": row.tax_category or "",
                        "valid_from": row.valid_from,
                        "minimum_net_rate": row.minimum_net_rate,
                        "maximum_net_rate": row.maximum_net_rate,
                    }
                    for row in (item.taxes or [])
                ],
            }

        category_state = {}
        if p.tax_category and frappe.db.exists("Ledgix Tax Category", p.tax_category):
            category = frappe.get_doc("Ledgix Tax Category", p.tax_category)
            category_state = {
                "name": category.name,
                "tax_type": category.tax_type,
                "default_rate": category.default_rate,
                "active": category.active,
                "is_exempt": category.is_exempt,
                "is_zero_rated": category.is_zero_rated,
                "description": category.description,
            }

        v2_mappings = []
        if (
            frappe.db.exists("DocType", "Ledgix FBR Item Mapping")
            and _table_exists("Ledgix FBR Item Mapping")
        ):
            v2_mappings = frappe.get_all(
                "Ledgix FBR Item Mapping",
                filters={"erpnext_item": item_code},
                fields=[
                    "name",
                    "company",
                    "erpnext_item",
                    "active",
                    "needs_review",
                    "effective_from",
                    "effective_to",
                    "hs_code",
                    "fbr_uom",
                    "sales_type",
                    "fbr_rate_description",
                    "tax_basis",
                    "notified_retail_price",
                    "sro_schedule_number",
                    "sro_item_serial_number",
                    "reference_version",
                    "last_reviewed_at",
                    "source_notes",
                ],
                order_by="modified desc",
                limit_page_length=0,
            )

        rows.append(
            {
                "profile": p.name,
                "erpnext_item": item_code,
                "active": p.active,
                "needs_review": p.needs_review,
                "taxable": p.taxable,
                "tax_category": p.tax_category,
                "tax_basis": p.tax_basis,
                "notified_retail_price": p.notified_retail_price,
                "hs_code": p.hs_code,
                "uom_for_fbr": p.uom_for_fbr,
                "sales_type": p.sales_type,
                "fbr_rate_description": p.fbr_rate_description,
                "scenario_id": p.scenario_id,
                "sro_schedule_number": p.sro_schedule_number,
                "sro_item_serial_number": p.sro_item_serial_number,
                "sales_tax_withheld_at_source_per_unit": (
                    p.sales_tax_withheld_at_source_per_unit
                ),
                "extra_tax_per_unit": p.extra_tax_per_unit,
                "further_tax_per_unit": p.further_tax_per_unit,
                "fed_payable_per_unit": p.fed_payable_per_unit,
                "item": item_state,
                "category": category_state,
                "v2_fbr_item_mappings": [dict(row) for row in v2_mappings],
            }
        )

    if len(rows) != 9:
        frappe.throw(f"Expected 9 blocked profiles, inspected {len(rows)}.")

    service_rows = [
        row for row in rows if str(row.get("erpnext_item") or "").startswith("CM-SVC-")
    ]
    fixture_rows = [row for row in rows if row not in service_rows]

    return {
        "site": frappe.local.site,
        "read_only": True,
        "count": len(rows),
        "service_items": service_rows,
        "complex_test_fixtures": fixture_rows,
        "all_blocked_profiles": rows,
    }
