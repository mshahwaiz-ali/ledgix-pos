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
    "Sales Operations",
    "Buying & Suppliers",
    "Catalog & Pricing",
    "Inventory Operations",
    "Stock & Inventory Reports",
    "Financial Statements",
    "Accounting Operations",
    "Reports & Insights",
    "Tax Configuration",
    "FBR & Compliance",
    "Administration",
)

# These labels intentionally match the current Workspace shortcut labels.
WORKSPACE_SHORTCUTS = (
    "Ledgix POS",
    "Sales Invoice",
    "Purchase Invoice",
    "Payment Entry",
    "Profit & Loss",
    "Gross Profit",
    "Balance Sheet",
    "Cash Flow",
    "Accounts Receivable",
    "Accounts Payable",
    "General Ledger",
    "Stock Balance",
)

# Each entry is UX-only visibility policy. Frappe/ERPNext permissions on the
# target DocType/Page/Report remain authoritative even when a link is visible.
WORKSPACE_LINK_POLICY = {
    # Sales & POS
    "Ledgix POS": {"roles": ROLE_ORDER, "all": ("enable_pos",)},
    "Sales Invoices": {"roles": ROLE_ORDER, "all": ("enable_sales_invoice",)},
    "POS Invoices": {"roles": ROLE_ORDER, "all": ("enable_pos",)},
    "Customers": {"roles": ROLE_ORDER, "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},

    # Sales Operations
    "Sales Register": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "POS Openings": {"roles": ("manager", "admin", "system"), "all": ("enable_pos",)},
    "POS Closings": {"roles": ("manager", "admin", "system"), "all": ("enable_pos",)},

    # Buying & Suppliers
    "Purchase Orders": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Purchase Receipts": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Purchase Invoices": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Suppliers": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Purchase Register": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},

    # Catalog & Pricing
    "Items": {"roles": ROLE_ORDER, "any": ("enable_sales_invoice", "enable_pos", "enable_inventory", "enable_buying", "enable_b2b")},
    "Item Groups": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_inventory", "enable_buying", "enable_b2b")},
    "Price Lists": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "Item Prices": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "Pricing Rules": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos", "enable_b2b")},
    "Modes of Payment": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},

    # Inventory Operations
    "Inventory Intelligence": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Warehouses": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Stock Entries": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},
    "Stock Reconciliation": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},
    "Batches": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},
    "Serial Numbers": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory", "enable_advanced_inventory")},

    # Stock & Inventory Reports
    "Stock Balance": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Stock Ledger": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Current Stock": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Low Stock": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},

    # Financial Statements
    "Profit & Loss": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Gross Profit": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Balance Sheet": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Cash Flow": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "General Ledger": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Trial Balance": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},

    # Accounting Operations
    "Accounts Receivable": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Accounts Payable": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Payment Entries": {"roles": ROLE_ORDER, "all": ("enable_accounting_workspace",)},
    "Journal Entries": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},

    # Reports & Insights
    "Sales Report": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos")},
    "Sales Return Report": {"roles": ("manager", "admin", "system"), "any": ("enable_sales_invoice", "enable_pos")},
    "Purchase Report": {"roles": ("manager", "admin", "system"), "all": ("enable_buying",)},
    "Customer Statement": {"roles": ("manager", "admin", "system"), "all": ("enable_accounting_workspace",)},
    "Stock Movement Report": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},
    "Inventory Intelligence Report": {"roles": ("manager", "admin", "system"), "all": ("enable_inventory",)},

    # Tax Configuration
    "Tax Categories": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "Tax Rules": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "Sales Taxes and Charges Templates": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "Item Tax Templates": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "Accounts": {"roles": ("admin", "system"), "all": ("enable_fbr",)},

    # FBR & Compliance
    "Tax & FBR Center": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "FBR Integration Profiles": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "FBR Item Mappings": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "FBR Tax Component Mappings": {"roles": ("admin", "system"), "all": ("enable_fbr",)},
    "FBR Reference Data": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "FBR Sandbox Certifications": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "FBR Submission Logs": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},
    "FBR Correction Requests": {"roles": ("manager", "admin", "system"), "all": ("enable_fbr",)},

    # Administration
    "Setup Wizard": {"roles": ("admin", "system")},
    "Business Profile": {"roles": ("admin", "system")},
    "Brand Settings": {"roles": ("admin", "system")},
    "User Profiles": {"roles": ("admin", "system")},
}

