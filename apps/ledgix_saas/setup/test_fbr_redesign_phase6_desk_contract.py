from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignPhase6DeskContract(unittest.TestCase):
    def setUp(self):
        self.page = (
            APP_ROOT
            / "ledgix"
            / "page"
            / "ledgix_tax_center"
            / "ledgix_tax_center.js"
        ).read_text(encoding="utf-8")
        self.api = (APP_ROOT / "api" / "fbr_v2_center.py").read_text(encoding="utf-8")
        self.hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.workspace = (
            APP_ROOT / "ledgix" / "workspace" / "ledgix" / "ledgix.json"
        ).read_text(encoding="utf-8")
        self.workspace_fixture = (
            APP_ROOT / "fixtures" / "workspace.json"
        ).read_text(encoding="utf-8")

    def test_desk_center_uses_v2_api_only(self):
        for marker in (
            "ledgix_saas.api.fbr_v2_center.get_v2_center_boot",
            "ledgix_saas.api.fbr_v2_center.get_v2_item_mappings",
            "ledgix_saas.api.fbr_reference_v2.sync_core_reference_data",
            "ledgix_saas.api.fbr_v2_center.evaluate_v2_invoice_readiness",
        ):
            self.assertIn(marker, self.page)

        for forbidden in (
            "ledgix_saas.api.tax_center.get_tax_center_boot",
            "ledgix_saas.api.fbr_settings.get_fbr_settings",
            "ledgix_saas.api.fbr_submission.",
            "ledgix_saas.api.fbr_native.submit_native_to_fbr",
            "validate_native_fbr_production",
            "submit_fbr(",
        ):
            self.assertNotIn(forbidden, self.page)

    def test_old_custom_tax_authority_is_not_exposed_in_page(self):
        for forbidden in (
            "Ledgix Tax Profile",
            "Ledgix Tax Category",
            "Ledgix Tax Rate",
            "Ledgix Item Tax Profile",
            "Category rollout",
            "Apply to unmapped",
            "Tax engine",
        ):
            self.assertNotIn(forbidden, self.page)

        for required in (
            "Tax Category",
            "Tax Rule",
            "Sales Taxes and Charges Template",
            "Item Tax Template",
            "Account",
        ):
            self.assertIn(required, self.page)

    def test_v2_fbr_configuration_is_exposed(self):
        for required in (
            "Ledgix FBR Integration Profile",
            "Ledgix FBR Reference Data",
            "Ledgix FBR Item Mapping",
            "Ledgix FBR Tax Component Mapping",
            "Ledgix FBR Sandbox Certification",
            "Ledgix FBR Submission Log",
            "Ledgix FBR Correction Request",
        ):
            self.assertIn(required, self.page)

    def test_center_has_no_production_invoice_action(self):
        self.assertIn(
            "This center contains no Production invoice-submit action.",
            self.page,
        )
        for forbidden in (
            "Submit Production",
            "Production Submit",
            "submit_native_to_fbr",
            "post_invoice(",
            "validate_invoice(",
        ):
            self.assertNotIn(forbidden, self.page)
            self.assertNotIn(forbidden, self.api)

    def test_v2_center_api_never_calculates_tax(self):
        for forbidden in (
            "* tax_rate / 100",
            "* rate / 100",
            "extra_tax_per_unit",
            "further_tax_per_unit",
            "fed_payable_per_unit",
            "Ledgix Tax Profile",
        ):
            self.assertNotIn(forbidden, self.api)

        self.assertIn('"architecture": "ERPNext Native + FBR V2"', self.api)
        self.assertIn('"final_payload_builder_active": False', self.api)

    def test_old_phase9_page_patch_is_not_loaded(self):
        self.assertNotIn(
            '"/assets/ledgix_saas/js/ledgix_fbr_native_center.js"',
            self.hooks,
        )

    def test_legacy_tax_center_readiness_rpc_routes_to_v2(self):
        self.assertIn(
            '"ledgix_saas.api.tax_center.get_fbr_readiness": '
            '"ledgix_saas.api.fbr_v2_center.get_fbr_readiness"',
            self.hooks,
        )
        self.assertNotIn(
            '"ledgix_saas.api.tax_center.get_fbr_readiness": '
            '"ledgix_saas.api.fbr_preflight.get_fbr_readiness"',
            self.hooks,
        )


    def test_main_workspace_and_fixture_use_native_tax_and_fbr_v2(self):
        for surface in (self.workspace, self.workspace_fixture):
            for forbidden in (
                "Ledgix Tax Profile",
                "Ledgix Tax Category",
                "Ledgix Tax Rate",
                "Ledgix Item Tax Profile",
                "Ledgix FBR Settings",
            ):
                self.assertNotIn(forbidden, surface)

            for required in (
                "Tax Category",
                "Tax Rule",
                "Sales Taxes and Charges Template",
                "Item Tax Template",
                "Ledgix FBR Integration Profile",
                "Ledgix FBR Item Mapping",
                "Ledgix FBR Tax Component Mapping",
                "Ledgix FBR Reference Data",
                "Ledgix FBR Sandbox Certification",
                "Ledgix FBR Submission Log",
                "Ledgix FBR Correction Request",
            ):
                self.assertIn(required, surface)

    def test_reference_sync_remains_get_only_from_desk(self):
        self.assertIn("Sync core references", self.page)
        self.assertIn(
            "It cannot validate or submit an invoice and cannot arm Production.",
            self.page,
        )


if __name__ == "__main__":
    unittest.main()
