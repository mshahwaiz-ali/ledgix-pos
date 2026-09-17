from __future__ import annotations

"""Local-only hygiene and fiscal prerequisites for the retail operating dataset.

This module is deliberately conservative: it only removes artifacts carrying
known Ledgix demo/spike names or markers, and it never runs on non-.local sites.
"""

from datetime import timedelta

import frappe
from dateutil.relativedelta import relativedelta
from frappe.utils import getdate

from ledgix_saas.setup import erpnext_demo_data as native

OLD_SEED = "LEDGIX-ERP-DEMO-V2"
OLD_ITEM_PREFIX = "LXD-"
OLD_POS_PROFILES = ("Ledgix Demo POS", "Ledgix ERPNext POS Spike")
OLD_PRICE_LISTS = ("Ledgix Demo Retail", "Ledgix Demo Wholesale", "Ledgix Demo Buying")
OLD_WAREHOUSES = ("Ledgix Demo Main Store", "Ledgix Demo POS Floor", "Ledgix Demo Back Store")
OLD_ITEM_GROUPS = (
    "Demo Bakery",
    "Demo Beverages",
    "Demo Grocery",
    "Demo Home & Personal",
    "Demo Electronics",
    "Demo Services",
)
OLD_CUSTOMER_GROUPS = ("Demo Retail", "Demo Trade")
OLD_SUPPLIER_GROUPS = ("Demo Suppliers",)
OLD_TAX_CATEGORIES = ("Ledgix Demo Standard Tax",)
OLD_ONLY_CUSTOMERS = (
    "Greenline Offices",
    "Morning Table Cafe",
    "Northgate Hostel Mess",
    "Urban Crust Cafe",
    "Sapphire Event Studio",
    "Central Learning Academy",
)
OLD_ONLY_SUPPLIERS = (
    "Heritage Food Supply Co.",
    "BlueRiver Beverage Distribution",
    "FreshFields Grocery Supply",
    "PackPro Retail Supplies",
    "Nova Small Appliances",
    "City Wholesale Traders",
)


def _applies_to_company(fiscal_year: str, company: str) -> bool:
    companies = frappe.get_all(
        "Fiscal Year Company",
        filters={"parent": fiscal_year},
        pluck="company",
        limit_page_length=0,
    )
    return not companies or company in companies


def _covering_fiscal_year(date_value, company: str):
    rows = frappe.get_all(
        "Fiscal Year",
        filters={
            "disabled": 0,
            "year_start_date": ["<=", date_value],
            "year_end_date": [">=", date_value],
        },
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date desc",
        limit_page_length=0,
    )
    return next((row for row in rows if _applies_to_company(row.name, company)), None)


