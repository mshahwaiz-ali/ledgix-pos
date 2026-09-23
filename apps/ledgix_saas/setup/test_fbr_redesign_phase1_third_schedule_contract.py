from __future__ import annotations

from pathlib import Path
import unittest

APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignPhase1ThirdScheduleContract(unittest.TestCase):
    def test_hook_registers_native_taxable_base_resolver(self):
        hooks = (APP_ROOT / "hooks.py").read_text()
        self.assertIn("erpnext_taxable_base_resolvers", hooks)
        self.assertIn("On Notified Retail Price", hooks)

    def test_transaction_authority_stamps_before_erpnext_calculation(self):
        source = (APP_ROOT / "services" / "erpnext_tax_authority.py").read_text()

        start = source.index("def apply_sales_tax_authority(")
        body = source[start:]

        stamp = "erpnext_taxable_base.stamp_fbr_taxable_base_inputs(doc)"
        prepare = "prepare_native_tax_state(doc)"
        calculate = 'doc.run_method("calculate_taxes_and_totals")'

        self.assertIn(stamp, body)
        self.assertIn(prepare, body)
        self.assertIn(calculate, body)

        self.assertLess(body.index(stamp), body.index(prepare))
        self.assertLess(body.index(prepare), body.index(calculate))

    def test_resolver_does_not_import_legacy_tax_engine(self):
        source = (APP_ROOT / "services" / "erpnext_taxable_base.py").read_text()
        self.assertNotIn("erpnext_tax_foundation", source)
        self.assertNotIn("api.taxation", source)
        self.assertIn('return flt(notified_value * flt(item.get("qty")))', source)

    def test_snapshot_captures_erpnext_resolver_base(self):
        source = (APP_ROOT / "services" / "erpnext_fbr_snapshot.py").read_text()
        self.assertIn("capture_taxable_base = self.get_item_taxable_base(item, tax)", source)
        self.assertIn('"taxable_base": flt(capture_taxable_base)', source)


if __name__ == "__main__":
    unittest.main()
