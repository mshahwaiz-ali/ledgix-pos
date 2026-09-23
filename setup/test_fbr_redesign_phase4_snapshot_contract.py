from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignPhase4SnapshotContract(unittest.TestCase):
    def test_collector_uses_erpnext_native_tax_engine(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "calculate_taxes_and_totals as ERPNextTaxesAndTotals",
            source,
        )
        self.assertIn("class ERPNextNativeTaxCollector(ERPNextTaxesAndTotals)", source)
        self.assertIn("super().get_current_tax_and_net_amount(", source)
        self.assertIn("super()._calculate()", source)

    def test_collector_does_not_implement_ledgix_tax_formulas(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "* tax_rate / 100",
            "* rate / 100",
            "/ (1 +",
            "extra_tax_per_unit",
            "further_tax_per_unit",
            "fed_payable_per_unit",
            "default_tax_rate",
            "erpnext_tax_foundation",
            "Ledgix Tax Category",
            "Ledgix Tax Rate",
        ):
            self.assertNotIn(forbidden, source)

    def test_duplicate_item_rows_use_unique_row_identity(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        self.assertIn('row.get("name") or f"{prefix}-{row.get('idx') or 0}"', source)
        self.assertNotIn("tax.item_wise_tax_detail", source)
        self.assertNotIn("item_wise_tax_detail.get(item.item_code", source)

    def test_pinned_v15_unsupported_rounding_paths_fail_closed(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"round_row_wise_tax"', source)
        self.assertIn("Round Tax Amount Row-wise is on", source)
        self.assertIn('tax.get("charge_type") == "Actual"', source)
        self.assertIn("V2 refuses to guess a line split", source)
        self.assertIn("MONEY_TOLERANCE", source)

    def test_mapped_rows_reconcile_to_authoritative_erpnext_tax_rows(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        self.assertIn('tax.get("tax_amount_after_discount_amount")', source)
        self.assertIn("ERPNext native line-tax capture did not reconcile", source)
        self.assertIn('"authority": "ERPNext Native"', source)
        self.assertIn('"reconciliation": reconciliation', source)

    def test_v2_uses_fbr_only_mapping_models(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        self.assertIn('MAPPING_DOCTYPE = "Ledgix FBR Item Mapping"', source)
        self.assertIn(
            'COMPONENT_MAPPING_DOCTYPE = "Ledgix FBR Tax Component Mapping"',
            source,
        )
        self.assertNotIn("Ledgix Item Tax Profile", source)

    def test_snapshot_foundation_is_non_persisting_and_non_networked(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "frappe.db.set_value(",
            ".insert(",
            ".save(",
            ".submit(",
            "requests.",
            "post_invoice(",
            "validate_invoice(",
        ):
            self.assertNotIn(forbidden, source)

        self.assertIn('"database_write": False', source)
        self.assertIn('"fbr_network_call": False', source)

    def test_submitted_return_is_never_reconstructed(self):
        source = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot_v2.py"
        ).read_text(encoding="utf-8")

        self.assertIn("Submitted return snapshots must not be reconstructed after the fact", source)
        self.assertIn("draft/submission lifecycle", source)


if __name__ == "__main__":
    unittest.main()