# Shortcut labels are not always identical to card-link labels, so shortcut
# visibility has its own explicit mapping to the same business rules.
WORKSPACE_SHORTCUT_POLICY = {
    "Ledgix POS": WORKSPACE_LINK_POLICY["Ledgix POS"],
    "Sales Invoice": WORKSPACE_LINK_POLICY["Sales Invoices"],
    "Purchase Invoice": WORKSPACE_LINK_POLICY["Purchase Invoices"],
    "Payment Entry": WORKSPACE_LINK_POLICY["Payment Entries"],
    "Profit & Loss": WORKSPACE_LINK_POLICY["Profit & Loss"],
    "Gross Profit": WORKSPACE_LINK_POLICY["Gross Profit"],
    "Balance Sheet": WORKSPACE_LINK_POLICY["Balance Sheet"],
    "Cash Flow": WORKSPACE_LINK_POLICY["Cash Flow"],
    "Accounts Receivable": WORKSPACE_LINK_POLICY["Accounts Receivable"],
    "Accounts Payable": WORKSPACE_LINK_POLICY["Accounts Payable"],
    "General Ledger": WORKSPACE_LINK_POLICY["General Ledger"],
    "Stock Balance": WORKSPACE_LINK_POLICY["Stock Balance"],
}

CARD_LINKS = {
    "Sales & POS": (
        "Ledgix POS", "Sales Invoices", "POS Invoices", "Customers",
    ),
    "Sales Operations": (
        "Sales Register", "POS Openings", "POS Closings",
    ),
    "Buying & Suppliers": (
        "Purchase Orders", "Purchase Receipts", "Purchase Invoices", "Suppliers", "Purchase Register",
    ),
    "Catalog & Pricing": (
        "Items", "Item Groups", "Price Lists", "Item Prices", "Pricing Rules", "Modes of Payment",
    ),
    "Inventory Operations": (
        "Inventory Intelligence", "Warehouses", "Stock Entries", "Stock Reconciliation", "Batches", "Serial Numbers",
    ),
    "Stock & Inventory Reports": (
        "Stock Balance", "Stock Ledger", "Current Stock", "Low Stock",
    ),
    "Financial Statements": (
        "Profit & Loss", "Gross Profit", "Balance Sheet", "Cash Flow", "General Ledger", "Trial Balance",
    ),
    "Accounting Operations": (
        "Accounts Receivable", "Accounts Payable", "Payment Entries", "Journal Entries",
    ),
    "Reports & Insights": (
        "Sales Report", "Sales Return Report", "Purchase Report", "Customer Statement",
        "Stock Movement Report", "Inventory Intelligence Report",
    ),
    "Tax Configuration": (
        "Tax Categories", "Tax Rules", "Sales Taxes and Charges Templates", "Item Tax Templates", "Accounts",
    ),
    "FBR & Compliance": (
        "Tax & FBR Center", "FBR Integration Profiles", "FBR Item Mappings", "FBR Tax Component Mappings",
        "FBR Reference Data", "FBR Sandbox Certifications", "FBR Submission Logs", "FBR Correction Requests",
    ),
    "Administration": (
        "Setup Wizard", "Business Profile", "Brand Settings", "User Profiles",
    ),
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
        label for label, rule in WORKSPACE_SHORTCUT_POLICY.items()
        if _enabled(rule, features, role_level)
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
