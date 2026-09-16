import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_phase7_extensions


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]


class TestERPNextPhase7Contract(unittest.TestCase):
    def test_phase7_extensions_only_target_native_erpnext_documents(self):
        self.assertEqual(
            set(erpnext_phase7_extensions.CUSTOM_FIELDS),
            {
                "Purchase Order",
                "Purchase Receipt",
                "Purchase Invoice",
                "Stock Entry",
                "Stock Reconciliation",
            },
        )

    def test_phase7_extensions_do_not_duplicate_money_or_stock_authority(self):
        forbidden = {
            "grand_total",
            "net_total",
            "outstanding_amount",
            "paid_amount",
            "actual_qty",
            "valuation_rate",
            "stock_value",
            "current_stock",
            "cost_price",
        }
        fieldnames = {
            row["fieldname"]
            for rows in erpnext_phase7_extensions.CUSTOM_FIELDS.values()
            for row in rows
        }
        self.assertFalse(forbidden.intersection(fieldnames))
        self.assertTrue(all(name.startswith("custom_ledgix_") for name in fieldnames))

    def test_native_buying_inventory_service_never_writes_legacy_stock_or_purchase(self):
        source = (APP_ROOT / "services" / "erpnext_buying_inventory.py").read_text(encoding="utf-8")
        for forbidden in (
            'frappe.new_doc("Ledgix Purchase")',
            'frappe.new_doc("Ledgix Stock Movement")',
            'frappe.new_doc("Ledgix Stock Lot")',
            'frappe.new_doc("Ledgix Stock Serial")',
            'frappe.get_doc("Ledgix Purchase"',
            'frappe.get_doc("Ledgix Stock Movement"',
            'frappe.get_doc("Ledgix Stock Lot"',
            'frappe.get_doc("Ledgix Stock Serial"',
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"Purchase Order"', source)
        self.assertIn('"Purchase Receipt"', source)
        self.assertIn('"Purchase Invoice"', source)
        self.assertIn('"Stock Entry"', source)
        self.assertIn('"Stock Reconciliation"', source)
        self.assertIn('"Serial No"', source)
        self.assertIn('"Bin"', source)

    def test_manual_stock_compatibility_routes_to_erpnext(self):
        source = (APP_ROOT / "api" / "stock_ops.py").read_text(encoding="utf-8")
        self.assertIn("erpnext_buying_inventory.create_stock_entry", source)
        self.assertIn("erpnext_buying_inventory.stock_snapshot", source)
        self.assertNotIn('frappe.new_doc("Ledgix Stock Movement")', source)
        self.assertNotIn("create_stock_lot_from_manual_entry", source)
        self.assertNotIn("create_stock_serials_for_manual_entry", source)
        self.assertNotIn("reduce_lots_fifo_for_manual_out", source)

    def test_pos_serial_picker_reads_erpnext_serial_no(self):
        source = (APP_ROOT / "api" / "v2_inventory.py").read_text(encoding="utf-8")
        self.assertIn("erpnext_buying_inventory.available_serials", source)
        self.assertIn('"authority": "ERPNext Serial No"', source)
        self.assertNotIn("Ledgix Stock Serial", source)

    def test_phase7_schema_is_installed_after_migrate(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.setup.erpnext_phase7_extensions.after_migrate", hooks)

    def test_workspace_routes_buying_and_stock_to_native_erpnext(self):
        workspace = (APP_ROOT / "ledgix" / "workspace" / "ledgix" / "ledgix.json").read_text(encoding="utf-8")
        for native in (
            '"link_to":"Purchase Order"',
            '"link_to":"Purchase Receipt"',
            '"link_to":"Purchase Invoice"',
            '"link_to":"Supplier"',
            '"link_to":"Item"',
            '"link_to":"Item Group"',
            '"link_to":"Warehouse"',
            '"link_to":"Stock Entry"',
            '"link_to":"Stock Reconciliation"',
            '"link_to":"Batch"',
            '"link_to":"Serial No"',
        ):
            self.assertIn(native, workspace)
        self.assertNotIn('"link_to":"Ledgix Purchase"', workspace)
        self.assertNotIn('"link_to":"Ledgix Stock Movement"', workspace)

    def test_supplier_ap_preflight_is_fail_closed(self):
        source = (APP_ROOT / "migration" / "erpnext_phase7_supplier_ap_preflight.py").read_text(encoding="utf-8")
        self.assertIn("current_balance", source)
        self.assertIn("GL Entry", source)
        self.assertIn('"blocking_suppliers"', source)
        self.assertIn('"ready": not blockers', source)
        self.assertIn("never silently reposted", source)

    def test_phase7_gate_proves_no_parallel_legacy_inventory_writes(self):
        source = (APP_ROOT / "migration" / "erpnext_phase7_buying_inventory_gate.py").read_text(encoding="utf-8")
        self.assertIn("no_parallel_ledgix_inventory_docs", source)
        self.assertIn("purchase_return", source)
        self.assertIn("cancel_and_backdated_behavior", source)
        self.assertIn("valuation_authority", source)
        self.assertIn('"phase7_complete"', source)
        self.assertIn('"phase8_ready"', source)

    def test_phase7_runner_includes_preflight_static_and_runtime_gates(self):
        source = (REPO_ROOT / "scripts" / "run_erpnext_phase7_final_gate.sh").read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase7_contract", source)
        self.assertIn("erpnext_phase7_supplier_ap_preflight.run", source)
        self.assertIn("erpnext_phase7_buying_inventory_gate.run", source)
        self.assertIn("phase7_complete", source)
        self.assertIn("phase8_ready", source)


if __name__ == "__main__":
    unittest.main()
