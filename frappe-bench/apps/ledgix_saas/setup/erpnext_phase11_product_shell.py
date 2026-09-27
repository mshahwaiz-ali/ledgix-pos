from __future__ import annotations

"""Migrate-time synchronization for the Phase 11 Ledgix product shell."""

import frappe

from ledgix_saas.api.product_shell import build_product_context
from ledgix_saas.setup.erpnext_extensions import get_effective_business_features


WORKSPACE_NAME = "Ledgix"
WORKSPACE_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager", "Ledgix Cashier")
LEGACY_OPERATIONAL_TARGETS = {
    "Ledgix Item",
    "Ledgix Category",
    "Ledgix Customer",
    "Ledgix Supplier",
    "Ledgix Sale",
    "Ledgix Purchase",
    "Ledgix Sales Return",
    "Ledgix POS Shift",
    "Ledgix POS Hold",
    "Ledgix Price List",
    "Ledgix Item Price",
    "Ledgix Payment Method",
    "Ledgix Payment",
    "Ledgix Stock Movement",
    "Ledgix Stock Lot",
    "Ledgix Stock Serial",
}


def desired_role_home_pages() -> dict[str, str]:
    features = get_effective_business_features()
    cashier = build_product_context(roles=["Ledgix Cashier"], features=features)
    return {
        "Ledgix Cashier": cashier["landing_route"],
        "Ledgix Manager": WORKSPACE_NAME,
        "Ledgix Admin": WORKSPACE_NAME,
    }


def sync_role_home_pages() -> dict[str, str]:
    desired = desired_role_home_pages()
    for role_name, home_page in desired.items():
        if not frappe.db.exists("Role", role_name):
            continue
        if frappe.db.get_value("Role", role_name, "home_page") != home_page:
            frappe.db.set_value("Role", role_name, "home_page", home_page, update_modified=False)
    return desired


def _sync_workspace_roles() -> None:
    if not frappe.db.exists("Workspace", WORKSPACE_NAME):
        return
    frappe.db.delete("Has Role", {"parent": WORKSPACE_NAME, "parenttype": "Workspace"})
    for role in WORKSPACE_ROLES:
        frappe.get_doc(
            {
                "doctype": "Has Role",
                "parent": WORKSPACE_NAME,
                "parenttype": "Workspace",
                "parentfield": "roles",
                "role": role,
            }
        ).insert(ignore_permissions=True)


def _assert_workspace_authority() -> None:
    workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
    targets = {str(row.link_to or "") for row in workspace.links}
    forbidden = sorted(targets.intersection(LEGACY_OPERATIONAL_TARGETS))
    if forbidden:
        frappe.throw("Phase 11 Workspace still exposes legacy operational DocTypes: " + ", ".join(forbidden))

    expected = {"Customer", "Item", "Sales Invoice", "POS Invoice", "Purchase Invoice", "Stock Entry"}
    missing = sorted(expected.difference(targets))
    if missing:
        frappe.throw("Phase 11 Workspace is missing required ERPNext targets: " + ", ".join(missing))


def sync_workspace() -> None:
    # Workspace records can be customized in the database. Phase 11 intentionally
    # makes the repository definition authoritative for the public Ledgix shell.
    frappe.reload_doc("ledgix", "workspace", "ledgix", force=True)
    _sync_workspace_roles()
    _assert_workspace_authority()


def sync_all() -> dict:
    sync_workspace()
    homes = sync_role_home_pages()
    frappe.clear_cache()
    frappe.db.commit()
    return {
        "workspace": WORKSPACE_NAME,
        "roles": list(WORKSPACE_ROLES),
        "role_home_pages": homes,
    }


def after_migrate() -> None:
    sync_all()
