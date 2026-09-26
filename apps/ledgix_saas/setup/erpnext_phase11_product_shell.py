from __future__ import annotations

"""Migrate-time synchronization for the Phase 11 Ledgix product shell."""

import frappe

from ledgix_saas.api.product_shell import (
    WORKSPACE_CARDS,
    WORKSPACE_LINK_POLICY,
    WORKSPACE_SHORTCUT_POLICY,
)


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
    # Role.home_page participates in Frappe website-root resolution, not only
    # Desk routing. Desk Page/Workspace names here can make "/" resolve them as
    # website routes and produce a 404 for authenticated users.
    #
    # Keep these blank. Frappe sends System Users to the normal Desk default
    # path, and the Phase 11 client shell applies profile-aware Ledgix landing
    # after Desk has loaded.
    return {
        "Ledgix Cashier": "",
        "Ledgix Manager": "",
        "Ledgix Admin": "",
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
    link_rows = [row for row in workspace.links if row.type == "Link"]
    targets = {str(row.link_to or "") for row in link_rows}
    labels = {str(row.label or "") for row in link_rows}

    forbidden = sorted(targets.intersection(LEGACY_OPERATIONAL_TARGETS))
    if forbidden:
        frappe.throw(
            "Phase 11 Workspace still exposes legacy operational DocTypes: "
            + ", ".join(forbidden)
        )

    forbidden_children = {
        "Ledgix FBR Business Nature",
        "Ledgix FBR Sandbox Scenario",
    }
    exposed_children = sorted(targets.intersection(forbidden_children))
    if exposed_children:
        frappe.throw(
            "Ledgix Workspace exposes FBR child tables directly: "
            + ", ".join(exposed_children)
        )

    expected_targets = {
        "Customer",
        "Item",
        "Sales Invoice",
        "POS Invoice",
        "Purchase Invoice",
        "Stock Entry",
        "Ledgix FBR Integration Profile",
        "Ledgix FBR Item Mapping",
        "Ledgix FBR Tax Component Mapping",
        "Ledgix FBR Reference Data",
        "Ledgix FBR Sandbox Certification",
        "Ledgix FBR Submission Log",
        "Ledgix FBR Correction Request",
    }
    missing_targets = sorted(expected_targets.difference(targets))
    if missing_targets:
        frappe.throw(
            "Ledgix Workspace is missing required current targets: "
            + ", ".join(missing_targets)
        )

    policy_only = sorted(set(WORKSPACE_LINK_POLICY).difference(labels))
    workspace_only = sorted(labels.difference(WORKSPACE_LINK_POLICY))
    if policy_only or workspace_only:
        frappe.throw(
            "Ledgix Workspace/product-shell link policy drift detected. "
            f"Policy-only: {policy_only}; Workspace-only: {workspace_only}"
        )

    content = frappe.parse_json(workspace.content or "[]")
    cards = tuple(
        str((row.get("data") or {}).get("card_name") or "")
        for row in content
        if row.get("type") == "card"
    )
    if cards != WORKSPACE_CARDS:
        frappe.throw(
            "Ledgix Workspace/product-shell card drift detected. "
            f"Workspace: {list(cards)}; Policy: {list(WORKSPACE_CARDS)}"
        )

    shortcut_labels = {str(row.label or "") for row in workspace.shortcuts}
    if shortcut_labels != set(WORKSPACE_SHORTCUT_POLICY):
        frappe.throw(
            "Ledgix Workspace/product-shell shortcut drift detected. "
            f"Workspace: {sorted(shortcut_labels)}; "
            f"Policy: {sorted(WORKSPACE_SHORTCUT_POLICY)}"
        )


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
