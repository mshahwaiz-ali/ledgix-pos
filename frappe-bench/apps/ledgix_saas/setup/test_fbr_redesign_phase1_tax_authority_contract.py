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

    def test_transaction_tax_boundary_is_erpnext_native_only(self):
        boundary = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def native_tax_authority_enabled()", boundary)
        self.assertIn("def evaluate_native_tax_contract(doc)", boundary)
        self.assertIn("def assert_native_tax_contract(doc)", boundary)
        self.assertIn("def prepare_native_tax_state(doc)", boundary)
        self.assertIn("def apply_sales_tax_authority(", boundary)
        self.assertNotIn("NATIVE_TAX_SITE_CONFIG_KEY", boundary)
        self.assertNotIn("ledgix_erpnext_native_tax_authority", boundary)
        self.assertNotIn("from ledgix_saas.setup import erpnext_tax_foundation", boundary)
        self.assertNotIn("erpnext_tax_foundation.apply_tax_plan", boundary)
        self.assertNotIn('"authority": "Legacy Bridge"', boundary)
        self.assertIn('return "ERPNext Native"', boundary)

    def test_native_branch_never_creates_ledgix_managed_tax_rows(self):
        boundary = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("doc.append(", boundary)
        self.assertNotIn('description": "[LEDGIX-TAX]', boundary)
        self.assertIn("assert_native_tax_contract(doc)", boundary)
        self.assertIn('doc.run_method("calculate_taxes_and_totals")', boundary)

    def test_native_branch_uses_erpnext_tax_population_before_totals(self):
        boundary = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertIn('doc.run_method("set_taxes_and_charges")', boundary)
        self.assertIn('doc.run_method("calculate_taxes_and_totals")', boundary)

        populate_at = boundary.index('doc.run_method("set_taxes_and_charges")')
        calculate_at = boundary.index('doc.run_method("calculate_taxes_and_totals")')
        contract_at = boundary.rindex("assert_native_tax_contract(doc)")
        self.assertLess(populate_at, calculate_at)
        self.assertLess(calculate_at, contract_at)

        self.assertNotIn("doc.append(", boundary)
        self.assertNotIn("erpnext_tax_foundation.apply_tax_plan", boundary)

    def test_native_return_paths_recalculate_after_ledgix_row_selection(self):
        selling = (APP_ROOT / "services" / "erpnext_selling.py").read_text(
            encoding="utf-8"
        )
        pos = (APP_ROOT / "services" / "erpnext_pos.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "erpnext_tax_authority.apply_sales_tax_authority(credit)",
            selling,
        )
        self.assertNotIn("native_tax_authority_enabled()", selling)
        self.assertIn(
            "erpnext_tax_authority.apply_sales_tax_authority(return_doc)",
            pos,
        )
        self.assertNotIn(
            "if erpnext_tax_authority.native_tax_authority_enabled():",
            pos,
        )

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

    def test_temporary_site_config_switch_and_legacy_fallback_are_removed(self):
        source = (
            APP_ROOT / "services" / "erpnext_tax_authority.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("NATIVE_TAX_SITE_CONFIG_KEY", source)
        self.assertNotIn("ledgix_erpnext_native_tax_authority", source)
        self.assertNotIn("Legacy Bridge", source)
        self.assertNotIn("erpnext_tax_foundation", source)
        self.assertIn("return True", source)
        self.assertIn('return "ERPNext Native"', source)


if __name__ == "__main__":
    unittest.main()
