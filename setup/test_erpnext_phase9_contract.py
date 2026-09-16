from __future__ import annotations

import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_phase9_extensions


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]


class TestERPNextPhase9Contract(unittest.TestCase):
    def test_phase9_metadata_only_targets_native_sales_documents(self):
        self.assertEqual(
            set(erpnext_phase9_extensions.CUSTOM_FIELDS),
            {"Sales Invoice", "POS Invoice"},
        )
        forbidden = {
            "grand_total",
            "net_total",
            "total_taxes_and_charges",
            "outstanding_amount",
            "paid_amount",
            "actual_qty",
            "valuation_rate",
        }
        fieldnames = {
            row["fieldname"]
            for rows in erpnext_phase9_extensions.CUSTOM_FIELDS.values()
            for row in rows
        }
        self.assertFalse(forbidden.intersection(fieldnames))
        self.assertTrue(all(value.startswith("custom_ledgix_fbr_") for value in fieldnames))

    def test_hooks_cut_fbr_source_over_to_erpnext(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.setup.erpnext_phase9_extensions.after_migrate", hooks)
        for doctype in ("Sales Invoice", "POS Invoice"):
            self.assertIn(f'"{doctype}": {{', hooks)
        self.assertIn("ledgix_saas.api.fbr_native.on_native_invoice_submit", hooks)
        self.assertIn("ledgix_saas.api.fbr_native.block_cancel_after_fbr_submission", hooks)
        self.assertIn(
            '"ledgix_saas.api.fbr_submission.submit_sale_to_fbr": "ledgix_saas.api.fbr_legacy_guard.reject_legacy_sale_submission"',
            hooks,
        )
        self.assertIn("/assets/ledgix_saas/js/ledgix_fbr_native_center.js", hooks)
        self.assertIn("scheduler_events = {}", hooks)

    def test_native_adapter_never_writes_legacy_business_ledgers(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        for forbidden in (
            'frappe.get_doc("Ledgix Sale"',
            'frappe.new_doc("Ledgix Sale")',
            'frappe.get_doc("Ledgix Sales Return"',
            'frappe.new_doc("Ledgix Sales Return")',
            'frappe.new_doc("Ledgix Payment")',
            'frappe.new_doc("Ledgix Stock Movement")',
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('SUPPORTED_DOCTYPES = ("Sales Invoice", "POS Invoice")', source)
        self.assertIn('"authority": "ERPNext"', source)

    def test_payload_requires_immutable_native_line_snapshot(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        self.assertIn('custom_ledgix_fbr_snapshot_json', source)
        self.assertIn("Do not reconstruct legal tax data after submission", source)
        self.assertIn('snapshot = json.loads(raw)', source)
        self.assertIn('custom_ledgix_fbr_snapshot_version', source)

    def test_consolidated_pos_sales_invoice_is_not_second_fbr_source(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        self.assertIn("def _is_consolidated_pos_sales_invoice", source)
        self.assertIn('"POS Invoice", {"consolidated_invoice": doc.name, "docstatus": 1}', source)
        self.assertIn("and not _is_consolidated_pos_sales_invoice(doc)", source)
        self.assertIn("source POS Invoices own FBR submission", source)

    def test_native_credit_note_references_original_fbr_invoice(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        self.assertIn('"invoiceType": "Credit Note" if is_return else "Sale Invoice"', source)
        self.assertIn('original.get("custom_ledgix_fbr_invoice_number")', source)
        self.assertIn('"invoiceRefNo": (', source)
        self.assertIn("180 days", source)

    def test_submission_log_remains_ledgix_audit_over_native_dynamic_reference(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        self.assertIn("from ledgix_saas.api.fbr_submission import create_submission_log", source)
        self.assertIn("doc.doctype,", source)
        self.assertIn("doc.name,", source)
        log_schema = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_fbr_submission_log"
            / "ledgix_fbr_submission_log.json"
        ).read_text(encoding="utf-8")
        self.assertIn('"fieldname":"reference_doctype"', log_schema)
        self.assertIn('"fieldtype":"Dynamic Link"', log_schema)

    def test_fbr_center_bridge_uses_native_sources(self):
        source = (APP_ROOT / "public" / "js" / "ledgix_fbr_native_center.js").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.api.fbr_native_ui.get_native_fbr_preview", source)
        self.assertIn("ledgix_saas.api.fbr_native.submit_native_to_fbr", source)
        self.assertIn('option value="Sales Invoice"', source)
        self.assertIn('option value="POS Invoice"', source)
        self.assertNotIn('options: "Ledgix Sale"', source)
        self.assertIn("reference_doctype", source)
        self.assertIn("reference_name", source)

    def test_legacy_production_submit_is_fail_closed(self):
        source = (APP_ROOT / "api" / "fbr_legacy_guard.py").read_text(encoding="utf-8")
        self.assertIn("Legacy Ledgix Sale FBR submission is retired", source)
        self.assertIn("ERPNext Sales Invoice or POS Invoice", source)

    def test_correction_tracker_accepts_native_invoice_reference(self):
        schema = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_fbr_correction_request"
            / "ledgix_fbr_correction_request.json"
        ).read_text(encoding="utf-8")
        controller = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_fbr_correction_request"
            / "ledgix_fbr_correction_request.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"fieldname":"reference_doctype"', schema)
        self.assertIn('"fieldname":"reference_name"', schema)
        self.assertIn('NATIVE_DOCTYPES = {"Sales Invoice", "POS Invoice"}', controller)
        self.assertIn('custom_ledgix_fbr_invoice_number', controller)

    def test_phase9_runner_is_fail_closed(self):
        runner = REPO_ROOT / "scripts" / "run_erpnext_phase9_final_gate.sh"
        if not runner.exists():
            self.fail("Phase 9 final gate runner is missing")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase9_contract", text)
        self.assertIn("erpnext_phase9_fbr_gate.run", text)
        self.assertIn("phase9_complete", text)
        self.assertIn("phase10_ready", text)


if __name__ == "__main__":
    unittest.main()
