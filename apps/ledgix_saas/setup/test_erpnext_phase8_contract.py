from __future__ import annotations

"""Phase 8 POS engine migration contract tests."""

import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_phase8_extensions


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]


class TestERPNextPhase8Contract(unittest.TestCase):
    def test_phase8_extensions_only_target_native_pos_documents(self):
        self.assertEqual(
            set(erpnext_phase8_extensions.CUSTOM_FIELDS),
            {"POS Invoice", "Sales Invoice", "POS Opening Entry", "POS Closing Entry"},
        )

    def test_phase8_extensions_do_not_duplicate_financial_or_stock_authority(self):
        forbidden = {
            "grand_total",
            "net_total",
            "paid_amount",
            "outstanding_amount",
            "change_amount",
            "actual_qty",
            "current_stock",
            "valuation_rate",
            "stock_value",
        }
        fieldnames = {
            row["fieldname"]
            for rows in erpnext_phase8_extensions.CUSTOM_FIELDS.values()
            for row in rows
        }
        self.assertFalse(forbidden.intersection(fieldnames))
        self.assertTrue(all(field.startswith("custom_ledgix_") for field in fieldnames))

    def test_native_pos_service_never_writes_legacy_ledgers(self):
        source = (APP_ROOT / "services" / "erpnext_pos.py").read_text(encoding="utf-8")
        for forbidden in (
            'frappe.new_doc("Ledgix Sale")',
            'frappe.new_doc("Ledgix Payment")',
            'frappe.new_doc("Ledgix POS Shift")',
            'frappe.new_doc("Ledgix POS Hold")',
            'frappe.new_doc("Ledgix Stock Movement")',
            'frappe.get_doc("Ledgix Sale"',
            'frappe.get_doc("Ledgix Payment"',
            'frappe.get_doc("Ledgix POS Shift"',
            'frappe.get_doc("Ledgix POS Hold"',
        ):
            self.assertNotIn(forbidden, source)
        for native in (
            '"POS Profile"',
            '"POS Opening Entry"',
            '"POS Invoice"',
            '"Sales Invoice"',
            '"Customer"',
            '"Item"',
            '"Price List"',
            '"Mode of Payment"',
        ):
            self.assertIn(native, source)
        self.assertIn(
            "from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening",
            source,
        )
        self.assertIn("closing = make_closing_entry_from_opening(opening)", source)

    def test_pos_profile_lookup_materializes_erpnext_row_by_name(self):
        source = (APP_ROOT / "services" / "erpnext_pos.py").read_text(encoding="utf-8")
        self.assertIn("profile_row = get_pos_profile(company, user=user)", source)
        self.assertIn('profile_row.get("name")', source)
        self.assertIn('frappe.get_doc("POS Profile", profile_name)', source)
        self.assertNotIn("frappe.get_doc(doc)", source)

    def test_pos_holds_are_native_drafts(self):
        source = (APP_ROOT / "services" / "erpnext_pos.py").read_text(encoding="utf-8")
        self.assertIn("custom_ledgix_hold_status", source)
        self.assertIn('"Held"', source)
        self.assertIn("build_pos_invoice", source)
        self.assertIn("erpnext_selling.build_sales_invoice", source)
        self.assertNotIn('frappe.new_doc("Ledgix POS Hold")', source)

    def test_retail_return_uses_native_pos_mapper_and_never_trusts_client_rate(self):
        source = (APP_ROOT / "services" / "erpnext_pos.py").read_text(encoding="utf-8")
        self.assertIn("from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return", source)
        self.assertIn("row.qty = -abs(qty)", source)
        self.assertNotIn("row.rate =", source)
        self.assertNotIn("price_list_rate =", source)

    def test_pos_rpc_contracts_are_overridden_to_phase8_compat(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        required = (
            '"ledgix_saas.api.v2_pos.get_pos_v2_boot": "ledgix_saas.api.pos_compat.get_pos_v2_boot"',
            '"ledgix_saas.api.v2_pos.search_pos_v2_items": "ledgix_saas.api.pos_compat.search_pos_v2_items"',
            '"ledgix_saas.api.v2_pos.complete_pos_v2_sale": "ledgix_saas.api.pos_compat.complete_pos_v2_sale"',
            '"ledgix_saas.api.v2_pos.preview_pos_v2_checkout": "ledgix_saas.api.pos_compat.preview_pos_v2_checkout"',
            '"ledgix_saas.api.v2_returns.create_pos_v2_return": "ledgix_saas.api.pos_compat.create_pos_v2_return"',
            '"ledgix_saas.api.v2_holds.hold_pos_v2_sale": "ledgix_saas.api.pos_compat.hold_pos_v2_sale"',
            '"ledgix_saas.api.api.open_pos_shift": "ledgix_saas.api.pos_compat.open_pos_shift"',
            '"ledgix_saas.api.api.close_pos_shift": "ledgix_saas.api.pos_compat.close_pos_shift"',
        )
        for value in required:
            self.assertIn(value, hooks)

    def test_native_result_never_restores_legacy_sale_print_identity(self):
        source = (APP_ROOT / "api" / "pos_compat.py").read_text(encoding="utf-8")
        self.assertIn('result["sale"] = ""', source)
        self.assertIn('result["native_document"] = native_document', source)
        self.assertIn('result["print_doctype"] = doctype', source)
        self.assertIn('result["print_deferred"] = False', source)
        self.assertIn('"Ledgix ERPNext POS Receipt"', source)
        self.assertIn('"Ledgix ERPNext Tax Invoice"', source)
        self.assertNotIn('print_doctype"] = "Ledgix Sale"', source)

    def test_phase8_schema_is_installed_after_migrate(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.setup.erpnext_phase8_extensions.after_migrate", hooks)

    def test_phase8_does_not_switch_fbr_submission_source(self):
        service = (APP_ROOT / "services" / "erpnext_pos.py").read_text(encoding="utf-8")
        compat = (APP_ROOT / "api" / "pos_compat.py").read_text(encoding="utf-8")
        for source in (service, compat):
            self.assertNotIn("submit_fbr", source)
            self.assertNotIn("fbr_connector", source)
            self.assertNotIn("post_to_fbr", source)

    def test_phase8_runner_is_fail_closed(self):
        runner = (REPO_ROOT / "scripts" / "run_erpnext_phase8_final_gate.sh").read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase8_contract", runner)
        self.assertIn("erpnext_phase8_pos_gate.run", runner)
        self.assertIn("phase8_complete", runner)
        self.assertIn("phase9_ready", runner)


if __name__ == "__main__":
    unittest.main()
