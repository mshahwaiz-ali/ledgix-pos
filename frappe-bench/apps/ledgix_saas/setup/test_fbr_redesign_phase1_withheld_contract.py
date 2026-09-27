from __future__ import annotations

from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignPhase1WithheldContract(unittest.TestCase):
    def test_non_posting_account_contract_exists(self):
        source = (APP_ROOT / "services" / "erpnext_tax_authority.py").read_text()
        self.assertIn("def _non_posting_fbr_tax_accounts", source)
        self.assertIn("posted_non_posting", source)
        self.assertIn("Sales Tax Withheld At Source", source)

    def test_snapshot_uses_erpnext_engine(self):
        source = (APP_ROOT / "services" / "erpnext_fbr_snapshot.py").read_text()
        self.assertIn("def _collect_non_posting_withheld_rows", source)
        self.assertIn(
            "ERPNextTaxesAndTotals.get_current_tax_and_net_amount",
            source,
        )
        self.assertIn("tax.parenttype = doc.doctype", source)
        self.assertIn('tax.parentfield = "taxes"', source)
        self.assertIn('tax.parent = doc.name or f"new-{doc.doctype}"', source)
        self.assertIn('"On Item Quantity"', source)
        self.assertIn('"non_posting_fbr_evidence": True', source)

    def test_financial_withheld_row_is_rejected(self):
        source = (APP_ROOT / "services" / "erpnext_fbr_snapshot.py").read_text()
        self.assertIn("if component == WITHHELD_COMPONENT:", source)
        self.assertIn("Sales Tax Withheld At Source Account {account} must not be ", source)
        self.assertIn("present in financial invoice taxes.", source)

    def test_old_ledgix_tax_formula_not_imported(self):
        source = (APP_ROOT / "services" / "erpnext_fbr_snapshot.py").read_text()
        self.assertNotIn("from ledgix_saas.services.tax", source)
        self.assertNotIn("erpnext_tax_foundation", source)


if __name__ == "__main__":
    unittest.main()