def _create_company_fiscal_year(company: str, start_date, end_date) -> str:
    start_date = getdate(start_date)
    end_date = getdate(end_date)
    existing = _covering_fiscal_year(start_date, company)
    if existing and getdate(existing.year_end_date) >= end_date:
        return existing.name

    abbr = frappe.db.get_value("Company", company, "abbr") or "LOCAL"
    label = f"Local Retail FY {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d} {abbr}"
    if frappe.db.exists("Fiscal Year", label):
        return label

    doc = frappe.get_doc(
        {
            "doctype": "Fiscal Year",
            "year": label,
            "year_start_date": start_date,
            "year_end_date": end_date,
            "disabled": 0,
            "companies": [{"company": company}],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_fiscal_year_window(company: str, required_start, required_end) -> dict:
    """Ensure every date in the local seed window belongs to an active FY."""
    native._local_only()
    required_start = getdate(required_start)
    required_end = getdate(required_end)
    created: list[str] = []

    end_fy = _covering_fiscal_year(required_end, company)
    if end_fy:
        cursor_start = getdate(end_fy.year_start_date)
        while required_start < cursor_start:
            previous_end = cursor_start - timedelta(days=1)
            previous_start = cursor_start - relativedelta(years=1)
            if not _covering_fiscal_year(previous_end, company):
                created.append(
                    _create_company_fiscal_year(company, previous_start, previous_end)
                )
            cursor_start = previous_start
    else:
        # Fallback only for an unusually bare local site: create calendar years
        # covering the requested window for this company.
        for year in range(required_start.year, required_end.year + 1):
            start = getdate(f"{year}-01-01")
            end = getdate(f"{year}-12-31")
            if not _covering_fiscal_year(start, company):
                created.append(_create_company_fiscal_year(company, start, end))

    if not _covering_fiscal_year(required_start, company):
        frappe.throw(
            f"Could not provision an active Fiscal Year covering {required_start} for {company}."
        )
    if not _covering_fiscal_year(required_end, company):
        frappe.throw(
            f"Could not provision an active Fiscal Year covering {required_end} for {company}."
        )
    return {"created_fiscal_years": created}


def _cancel_delete(doctype: str, name: str, removed: list[str], archived: list[str]) -> None:
    if not frappe.db.exists(doctype, name):
        return
    try:
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            doc.cancel()
        doc.delete(ignore_permissions=True)
        removed.append(f"{doctype}:{name}")
    except Exception:
        # Do not turn a known old artifact into a seed blocker solely because
        # ERPNext retains historical links. Hide it when the DocType supports it.
        frappe.db.rollback(save_point="old_artifact")
        if frappe.get_meta(doctype).has_field("disabled"):
            frappe.db.set_value(doctype, name, "disabled", 1, update_modified=False)
            archived.append(f"{doctype}:{name}")
        else:
            archived.append(f"linked:{doctype}:{name}")


def _delete_marker_transactions(seed: str, removed: list[str], archived: list[str]) -> None:
    openings = frappe.get_all(
        "POS Opening Entry",
        filters={"custom_ledgix_opening_notes": ["like", f"%{seed}%"]},
        pluck="name",
        limit_page_length=0,
    )
    selectors = (
        ("Payment Entry", "custom_ledgix_client_payment_id"),
        ("POS Invoice", "custom_ledgix_client_return_id"),
        ("Sales Invoice", "custom_ledgix_client_return_id"),
        ("POS Invoice", "custom_ledgix_client_sale_id"),
        ("Sales Invoice", "custom_ledgix_client_sale_id"),
        ("Purchase Invoice", "custom_ledgix_client_purchase_invoice_id"),
        ("Purchase Receipt", "custom_ledgix_client_receipt_id"),
        ("Purchase Order", "custom_ledgix_client_purchase_id"),
        ("Stock Reconciliation", "custom_ledgix_client_stock_reconciliation_id"),
        ("Stock Entry", "custom_ledgix_client_stock_id"),
    )
    for doctype, fieldname in selectors:
        if not frappe.get_meta(doctype).has_field(fieldname):
            continue
        names = frappe.get_all(
            doctype,
            filters={fieldname: ["like", f"{seed}-%"]},
            pluck="name",
            order_by="creation desc",
            limit_page_length=0,
        )
        for name in names:
            frappe.db.savepoint("old_artifact")
            _cancel_delete(doctype, name, removed, archived)

    if openings:
        closings = frappe.get_all(
            "POS Closing Entry",
            filters={"pos_opening_entry": ["in", openings]},
            pluck="name",
            limit_page_length=0,
        )
        for name in closings:
            frappe.db.savepoint("old_artifact")
            _cancel_delete("POS Closing Entry", name, removed, archived)
        for name in openings:
            frappe.db.savepoint("old_artifact")
            _cancel_delete("POS Opening Entry", name, removed, archived)


def _cleanup_spike_profiles(removed: list[str], archived: list[str]) -> None:
    for profile in OLD_POS_PROFILES:
        if not frappe.db.exists("POS Profile", profile):
            continue
        openings = frappe.get_all(
            "POS Opening Entry",
            filters={"pos_profile": profile},
            pluck="name",
            limit_page_length=0,
        )
        if openings:
            closings = frappe.get_all(
                "POS Closing Entry",
                filters={"pos_opening_entry": ["in", openings]},
                pluck="name",
                limit_page_length=0,
            )
            for name in closings:
                frappe.db.savepoint("old_artifact")
                _cancel_delete("POS Closing Entry", name, removed, archived)
        invoices = frappe.get_all(
            "POS Invoice",
            filters={"pos_profile": profile},
            pluck="name",
            order_by="creation desc",
            limit_page_length=0,
        )
        for name in invoices:
            frappe.db.savepoint("old_artifact")
            _cancel_delete("POS Invoice", name, removed, archived)
        for name in openings:
            frappe.db.savepoint("old_artifact")
            _cancel_delete("POS Opening Entry", name, removed, archived)
        frappe.db.savepoint("old_artifact")
        _cancel_delete("POS Profile", profile, removed, archived)


def cleanup_old_local_artifacts() -> dict:
    """Remove/hide only known previous Ledgix demo/spike artifacts."""
    native._local_only()
    old_user = frappe.session.user or "Administrator"
    frappe.set_user("Administrator")
    removed: list[str] = []
    archived: list[str] = []
    try:
        _delete_marker_transactions(OLD_SEED, removed, archived)
        _cleanup_spike_profiles(removed, archived)

        # Remove old item-specific extension rows and prices before masters.
        for name in frappe.get_all(
            "Ledgix Item Tax Profile",
            filters={"erpnext_item": ["like", f"{OLD_ITEM_PREFIX}%"]},
            pluck="name",
            limit_page_length=0,
        ):
            frappe.db.delete("Ledgix Item Tax Profile", {"name": name})
            removed.append(f"Ledgix Item Tax Profile:{name}")
        frappe.db.delete("Item Price", {"item_code": ["like", f"{OLD_ITEM_PREFIX}%"]})

        for name in frappe.get_all(
            "Item",
            filters={"item_code": ["like", f"{OLD_ITEM_PREFIX}%"]},
            pluck="name",
            limit_page_length=0,
        ):
            frappe.db.savepoint("old_artifact")
            _cancel_delete("Item", name, removed, archived)

        for doctype, names in (
            ("Customer", OLD_ONLY_CUSTOMERS),
            ("Supplier", OLD_ONLY_SUPPLIERS),
            ("Warehouse", OLD_WAREHOUSES),
            ("Price List", OLD_PRICE_LISTS),
            ("Item Group", OLD_ITEM_GROUPS),
            ("Customer Group", OLD_CUSTOMER_GROUPS),
            ("Supplier Group", OLD_SUPPLIER_GROUPS),
            ("Ledgix Tax Category", OLD_TAX_CATEGORIES),
        ):
            for name in names:
                if frappe.db.exists(doctype, name):
                    frappe.db.savepoint("old_artifact")
                    _cancel_delete(doctype, name, removed, archived)

        frappe.db.commit()
        return {"removed": removed, "archived": archived}
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(old_user)


def visible_old_artifacts() -> list[str]:
    """Return only old artifacts that are still active/visible after cleanup."""
    native._local_only()
    leftovers: list[str] = []
    for name in frappe.get_all(
        "Item",
        filters={"item_code": ["like", f"{OLD_ITEM_PREFIX}%"], "disabled": 0},
        pluck="name",
        limit_page_length=0,
    ):
        leftovers.append(f"Item:{name}")
    for doctype, names in (
        ("POS Profile", OLD_POS_PROFILES),
        ("Warehouse", OLD_WAREHOUSES),
        ("Price List", OLD_PRICE_LISTS),
    ):
        meta = frappe.get_meta(doctype)
        for name in names:
            if not frappe.db.exists(doctype, name):
                continue
            if meta.has_field("disabled") and frappe.db.get_value(doctype, name, "disabled"):
                continue
            if meta.has_field("enabled") and not frappe.db.get_value(doctype, name, "enabled"):
                continue
            leftovers.append(f"{doctype}:{name}")
    return leftovers


__all__ = [
    "ensure_fiscal_year_window",
    "cleanup_old_local_artifacts",
    "visible_old_artifacts",
]
