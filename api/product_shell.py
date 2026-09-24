from __future__ import annotations

"""Ledgix product-shell policy.

This module controls *navigation only*. ERPNext/Frappe permissions remain the
security authority and the business-profile flags do not grant access.
"""

import frappe

from ledgix_saas.setup.erpnext_extensions import get_effective_business_features


LEDGIX_ROLES = ("Ledgix Cashier", "Ledgix Manager", "Ledgix Admin")
ROLE_ORDER = ("cashier", "manager", "admin", "system")

WORKSPACE_CARDS = (
    "Sales & POS",
    "Catalog & Pricing",
    "Purchasing",
    "Inventory & Stock",
    "Reports & Accounting",
    "Tax & FBR",
    "Administration",
)

# Product pages intentionally retained as first-class Ledgix UX. Their business
# data remains ERPNext-authoritative; these shortcuts are navigation only.
WORKSPACE_SHORTCUTS = (
    "Ledgix POS",
    "Inventory Intelligence",
    "Tax & FBR Center",
    "Setup Wizard",
)

# Each entry is UX-only visibility policy. Permissions on the target DocType/Page
# remain authoritative even when a link is visible.
WORKSPACE_LINK_POLICY = {
    "Ledgix POS": {"roles": ROLE_ORDER, "all": ("enable_pos",)},
    "Sales Invoices": {"roles": ROLE_ORDER, "all": ("enable_sales_invoice",)},
    "POS Invoices": {"roles": ROLE_ORDER, "all": ("enable_pos",)},
    "Customers": {"roles": ROLE_ORDER, "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "Payment Entries": {"roles": ROLE_ORDER, "all": ("enable_accounting_workspace",)},
    "POS Openings": {"roles": ("manager", "admin", "system"), "all": ("enable_pos",)},
    "POS Closings": {"roles": ("manager", "admin", "system"), "all": ("enable_pos",)},

    "Items": {"roles": ROLE_ORDER, "any": ("enable_sales_invoice", "enable_pos", "enable_inventory", "enable_buying", "enable_b2b")},
    "Item Groups": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_inventory", "enable_buying", "enable_b2b")},
    "Price Lists": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "Item Prices": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "Pricing Rules": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},

    "Purchase Orders": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Purchase Receipts": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Purchase Invoices": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Suppliers": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},

    "Inventory Intelligence": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Warehouses": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Stock Entries": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},
    "Stock Reconciliation": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},
    "Batches": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},
    "Serial Numbers": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},

    "Sales Report": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos")},
    "Sales Return Report": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos")},
    "Purchase Report": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Customer Statement": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Stock Balance": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Stock Ledger": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Accounts Receivable": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "General Ledger": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Profit and Loss Statement": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},

    "Tax & FBR Center": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "Item Tax Profiles": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "Tax Profile": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "Tax Categories": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "Tax Rates": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "FBR Integration Profiles": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "FBR Submission Logs": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "Tax Audit Logs": {"roles": ("admin", "system"), "all": ("enable_fbr",)},

    "Setup Wizard": {"roles": ("admin", "system")},
    "Business Profile": {"roles": ("admin", "system")},
    "Brand Settings": {"roles": ("admin", "system")},
    "User Profiles": {"roles": ("admin", "system")},
}

CARD_LINKS = {
    "Sales & POS": (
        "Ledgix POS", "Sales Invoices", "POS Invoices", "Customers", "Payment Entries",
        "POS Openings", "POS Closings",
    ),
    "Catalog & Pricing": ("Items", "Item Groups", "Price Lists", "Item Prices", "Pricing Rules"),
    "Purchasing": ("Purchase Orders", "Purchase Receipts", "Purchase Invoices", "Suppliers"),
    "Inventory & Stock": (
        "Inventory Intelligence", "Warehouses", "Stock Entries", "Stock Reconciliation", "Batches", "Serial Numbers",
    ),
    "Reports & Accounting": (
        "Sales Report", "Sales Return Report", "Purchase Report", "Customer Statement", "Stock Balance", "Stock Ledger",
        "Accounts Receivable", "General Ledger", "Profit and Loss Statement",
    ),
    "Tax & FBR": (
        "Tax & FBR Center", "Item Tax Profiles", "Tax Profile", "Tax Categories", "Tax Rates", "FBR Integration Profiles",
        "FBR Submission Logs", "Tax Audit Logs",
    ),
    "Administration": ("Setup Wizard", "Business Profile", "Brand Settings", "User Profiles"),
}


def _role_level(roles: list[str] | tuple[str, ...] | None = None) -> str:
    roles = set(roles or frappe.get_roles())
    if "System Manager" in roles:
        return "system"
    if "Ledgix Admin" in roles:
        return "admin"
    if "Ledgix Manager" in roles:
        return "manager"
    if "Ledgix Cashier" in roles:
        return "cashier"
    return "none"


def _enabled(rule: dict, features: dict, role_level: str) -> bool:
    if role_level not in rule.get("roles", ()):
        return False
    if role_level == "system":
        return True
    if any(not int(features.get(name) or 0) for name in rule.get("all", ())):
        return False
    any_features = rule.get("any", ())
    if any_features and not any(int(features.get(name) or 0) for name in any_features):
        return False
    return True


def build_product_context(*, roles=None, features=None) -> dict:
    features = dict(features or get_effective_business_features())
    role_level = _role_level(roles)
    visible_links = [
        label for label, rule in WORKSPACE_LINK_POLICY.items()
        if _enabled(rule, features, role_level)
    ]
    visible_link_set = set(visible_links)
    visible_cards = [
        card for card, links in CARD_LINKS.items()
        if any(label in visible_link_set for label in links)
    ]
    visible_shortcuts = [
        label for label in WORKSPACE_SHORTCUTS
        if label in visible_link_set
    ]

    if role_level == "cashier" and int(features.get("enable_pos") or 0):
        landing_route = "ledgix-pos"
    else:
        landing_route = "ledgix"

    return {
        **features,
        "role_level": role_level,
        "landing_route": landing_route,
        "curated_sidebar": role_level in {"cashier", "manager", "admin"},
        "visible_workspace_cards": visible_cards,
        "visible_workspace_links": visible_links,
        "visible_workspace_shortcuts": visible_shortcuts,
        "workspace_authority": "ERPNext native forms/lists + retained Ledgix product pages",
    }


def get_product_context() -> dict:
    return build_product_context()


def extend_bootinfo(bootinfo) -> None:
    bootinfo.ledgix_product = get_product_context()


@frappe.whitelist()
def get_current_product_context() -> dict:
    return get_product_context()
