from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
REPORT_ROOT = APP_ROOT / "ledgix" / "report"
PRINT_ROOT = APP_ROOT / "ledgix" / "print_format"


class TestERPNextPhase10Contract(unittest.TestCase):
    def test_inventory_intelligence_rpc_is_erpnext_native(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn(
            '"ledgix_saas.api.inventory_intelligence.get_inventory_intelligence_data": "ledgix_saas.api.inventory_intelligence_native.get_inventory_intelligence_data"',
            hooks,
        )
        native = (APP_ROOT / "api" / "inventory_intelligence_native.py").read_text(encoding="utf-8")
        self.assertIn("erpnext_reporting.inventory_intelligence", native)
        self.assertNotIn("business_intelligence", native)

    def test_active_reporting_service_never_queries_legacy_ledgers(self):
        source = (APP_ROOT / "services" / "erpnext_reporting.py").read_text(encoding="utf-8")
        self.assertNotIn("`tabLedgix", source)
        for native in (
            "`tabItem`",
            "`tabBin`",
            "`tabStock Ledger Entry`",
            "`tabSales Invoice`",
            "`tabPOS Invoice`",
            "`tabPurchase Invoice`",
            "`tabGL Entry`",
        ):
            self.assertIn(native, source)
        self.assertIn("consolidated_invoice = si.name", source)

    def test_workspace_report_modules_are_native_wrappers(self):
        modules = (
            "ledgix_current_stock",
            "ledgix_low_stock",
            "ledgix_stock_movement_report",
            "ledgix_sales_report",
            "ledgix_purchase_report",
            "ledgix_sales_return_report",
            "ledgix_customer_statement",
            "inventory_intelligence_report",
        )
        for module in modules:
            source = (REPORT_ROOT / module / f"{module}.py").read_text(encoding="utf-8")
            self.assertIn("erpnext_reporting", source, module)
            self.assertNotIn("`tabLedgix", source, module)
            self.assertNotIn('frappe.get_all("Ledgix', source, module)

    def test_active_report_metadata_references_erpnext_doctypes(self):
        expected = {
            "ledgix_current_stock": "Item",
            "ledgix_low_stock": "Item",
            "ledgix_stock_movement_report": "Stock Ledger Entry",
            "ledgix_sales_report": "Sales Invoice",
            "ledgix_purchase_report": "Purchase Invoice",
            "ledgix_sales_return_report": "Sales Invoice",
            "ledgix_customer_statement": "Customer",
            "inventory_intelligence_report": "Item",
        }
        for module, doctype in expected.items():
            payload = json.loads((REPORT_ROOT / module / f"{module}.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("ref_doctype"), doctype, module)
            self.assertFalse(payload.get("disabled"), module)

    def test_native_print_formats_target_erpnext_documents(self):
        tax = json.loads(
            (PRINT_ROOT / "ledgix_erpnext_tax_invoice" / "ledgix_erpnext_tax_invoice.json").read_text(encoding="utf-8")
        )
        pos = json.loads(
            (PRINT_ROOT / "ledgix_erpnext_pos_receipt" / "ledgix_erpnext_pos_receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(tax["doc_type"], "Sales Invoice")
        self.assertEqual(pos["doc_type"], "POS Invoice")
        for payload in (tax, pos):
            self.assertIn("get_native_invoice_print_context", payload["html"])
            self.assertIn("fbr_invoice_number", payload["html"])
            self.assertIn("fbr_qr_data_uri", payload["html"])
            self.assertNotIn("Ledgix Sale", payload["html"])

    def test_legacy_print_formats_remain_history_only(self):
        b2b = json.loads(
            (PRINT_ROOT / "ledgix_b2b_invoice" / "ledgix_b2b_invoice.json").read_text(encoding="utf-8")
        )
        thermal = json.loads(
            (PRINT_ROOT / "ledgix_thermal_receipt" / "ledgix_thermal_receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(b2b["doc_type"], "Ledgix Sale")
        self.assertEqual(thermal["doc_type"], "Ledgix Sale")

    def test_native_print_context_reads_same_erpnext_transaction(self):
        source = (APP_ROOT / "api" / "printing.py").read_text(encoding="utf-8")
        self.assertIn('SUPPORTED_PRINT_DOCTYPES = {"Sales Invoice", "POS Invoice"}', source)
        self.assertIn("custom_ledgix_fbr_invoice_number", source)
        self.assertIn("get_fbr_qr_data_uri(fbr_invoice_number)", source)
        self.assertIn("custom_ledgix_fbr_snapshot_json", source)
        self.assertNotIn('frappe.get_doc("Ledgix Sale"', source)

    def test_pos_print_target_is_native_and_not_deferred(self):
        source = (APP_ROOT / "api" / "pos_compat.py").read_text(encoding="utf-8")
        self.assertIn('result["native_document"] = native_document', source)
        self.assertIn('result["print_doctype"] = doctype', source)
        self.assertIn('result["print_deferred"] = False', source)
        self.assertIn('"Ledgix ERPNext Tax Invoice"', source)
        self.assertIn('"Ledgix ERPNext POS Receipt"', source)
        self.assertIn('result["sale"] = ""', source)

    def test_phase10_client_bridge_uses_native_print_and_bi_routes(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        bridge = (APP_ROOT / "public" / "js" / "ledgix_phase10_native_surfaces.js").read_text(encoding="utf-8")
        self.assertIn("ledgix_phase10_native_surfaces.js", hooks)
        # The bridge intentionally uses optional chaining in the print URL helper.
        # Accept both null-safe (result?.field) and direct (result.field) access
        # while still proving that the native print contract fields are consumed.
        self.assertRegex(bridge, r"result(?:\?\.|\.)native_document")
        self.assertRegex(bridge, r"result(?:\?\.|\.)print_doctype")
        self.assertRegex(bridge, r"result(?:\?\.|\.)print_format")
        self.assertIn('options: "Item"', bridge)
        self.assertIn('"Stock Ledger"', bridge)
        self.assertIn('"Stock Balance"', bridge)
        self.assertNotIn("doctype=Ledgix%20Sale", bridge)

    def test_phase10_runtime_fixture_uses_stock_item_authority(self):
        gate = (APP_ROOT / "migration" / "erpnext_phase10_reporting_print_gate.py").read_text(encoding="utf-8")
        self.assertIn('ITEM = "LEDGIX-P10-STOCK-NATIVE"', gate)
        self.assertIn("p7_gate._ensure_item(ITEM, stock=True)", gate)
        self.assertNotIn("tax_gate._ensure_item(ITEM)", gate)
        self.assertIn('client_stock_id="LEDGIX-P10-STOCK-SEED-V2"', gate)

    def test_phase10_print_and_pos_cost_follow_pinned_erpnext_v15(self):
        tax = json.loads(
            (PRINT_ROOT / "ledgix_erpnext_tax_invoice" / "ledgix_erpnext_tax_invoice.json").read_text(encoding="utf-8")
        )
        pos = json.loads(
            (PRINT_ROOT / "ledgix_erpnext_pos_receipt" / "ledgix_erpnext_pos_receipt.json").read_text(encoding="utf-8")
        )
        for payload in (tax, pos):
            self.assertIn("p['items']", payload["html"])
            self.assertNotIn("p.items", payload["html"])

        compat = (APP_ROOT / "services" / "erpnext_reporting_compat.py").read_text(encoding="utf-8")
        self.assertIn("`tabStock Ledger Entry`", compat)
        self.assertIn("sle.voucher_type = 'POS Invoice'", compat)
        self.assertIn("sle.voucher_detail_no", compat)
        self.assertIn("stock_value_difference", compat)
        self.assertNotIn("pii.incoming_rate", compat)

        sales = (REPORT_ROOT / "ledgix_sales_report" / "ledgix_sales_report.py").read_text(encoding="utf-8")
        returns = (REPORT_ROOT / "ledgix_sales_return_report" / "ledgix_sales_return_report.py").read_text(encoding="utf-8")
        intelligence_report = (
            REPORT_ROOT / "inventory_intelligence_report" / "inventory_intelligence_report.py"
        ).read_text(encoding="utf-8")
        native_bi = (APP_ROOT / "api" / "inventory_intelligence_native.py").read_text(encoding="utf-8")
        for source in (sales, returns, intelligence_report, native_bi):
            self.assertIn("erpnext_reporting_compat", source)

    def test_phase10_runner_is_fail_closed(self):
        runner = REPO_ROOT / "scripts" / "run_erpnext_phase10_final_gate.sh"
        if not runner.exists():
            self.fail("Phase 10 final gate runner is missing")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase10_contract", text)
        self.assertIn("erpnext_phase10_reporting_print_gate.run", text)
        self.assertIn("phase10_complete", text)
        self.assertIn("phase11_ready", text)


if __name__ == "__main__":
    unittest.main()
