from __future__ import annotations

from collections import OrderedDict

import frappe


COUNT_DOCTYPES = OrderedDict(
    {
        "accounts": "Account",
        "warehouses": "Warehouse",
        "fiscal_years": "Fiscal Year",
        "price_lists": "Price List",
        "modes_of_payment": "Mode of Payment",
        "item_groups": "Item Group",
        "customer_groups": "Customer Group",
        "supplier_groups": "Supplier Group",
        "territories": "Territory",
        "uoms": "UOM",
        "pos_profiles": "POS Profile",
    }
)


def _count(doctype: str) -> int | None:
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def run() -> dict:
    """Read-only preflight for the Phase 2 ERPNext behavioral transaction spike."""

    companies = frappe.get_all(
        "Company",
        fields=["name", "abbr", "default_currency", "country"],
        order_by="name asc",
    )
    default_company = frappe.db.get_single_value("Global Defaults", "default_company")
    counts = OrderedDict((label, _count(doctype)) for label, doctype in COUNT_DOCTYPES.items())

    blockers: list[str] = []
    if not companies:
        blockers.append("no_company")
    if not default_company:
        blockers.append("no_default_company")
    if not counts["accounts"]:
        blockers.append("no_chart_of_accounts")
    if not counts["warehouses"]:
        blockers.append("no_warehouse")
    if not counts["fiscal_years"]:
        blockers.append("no_fiscal_year")
    if not counts["price_lists"]:
        blockers.append("no_price_list")

    return OrderedDict(
        {
            "site": frappe.local.site,
            "installed_apps": frappe.get_installed_apps(),
            "companies": companies,
            "default_company": default_company,
            "counts": counts,
            "ready_for_sales_invoice_spike": not blockers,
            "behavioral_spike_blockers": blockers,
        }
    )
