from __future__ import annotations

import json
import unittest
from pathlib import Path

from ledgix_saas.api import client_setup, product_shell
from ledgix_saas.setup.erpnext_extensions import PROFILE_DEFAULTS


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
SETUP_PAGE = APP_ROOT / "ledgix" / "page" / "ledgix_setup"
WORKSPACE = APP_ROOT / "ledgix" / "workspace" / "ledgix" / "ledgix.json"
BUSINESS_PROFILE = (
    APP_ROOT
    / "ledgix"
    / "doctype"
    / "ledgix_business_profile"
    / "ledgix_business_profile.json"
)


class TestERPNextPhase13Contract(unittest.TestCase):
    def test_profile_catalog_is_one_codebase_configuration(self):
        self.assertEqual(
            set(PROFILE_DEFAULTS),
            {"Invoice + FBR Only", "Small Retail", "Full Retail", "B2B", "Mixed"},
        )
        self.assertEqual(set(client_setup.PROFILE_COPY), set(PROFILE_DEFAULTS))
        for name in PROFILE_DEFAULTS:
            self.assertTrue(client_setup.PROFILE_COPY[name]["summary"])
            self.assertTrue(client_setup.PROFILE_COPY[name]["best_for"])

    def test_setup_service_is_configuration_only(self):
        source = (APP_ROOT / "api" / "client_setup.py").read_text(encoding="utf-8")
        self.assertIn("ERPNext native configuration + Ledgix product preset", source)
        self.assertIn("apply_standard_defaults", source)
        self.assertIn('frappe.get_single("Ledgix Business Profile")', source)
        self.assertIn('frappe.db.set_single_value("Global Defaults"', source)
        self.assertIn('"Selling Settings"', source)
        self.assertIn('"Stock Settings"', source)
        for forbidden in (
            'frappe.new_doc("Item")',
            'frappe.new_doc("Customer")',
            'frappe.new_doc("Supplier")',
            '"doctype": "Item"',
            '"doctype": "Customer"',
            '"doctype": "Supplier"',
            '"doctype": "Sales Invoice"',
            '"doctype": "Purchase Invoice"',
            '"doctype": "Stock Entry"',
        ):
            self.assertNotIn(forbidden, source)

    def test_explicit_setup_selections_fail_closed(self):
        source = (APP_ROOT / "api" / "client_setup.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('explicit = str(value or "").strip()'), 3)
        gate = (
            APP_ROOT
            / "migration"
            / "erpnext_phase13_client_setup_gate.py"
        ).read_text(encoding="utf-8")
        self.assertIn("explicit_invalid_selling_price_list_fails_closed", gate)
        self.assertIn("explicit_invalid_warehouse_fails_closed", gate)
        self.assertIn("retail_requires_pos_profile", gate)

    def test_setup_page_is_admin_only_and_uses_readiness_api(self):
        schema = json.loads((SETUP_PAGE / "ledgix_setup.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["name"], "ledgix-setup")
        self.assertEqual(
            {row["role"] for row in schema.get("roles") or []},
            {"System Manager", "Ledgix Admin"},
        )
        source = (SETUP_PAGE / "ledgix_setup.js").read_text(encoding="utf-8")
        self.assertIn("get_client_setup_boot", source)
        self.assertIn("evaluate_client_setup", source)
        self.assertIn("apply_client_setup", source)
        self.assertIn("Apply Configuration", source)
        self.assertIn("does not create duplicate Items", source)

    def test_business_profile_records_setup_audit_not_business_authority(self):
        schema = json.loads(BUSINESS_PROFILE.read_text(encoding="utf-8"))
        fields = {row["fieldname"]: row for row in schema.get("fields") or []}
        for fieldname in (
            "setup_complete",
            "setup_version",
            "setup_company",
            "setup_completed_at",
            "setup_completed_by",
            "setup_snapshot_json",
        ):
            self.assertIn(fieldname, fields)
        self.assertTrue(fields["setup_complete"].get("read_only"))
        self.assertTrue(fields["setup_company"].get("read_only"))
        description = fields["setup_section"].get("description") or ""
        self.assertIn("never replace ERPNext business masters", description)

    def test_workspace_and_product_shell_surface_setup_only_to_admin(self):
        payload = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        setup_links = [
            row for row in payload.get("links") or []
            if row.get("label") == "Setup Wizard"
        ]
        self.assertEqual(len(setup_links), 1)
        self.assertEqual(setup_links[0].get("link_to"), "ledgix-setup")
        self.assertEqual(setup_links[0].get("link_type"), "Page")
        full = {"business_profile": "Mixed", **PROFILE_DEFAULTS["Mixed"]}
        admin = product_shell.build_product_context(roles=["Ledgix Admin"], features=full)
        manager = product_shell.build_product_context(roles=["Ledgix Manager"], features=full)
        cashier = product_shell.build_product_context(roles=["Ledgix Cashier"], features=full)
        self.assertIn("Setup Wizard", admin["visible_workspace_links"])
        self.assertNotIn("Setup Wizard", manager["visible_workspace_links"])
        self.assertNotIn("Setup Wizard", cashier["visible_workspace_links"])

    def test_client_site_preflight_enforces_erpnext_v15(self):
        path = REPO_ROOT / "scripts" / "run_ledgix_client_preflight.sh"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for token in (
            "frappe erpnext ledgix_saas",
            '[[ "$frappe_version" == 15.* ]]',
            '[[ "$erpnext_version" == 15.* ]]',
            "required_apps",
            "ledgix-setup",
        ):
            self.assertIn(token, text)

    def test_phase13_gate_preserves_phase12_and_business_masters(self):
        gate = (
            APP_ROOT
            / "migration"
            / "erpnext_phase13_client_setup_gate.py"
        ).read_text(encoding="utf-8")
        self.assertIn("legacy_retirement.is_frozen()", gate)
        self.assertIn("verify_frozen_snapshot", gate)
        self.assertIn("BUSINESS_MASTER_COUNTS", gate)
        self.assertIn("counts_before == counts_after_apply", gate)
        self.assertIn("_restore_profile(original_profile)", gate)
        self.assertIn("phase13_complete", gate)
        self.assertIn("migration_complete", gate)

    def test_phase13_runner_is_fail_closed(self):
        runner = REPO_ROOT / "scripts" / "run_erpnext_phase13_final_gate.sh"
        if not runner.exists():
            self.fail("Phase 13 final gate runner is missing")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("run_ledgix_client_preflight.sh", text)
        self.assertIn("test_erpnext_phase13_contract", text)
        self.assertIn("erpnext_phase13_client_setup_gate.run", text)
        self.assertIn("phase13_complete", text)
        self.assertIn("migration_complete", text)


if __name__ == "__main__":
    unittest.main()
