from __future__ import annotations

import json
import unittest
from pathlib import Path

from ledgix_saas.api import product_shell
from ledgix_saas.setup.erpnext_extensions import PROFILE_DEFAULTS


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = next(
    (
        parent
        for parent in APP_ROOT.parents
        if (parent / "scripts" / "run_erpnext_phase11_final_gate.sh").exists()
    ),
    APP_ROOT.parents[1],
)
WORKSPACE_PATH = APP_ROOT / "ledgix" / "workspace" / "ledgix" / "ledgix.json"


class TestERPNextPhase11Contract(unittest.TestCase):
    def test_phase11_hooks_load_product_shell_after_prior_cutovers(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("ledgix_phase11_product_shell.js", hooks)
        self.assertIn("ledgix_saas.api.product_shell.extend_bootinfo", hooks)
        self.assertIn("ledgix_saas.setup.erpnext_phase11_product_shell.after_migrate", hooks)
        self.assertNotIn("role_home_page = {", hooks)
        self.assertLess(
            hooks.index("ledgix_saas.setup.fast_permissions.after_migrate"),
            hooks.index("ledgix_saas.setup.erpnext_phase11_product_shell.after_migrate"),
        )

    def test_role_home_pages_do_not_hijack_website_root(self):
        from ledgix_saas.setup import permissions
        from ledgix_saas.setup import erpnext_phase11_product_shell

        expected = {
            "Ledgix Cashier": "",
            "Ledgix Manager": "",
            "Ledgix Admin": "",
        }

        self.assertEqual(permissions.ROLE_HOME_PAGES, expected)
        self.assertEqual(
            erpnext_phase11_product_shell.desired_role_home_pages(),
            expected,
        )

    def test_workspace_is_native_and_cashier_visible(self):
        payload = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
        roles = {row["role"] for row in payload.get("roles") or []}
        self.assertEqual(
            roles,
            {"System Manager", "Ledgix Admin", "Ledgix Manager", "Ledgix Cashier"},
        )
        targets = {str(row.get("link_to") or "") for row in payload.get("links") or []}
        for target in (
            "Customer",
            "Item",
            "Sales Invoice",
            "POS Invoice",
            "Payment Entry",
            "Purchase Invoice",
            "Stock Entry",
            "Ledgix Business Profile",
        ):
            self.assertIn(target, targets)
        self.assertTrue(targets.isdisjoint(product_shell_module_legacy_targets()))

    def test_only_ledgix_specific_pages_remain_custom_navigation(self):
        payload = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
        expected_pages = {
            "ledgix-pos",
            "business-intelligence-center",
            "ledgix-tax-center",
            "ledgix-setup",
        }
        page_targets = {
            row.get("link_to")
            for row in payload.get("links") or []
            if row.get("link_type") == "Page"
        }
        self.assertEqual(page_targets, expected_pages)

        page_root = APP_ROOT / "ledgix" / "page"
        expected_folders = {
            "ledgix_pos",
            "business_intelligence_center",
            "ledgix_tax_center",
            "ledgix_setup",
        }
        for folder in expected_folders:
            self.assertTrue((page_root / folder).is_dir(), f"retained custom page is missing: {folder}")

    def test_workspace_shortcuts_match_current_operational_shell(self):
        payload = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))

        expected_page_links = {
            "Ledgix POS": "ledgix-pos",
            "Inventory Intelligence": "business-intelligence-center",
            "Tax & FBR Center": "ledgix-tax-center",
            "Setup Wizard": "ledgix-setup",
        }
        page_links = {
            row.get("label"): row.get("link_to")
            for row in payload.get("links") or []
            if row.get("link_type") == "Page"
        }
        self.assertEqual(page_links, expected_page_links)

        shortcut_map = {
            row.get("label"): (row.get("link_to"), row.get("type"))
            for row in payload.get("shortcuts") or []
        }
        self.assertEqual(
            shortcut_map,
            {
                "Ledgix POS": ("ledgix-pos", "Page"),
                "Sales Invoice": ("Sales Invoice", "DocType"),
                "Purchase Invoice": ("Purchase Invoice", "DocType"),
                "Payment Entry": ("Payment Entry", "DocType"),
                "Profit & Loss": ("Profit and Loss Statement", "Report"),
                "Gross Profit": ("Gross Profit", "Report"),
                "Balance Sheet": ("Balance Sheet", "Report"),
                "Cash Flow": ("Cash Flow", "Report"),
                "Accounts Receivable": ("Accounts Receivable", "Report"),
                "Accounts Payable": ("Accounts Payable", "Report"),
                "General Ledger": ("General Ledger", "Report"),
                "Stock Balance": ("Stock Balance", "Report"),
            },
        )
        self.assertEqual(tuple(shortcut_map), product_shell.WORKSPACE_SHORTCUTS)
        self.assertEqual(set(shortcut_map), set(product_shell.WORKSPACE_SHORTCUT_POLICY))

        content = json.loads(payload.get("content") or "[]")
        content_shortcuts = [
            row.get("data", {}).get("shortcut_name")
            for row in content
            if row.get("type") == "shortcut"
        ]
        self.assertEqual(content_shortcuts, list(product_shell.WORKSPACE_SHORTCUTS))

    def test_product_profiles_curate_cashier_without_granting_permissions(self):
        invoice = product_shell.build_product_context(
            roles=["Ledgix Cashier"],
            features={"business_profile": "Invoice + FBR Only", **PROFILE_DEFAULTS["Invoice + FBR Only"]},
        )
        self.assertEqual(invoice["landing_route"], "ledgix")
        self.assertIn("Sales Invoices", invoice["visible_workspace_links"])
        self.assertIn("Customers", invoice["visible_workspace_links"])
        self.assertIn("Payment Entries", invoice["visible_workspace_links"])
        self.assertNotIn("Ledgix POS", invoice["visible_workspace_links"])
        self.assertNotIn("Purchase Invoices", invoice["visible_workspace_links"])
        self.assertNotIn("Stock Entries", invoice["visible_workspace_links"])
        self.assertNotIn("Tax & FBR Center", invoice["visible_workspace_links"])
        self.assertNotIn("Setup Wizard", invoice["visible_workspace_links"])
        self.assertEqual(invoice["visible_workspace_shortcuts"], ["Sales Invoice", "Payment Entry"])

        small = product_shell.build_product_context(
            roles=["Ledgix Cashier"],
            features={"business_profile": "Small Retail", **PROFILE_DEFAULTS["Small Retail"]},
        )
        self.assertEqual(small["landing_route"], "ledgix-pos")
        self.assertIn("Ledgix POS", small["visible_workspace_links"])
        self.assertEqual(
            small["visible_workspace_shortcuts"],
            ["Ledgix POS", "Sales Invoice", "Payment Entry"],
        )
        self.assertNotIn("Stock Entries", small["visible_workspace_links"])

    def test_manager_admin_and_full_retail_visibility(self):
        full_features = {"business_profile": "Full Retail", **PROFILE_DEFAULTS["Full Retail"]}
        manager = product_shell.build_product_context(roles=["Ledgix Manager"], features=full_features)
        self.assertIn("Purchase Invoices", manager["visible_workspace_links"])
        self.assertIn("Stock Entries", manager["visible_workspace_links"])
        self.assertIn("Tax & FBR Center", manager["visible_workspace_links"])
        self.assertIn("FBR Submission Logs", manager["visible_workspace_links"])
        self.assertNotIn("FBR Integration Profiles", manager["visible_workspace_links"])
        self.assertNotIn("Business Profile", manager["visible_workspace_links"])
        self.assertNotIn("Setup Wizard", manager["visible_workspace_links"])
        self.assertEqual(
            set(manager["visible_workspace_shortcuts"]),
            set(product_shell.WORKSPACE_SHORTCUTS),
        )

        admin = product_shell.build_product_context(roles=["Ledgix Admin"], features=full_features)
        self.assertIn("Setup Wizard", admin["visible_workspace_links"])
        self.assertIn("Business Profile", admin["visible_workspace_links"])
        self.assertIn("Brand Settings", admin["visible_workspace_links"])
        self.assertIn("FBR Integration Profiles", admin["visible_workspace_links"])
        self.assertIn("FBR Item Mappings", admin["visible_workspace_links"])
        self.assertIn("FBR Tax Component Mappings", admin["visible_workspace_links"])
        self.assertIn("FBR Submission Logs", admin["visible_workspace_links"])
        self.assertEqual(
            set(admin["visible_workspace_shortcuts"]),
            set(product_shell.WORKSPACE_SHORTCUTS),
        )

    def test_system_manager_is_not_sidebar_restricted(self):
        context = product_shell.build_product_context(
            roles=["System Manager"],
            features={"business_profile": "Invoice + FBR Only", **PROFILE_DEFAULTS["Invoice + FBR Only"]},
        )
        self.assertEqual(context["role_level"], "system")
        self.assertFalse(context["curated_sidebar"])
        self.assertEqual(set(context["visible_workspace_links"]), set(product_shell.WORKSPACE_LINK_POLICY))
        self.assertEqual(set(context["visible_workspace_shortcuts"]), set(product_shell.WORKSPACE_SHORTCUTS))

    def test_client_shell_uses_frappe_v15_workspace_dom_contract(self):
        source = (APP_ROOT / "public" / "js" / "ledgix_phase11_product_shell.js").read_text(encoding="utf-8")
        self.assertIn("ledgix_product", source)
        self.assertIn(".desk-sidebar .sidebar-item-container", source)
        self.assertIn(".links-widget-box", source)
        self.assertIn("a.link-item", source)
        self.assertIn(".shortcut-widget-box", source)
        self.assertIn('getAttribute("aria-label")', source)
        self.assertIn("visible_workspace_cards", source)
        self.assertIn("visible_workspace_links", source)
        self.assertIn("visible_workspace_shortcuts", source)
        self.assertIn("GENERIC_DESK_HOME_PATHS", source)
        self.assertIn('"/app/home"', source)
        self.assertIn('"/app/workspaces"', source)

    def test_business_profile_refreshes_landing_without_becoming_authorization(self):
        controller = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_business_profile"
            / "ledgix_business_profile.py"
        ).read_text(encoding="utf-8")
        self.assertIn("sync_role_home_pages", controller)
        schema = json.loads(
            (
                APP_ROOT
                / "ledgix"
                / "doctype"
                / "ledgix_business_profile"
                / "ledgix_business_profile.json"
            ).read_text(encoding="utf-8")
        )
        note = next(row for row in schema["fields"] if row.get("fieldname") == "profile_note")
        self.assertIn("not an authorization system", note.get("description") or "")

    def test_phase11_runner_is_fail_closed(self):
        runner = REPO_ROOT / "scripts" / "run_erpnext_phase11_final_gate.sh"
        if not runner.exists():
            self.fail("Phase 11 final gate runner is missing")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase11_contract", text)
        self.assertIn("erpnext_phase11_product_shell_gate.run", text)
        self.assertIn("phase11_complete", text)
        self.assertIn("phase12_ready", text)


def product_shell_module_legacy_targets() -> set[str]:
    # Keep the static test independent from Frappe DB state.
    return {
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


if __name__ == "__main__":
    unittest.main()
