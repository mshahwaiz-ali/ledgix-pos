from __future__ import annotations

import traceback

import frappe

from ledgix_saas.api import product_shell
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.setup import erpnext_phase11_product_shell as phase11
from ledgix_saas.setup.erpnext_extensions import PROFILE_DEFAULTS, get_effective_business_features


LEGACY_BUSINESS_DOCTYPES = (
    "Ledgix Sale",
    "Ledgix Sales Return",
    "Ledgix Payment",
    "Ledgix Purchase",
    "Ledgix Stock Movement",
    "Ledgix Stock Lot",
    "Ledgix Stock Serial",
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(f"Refusing Phase 11 gate on {frappe.local.site!r}; restricted to {INTEGRATION_SITE!r}.")
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration Company {TEST_COMPANY!r} is missing.")


def _count(doctype: str) -> int | None:
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def _legacy_counts() -> dict:
    return {doctype: _count(doctype) for doctype in LEGACY_BUSINESS_DOCTYPES}


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        return {"name": name, "evidence": evidence, "checks": checks, "passed": all(checks.values())}
    except Exception as exc:
        return {
            "name": name,
            "evidence": {},
            "checks": {},
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": traceback.format_exc().splitlines()[-12:],
        }


def _profile(name: str) -> dict:
    return {"business_profile": name, **PROFILE_DEFAULTS[name]}


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")

    legacy_before = _legacy_counts()
    custom_perm_before = frappe.db.count("Custom DocPerm")
    features_before = get_effective_business_features()
    sync_result = phase11.sync_all()

    cases = {}

    def workspace_case():
        workspace = frappe.get_doc("Workspace", "Ledgix")
        roles = set(
            frappe.get_all(
                "Has Role",
                filters={"parent": "Ledgix", "parenttype": "Workspace"},
                pluck="role",
            )
        )
        targets = {str(row.link_to or "") for row in workspace.links}
        labels = {str(row.label or "") for row in workspace.links if row.type == "Link"}
        expected_native = {
            "Customer", "Item", "Sales Invoice", "POS Invoice", "Payment Entry",
            "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Supplier",
            "Warehouse", "Stock Entry", "Stock Reconciliation", "Batch", "Serial No",
        }
        checks = {
            "cashier_can_open_ledgix_workspace": "Ledgix Cashier" in roles,
            "manager_admin_system_workspace_roles_present": {"Ledgix Manager", "Ledgix Admin", "System Manager"}.issubset(roles),
            "native_operational_targets_present": expected_native.issubset(targets),
            "legacy_operational_targets_absent": targets.isdisjoint(phase11.LEGACY_OPERATIONAL_TARGETS),
            "business_profile_is_admin_entry": "Business Profile" in labels and "Ledgix Business Profile" in targets,
            "only_three_custom_product_pages": {
                row.link_to for row in workspace.links if row.link_type == "Page"
            } == {"ledgix-pos", "ledgix-tax-center", "business-intelligence-center"},
        }
        return {
            "roles": sorted(roles),
            "link_count": len(labels),
            "native_targets_checked": sorted(expected_native),
        }, checks

    def landing_case():
        desired = phase11.desired_role_home_pages()
        actual = {
            role: frappe.db.get_value("Role", role, "home_page")
            for role in ("Ledgix Cashier", "Ledgix Manager", "Ledgix Admin")
        }
        cashier_context = product_shell.build_product_context(
            roles=["Ledgix Cashier"], features=features_before
        )
        checks = {
            "cashier_home_matches_profile": actual["Ledgix Cashier"] == cashier_context["landing_route"],
            "manager_home_is_ledgix": actual["Ledgix Manager"] == "Ledgix",
            "admin_home_is_ledgix": actual["Ledgix Admin"] == "Ledgix",
            "sync_result_matches_db": desired == actual,
        }
        return {"features": features_before, "desired": desired, "actual": actual}, checks

    def profile_matrix_case():
        invoice_cashier = product_shell.build_product_context(
            roles=["Ledgix Cashier"], features=_profile("Invoice + FBR Only")
        )
        small_cashier = product_shell.build_product_context(
            roles=["Ledgix Cashier"], features=_profile("Small Retail")
        )
        full_manager = product_shell.build_product_context(
            roles=["Ledgix Manager"], features=_profile("Full Retail")
        )
        b2b_cashier = product_shell.build_product_context(
            roles=["Ledgix Cashier"], features=_profile("B2B")
        )
        mixed_admin = product_shell.build_product_context(
            roles=["Ledgix Admin"], features=_profile("Mixed")
        )
        checks = {
            "invoice_only_cashier_avoids_pos": invoice_cashier["landing_route"] == "ledgix" and "Ledgix POS" not in invoice_cashier["visible_workspace_links"],
            "invoice_only_keeps_native_sales": "Sales Invoices" in invoice_cashier["visible_workspace_links"] and "Customers" in invoice_cashier["visible_workspace_links"],
            "small_retail_cashier_lands_pos": small_cashier["landing_route"] == "ledgix-pos" and "Ledgix POS" in small_cashier["visible_workspace_links"],
            "small_retail_hides_advanced_stock": "Stock Entries" not in small_cashier["visible_workspace_links"],
            "full_retail_manager_has_buying_and_advanced_stock": "Purchase Invoices" in full_manager["visible_workspace_links"] and "Stock Entries" in full_manager["visible_workspace_links"],
            "b2b_cashier_has_sales_without_pos": b2b_cashier["landing_route"] == "ledgix" and "Sales Invoices" in b2b_cashier["visible_workspace_links"] and "Ledgix POS" not in b2b_cashier["visible_workspace_links"],
            "mixed_admin_has_setup_and_operations": "Business Profile" in mixed_admin["visible_workspace_links"] and "Purchase Invoices" in mixed_admin["visible_workspace_links"] and "Ledgix POS" in mixed_admin["visible_workspace_links"],
        }
        return {
            "invoice_cashier": invoice_cashier,
            "small_cashier": small_cashier,
            "full_manager": full_manager,
            "b2b_cashier": b2b_cashier,
            "mixed_admin": mixed_admin,
        }, checks

    def role_case():
        full = _profile("Full Retail")
        cashier = product_shell.build_product_context(roles=["Ledgix Cashier"], features=full)
        manager = product_shell.build_product_context(roles=["Ledgix Manager"], features=full)
        admin = product_shell.build_product_context(roles=["Ledgix Admin"], features=full)
        system = product_shell.build_product_context(roles=["System Manager"], features=_profile("Invoice + FBR Only"))
        checks = {
            "cashier_is_minimal": "Accounts Receivable" not in cashier["visible_workspace_links"] and "Purchase Invoices" not in cashier["visible_workspace_links"],
            "manager_gets_reports_not_admin_setup": "Sales Report" in manager["visible_workspace_links"] and "Business Profile" not in manager["visible_workspace_links"],
            "admin_gets_setup": "Business Profile" in admin["visible_workspace_links"] and "Tax Audit Logs" in admin["visible_workspace_links"],
            "system_manager_not_sidebar_curated": system["role_level"] == "system" and not system["curated_sidebar"],
            "system_manager_sees_all_workspace_links": set(system["visible_workspace_links"]) == set(product_shell.WORKSPACE_LINK_POLICY),
        }
        return {"cashier": cashier, "manager": manager, "admin": admin, "system": system}, checks

    cases["native_ledgix_workspace"] = _case("native_ledgix_workspace", workspace_case)
    cases["profile_aware_landing"] = _case("profile_aware_landing", landing_case)
    cases["five_profile_navigation_matrix"] = _case("five_profile_navigation_matrix", profile_matrix_case)
    cases["role_aware_product_surface"] = _case("role_aware_product_surface", role_case)

    legacy_after = _legacy_counts()
    custom_perm_after = frappe.db.count("Custom DocPerm")
    features_after = get_effective_business_features()
    cases["navigation_only_no_business_or_permission_writes"] = {
        "name": "navigation_only_no_business_or_permission_writes",
        "evidence": {
            "legacy_before": legacy_before,
            "legacy_after": legacy_after,
            "custom_perm_before": custom_perm_before,
            "custom_perm_after": custom_perm_after,
            "features_before": features_before,
            "features_after": features_after,
        },
        "checks": {
            "legacy_business_counts_unchanged": legacy_before == legacy_after,
            "custom_permissions_unchanged": custom_perm_before == custom_perm_after,
            "business_profile_unchanged": features_before == features_after,
        },
        "passed": legacy_before == legacy_after and custom_perm_before == custom_perm_after and features_before == features_after,
    }

    failed = [name for name, case in cases.items() if not case.get("passed")]
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "sync": sync_result,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "decisions": {
            "workspace_authority": "Ledgix curated shell over ERPNext standard Forms/Lists",
            "custom_product_pages": ["ledgix-pos", "ledgix-tax-center", "business-intelligence-center"],
            "profile_flags_are_authorization": False,
            "erpnext_permissions_remain_authoritative": True,
            "legacy_operational_workspace_links": False,
        },
        "phase11_complete": not failed,
        "phase12_ready": not failed,
        "next_phase": "Phase 12 — Legacy Freeze, Reconciliation and Retirement",
        "passed": not failed,
    }
    frappe.db.commit()
    return result
