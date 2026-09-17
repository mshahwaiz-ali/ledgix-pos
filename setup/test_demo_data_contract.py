from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
NATIVE = APP_ROOT / "setup" / "erpnext_demo_data.py"
ENTRYPOINT = APP_ROOT / "setup" / "demo_data.py"


class TestDemoDataContract(unittest.TestCase):
    def test_supported_entrypoint_is_erpnext_native(self):
        source = ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("erpnext_demo_data as native", source)
        self.assertIn("def inspect_site", source)
        self.assertIn("def cleanup_seed_transactions", source)
        self.assertIn("def seed", source)
        self.assertIn("def verify", source)
        for legacy in (
            'frappe.new_doc("Ledgix Item")',
            'frappe.new_doc("Ledgix Customer")',
            'frappe.new_doc("Ledgix Supplier")',
            'frappe.new_doc("Ledgix Sale")',
            'frappe.new_doc("Ledgix Purchase")',
            'frappe.new_doc("Ledgix Payment")',
            'frappe.new_doc("Ledgix Stock Movement")',
        ):
            self.assertNotIn(legacy, source)

    def test_native_seed_uses_standard_erpnext_authority(self):
        source = NATIVE.read_text(encoding="utf-8")
        for authority in (
            '"doctype": "Item"',
            '"doctype": "Customer"',
            '"doctype": "Supplier"',
            '"doctype": "Purchase Order"',
            '"doctype": "POS Opening Entry"',
            '"doctype": "POS Invoice"',
            '"doctype": "Sales Invoice"',
            '"doctype": "Stock Entry"',
            '"doctype": "Warehouse"',
        ):
            self.assertIn(authority, source)
        self.assertIn("make_purchase_receipt", source)
        self.assertIn("make_purchase_invoice", source)
        self.assertIn("make_closing_entry_from_opening", source)
        self.assertIn("make_sales_return", source)
        self.assertIn("make_return_doc", source)
        self.assertIn("use_serial_batch_fields", source)
        self.assertIn("ensure_batch", source)

    def test_seed_is_local_only_and_fbr_transport_is_forced_off(self):
        source = NATIVE.read_text(encoding="utf-8")
        self.assertIn('site.endswith(".local")', source)
        self.assertIn('"mode": "Disabled"', source)
        self.assertIn('"enabled": 0', source)
        self.assertIn('"production_post_armed": 0', source)
        self.assertNotIn("sandbox_response", source.lower())
        self.assertNotIn("production_response", source.lower())

    def test_seed_has_realistic_scale_and_determinism(self):
        source = NATIVE.read_text(encoding="utf-8")
        self.assertIn("random.Random(260917)", source)
        self.assertIn("range(-84, 0, 7)", source)
        self.assertIn("for slot in range(9)", source)
        self.assertIn("for sequence in range(1, 13)", source)
        self.assertIn("LEDGIX-ERP-DEMO-V2", source)

    def test_cleanup_is_marker_scoped(self):
        source = NATIVE.read_text(encoding="utf-8")
        cleanup = source[source.index("def cleanup_seed_transactions") :]
        self.assertIn('f"{SEED}-%"', cleanup)
        self.assertIn('f"%{SEED}%"', cleanup)
        self.assertNotIn('frappe.db.delete("Item"', cleanup)
        self.assertNotIn('frappe.db.delete("Customer"', cleanup)
        self.assertNotIn('frappe.db.delete("Supplier"', cleanup)


if __name__ == "__main__":
    unittest.main()
