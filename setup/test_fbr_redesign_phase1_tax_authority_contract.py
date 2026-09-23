from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignPhase1TaxAuthorityContract(unittest.TestCase):
    def test_transaction_services_do_not_import_old_tax_foundation_directly(self):
        for relative in (
            Path("services") / "erpnext_selling.py",
            Path("services") / "erpnext_pos.py",
        ):
            source = (APP_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn(
                "from ledgix_saas.setup import erpnext_tax_foundation",
                source,
                relative.as_posix(),
            )
            self.assertNotIn(
                "erpnext_tax_foundation.apply_tax_plan",
                source,
                relative.as_posix(),
            )
            self.assertIn(
                "erpnext_tax_authority.apply_sales_tax_authority",
                source,
                relative.as_posix(),
            )

    def test_legacy_tax_bridge_is_confined_to_transition_boundary(self):
        boundary = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'NATIVE_TAX_SITE_CONFIG_KEY = "ledgix_erpnext_native_tax_authority"',
            boundary,
        )
        self.assertIn("def native_tax_authority_enabled()", boundary)
        self.assertIn("def evaluate_native_tax_contract(doc)", boundary)
        self.assertIn("def assert_native_tax_contract(doc)", boundary)
        self.assertIn("def apply_sales_tax_authority(", boundary)
        self.assertIn(
            "from ledgix_saas.setup import erpnext_tax_foundation",
            boundary,
        )

    def test_native_branch_never_creates_ledgix_managed_tax_rows(self):
        boundary = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        native_branch = boundary.split(
            "# Transitional fallback only. Remove after the Phase 1 native runtime gate.",
            1,
        )[0]
        self.assertNotIn("doc.append(", native_branch)
        self.assertNotIn('description": "[LEDGIX-TAX]', native_branch)
        self.assertIn("assert_native_tax_contract(doc)", native_branch)
        self.assertIn('doc.run_method("calculate_taxes_and_totals")', native_branch)

    def test_native_contract_rejects_legacy_managed_rows(self):
        source = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertIn('LEGACY_MANAGED_TAX_PREFIX = "[LEDGIX-TAX]"', source)
        self.assertIn("Native tax authority cannot run with legacy [LEDGIX-TAX]", source)

    def test_native_contract_validates_erpnext_templates_and_accounts(self):
        source = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        for marker in (
            '"Sales Taxes and Charges Template"',
            '"Item Tax Template"',
            '"Account"',
            '"company"',
            '"disabled"',
            '"is_group"',
            "Positive Item Tax Template accounts are not represented in invoice taxes",
        ):
            self.assertIn(marker, source)

    def test_transition_flag_is_documented_as_internal_not_business_config(self):
        source = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "This is an engineering migration switch, not client tax configuration.",
            source,
        )
        self.assertIn(
            "Normal business tax/FBR configuration remains Desk-driven.",
            source,
        )


if __name__ == "__main__":
    unittest.main()
