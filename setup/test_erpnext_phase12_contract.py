from __future__ import annotations

import json
import unittest
from pathlib import Path

from ledgix_saas.api import legacy_retirement


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
WORKSPACE = APP_ROOT / "ledgix" / "workspace" / "ledgix" / "ledgix.json"


class TestERPNextPhase12Contract(unittest.TestCase):
    def test_retirement_state_is_audit_metadata_not_business_ledger(self):
        path = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_legacy_retirement_state"
            / "ledgix_legacy_retirement_state.json"
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload.get("issingle"))
        self.assertEqual(payload.get("module"), "Ledgix")
        fields = {row["fieldname"] for row in payload.get("fields") or []}
        self.assertTrue(
            {
                "status",
                "frozen_at",
                "frozen_by",
                "frozen_commit",
                "snapshot_json",
                "reconciliation_json",
                "last_verified_at",
            }.issubset(fields)
        )

    def test_freeze_scope_excludes_ledgix_compliance_product_doctypes(self):
        required = {
            "Ledgix Item",
            "Ledgix Customer",
            "Ledgix Supplier",
            "Ledgix Sale",
            "Ledgix Purchase",
            "Ledgix Sales Return",
            "Ledgix Payment",
            "Ledgix POS Shift",
            "Ledgix POS Hold",
            "Ledgix Stock Movement",
            "Ledgix Stock Lot",
            "Ledgix Stock Serial",
        }
        self.assertTrue(required.issubset(set(legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES)))
        for retained in (
            "Ledgix FBR Settings",
            "Ledgix FBR Submission Log",
            "Ledgix Tax Audit Log",
            "Ledgix Item Tax Profile",
            "Ledgix Brand Settings",
            "Ledgix Business Profile",
        ):
            self.assertNotIn(retained, legacy_retirement.LEGACY_ALL_DOCTYPES)

    def test_phase12_never_deletes_legacy_schema_or_rows(self):
        retirement = (APP_ROOT / "api" / "legacy_retirement.py").read_text(encoding="utf-8")
        setup = (APP_ROOT / "setup" / "erpnext_phase12_legacy_retirement.py").read_text(encoding="utf-8")
        for source in (retirement, setup):
            self.assertNotIn("frappe.delete_doc(", source)
            self.assertNotIn("DROP TABLE", source.upper())
            self.assertNotIn("TRUNCATE TABLE", source.upper())
        self.assertIn("capture_legacy_snapshot", retirement)
        self.assertIn("verify_frozen_snapshot", retirement)
        self.assertIn("UNFREEZE LEGACY LEDGERS FOR CONTROLLED ROLLBACK", retirement)

    def test_reconciliation_is_mapping_and_open_operation_based(self):
        source = (APP_ROOT / "api" / "legacy_retirement.py").read_text(encoding="utf-8")
        self.assertIn("MASTER_MAPPINGS", source)
        self.assertIn("OPEN_OPERATIONAL_CHECKS", source)
        self.assertIn("Current ERPNext balances and stock", source)
        self.assertNotIn("erpnext_current_stock == legacy_current_stock", source)
        for marker in (
            "custom_ledgix_legacy_item",
            "custom_ledgix_legacy_category",
            "custom_ledgix_legacy_customer",
            "custom_ledgix_legacy_supplier",
            "custom_ledgix_legacy_price_list",
            "custom_ledgix_legacy_item_price",
            "custom_ledgix_legacy_payment_method",
        ):
            self.assertIn(marker, source)

    def test_frozen_legacy_permissions_are_audit_only(self):
        source = (APP_ROOT / "setup" / "erpnext_phase12_legacy_retirement.py").read_text(encoding="utf-8")
        self.assertIn('AUDIT_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")', source)
        self.assertIn('"read": 1', source)
        self.assertIn('"report": 1', source)
        self.assertIn('"export": 1', source)
        self.assertIn('"print": 1', source)
        self.assertIn('"write", "create", "delete", "submit", "cancel", "amend"', source)
        self.assertIn("cashier_legacy_access", source)

    def test_custom_docperm_uses_pinned_frappe_v15_schema(self):
        source = (APP_ROOT / "setup" / "erpnext_phase12_legacy_retirement.py").read_text(encoding="utf-8")
        self.assertIn('"parent": doctype', source)
        self.assertIn("setup_custom_perms(doctype)", source)
        self.assertNotIn('"parenttype":', source)
        self.assertNotIn('"parentfield":', source)

    def test_hooks_freeze_all_legacy_top_level_business_doctypes(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.setup.erpnext_phase12_legacy_retirement.after_migrate", hooks)
        self.assertIn("ledgix_saas.api.legacy_retirement.guard_legacy_write", hooks)
        self.assertIn('"before_insert"', hooks)
        self.assertIn('"before_save"', hooks)
        self.assertIn('"before_submit"', hooks)
        self.assertIn('"before_cancel"', hooks)
        self.assertIn('"on_trash"', hooks)
        for doctype in legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES:
            self.assertIn(f'"{doctype}"', hooks)

    def test_old_pos_compatibility_surface_reads_native_erpnext_only(self):
        source = (APP_ROOT / "api" / "pos.py").read_text(encoding="utf-8")
        for forbidden in (
            'frappe.get_doc("Ledgix Sale"',
            'frappe.get_all("Ledgix Sale"',
            'frappe.new_doc("Ledgix Sale")',
            'frappe.get_doc("Ledgix POS Shift"',
            'frappe.new_doc("Ledgix POS Shift")',
            'frappe.get_all("Ledgix Stock Serial"',
            '`tabLedgix Payment`',
        ):
            self.assertNotIn(forbidden, source)
        for required in (
            '"POS Invoice"',
            '"POS Invoice Item"',
            '"Item"',
            '"Item Barcode"',
            "erpnext_buying_inventory.available_serials",
            "get_native_invoice_print_context",
            "pos_compat.complete_pos_v2_sale",
        ):
            self.assertIn(required, source)

    def test_old_business_intelligence_rpc_is_forced_to_native_phase10_adapter(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn(
            '"ledgix_saas.api.business_intelligence.get_business_intelligence_data": "ledgix_saas.api.inventory_intelligence_native.get_inventory_intelligence_data"',
            hooks,
        )

    def test_active_workspace_still_has_no_legacy_operational_targets(self):
        payload = json.loads(WORKSPACE.read_text(encoding="utf-8"))
        targets = {str(row.get("link_to") or "") for row in payload.get("links") or []}
        self.assertTrue(targets.isdisjoint(set(legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES)))

    def test_phase12_runner_is_fail_closed(self):
        runner = REPO_ROOT / "scripts" / "run_erpnext_phase12_final_gate.sh"
        if not runner.exists():
            self.fail("Phase 12 final gate runner is missing")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase12_contract", text)
        self.assertIn("erpnext_phase12_legacy_retirement_gate.run", text)
        self.assertIn("phase12_complete", text)
        self.assertIn("phase13_ready", text)
        self.assertIn("legacy_snapshot_matches", text)


if __name__ == "__main__":
    unittest.main()
