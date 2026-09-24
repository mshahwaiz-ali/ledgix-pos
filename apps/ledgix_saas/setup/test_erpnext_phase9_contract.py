from __future__ import annotations

import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_phase9_extensions


APP_ROOT = Path(__file__).resolve().parents[1]
def _find_repo_root() -> Path:
    # Find the outer Ledgix repository from source or Bench runtime copies.
    for candidate in APP_ROOT.parents:
        if (
            (candidate / "scripts").is_dir()
            and (candidate / "apps" / "ledgix_saas").is_dir()
        ):
            return candidate
    raise RuntimeError(f"Could not locate Ledgix repository root from {APP_ROOT}")


REPO_ROOT = _find_repo_root()


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
        self.assertNotIn("/assets/ledgix_saas/js/ledgix_fbr_native_center.js", hooks)
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
        self.assertIn("fbr_v2_payload_builder", source)
        self.assertIn('"authority": "ERPNext Native"', source)

    def test_payload_requires_hash_verified_v2_snapshot(self):
        native = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        readiness = (
            APP_ROOT / "services" / "fbr_v2_readiness.py"
        ).read_text(encoding="utf-8")
        persistence = (
            APP_ROOT / "services" / "fbr_v2_snapshot_persistence.py"
        ).read_text(encoding="utf-8")

        self.assertIn("fbr_v2_readiness.evaluate_invoice_readiness(", native)
        self.assertIn("_persisted_snapshot_candidate(", readiness)
        self.assertIn("read_persisted_v2_snapshot(", readiness)
        self.assertIn('"snapshot_source": "persisted_v2"', readiness)
        self.assertIn("hash_verified", persistence)


    def test_consolidated_pos_sales_invoice_is_not_second_fbr_source(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        self.assertIn("def _is_consolidated_pos_sales_invoice", source)
        self.assertIn('"POS Invoice", {"consolidated_invoice": doc.name, "docstatus": 1}', source)
        self.assertIn("and not _is_consolidated_pos_sales_invoice(doc)", source)
        self.assertIn("source POS Invoices own FBR submission", source)

    def test_v2_return_payload_remains_fail_closed_until_sandbox_proof(self):
        source = (
            APP_ROOT / "services" / "fbr_v2_payload_builder.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "FBR V2 return payload is not activated until Debit/Credit Note semantics",
            source,
        )
        self.assertNotIn(
            '"invoiceType": "Credit Note" if is_return else "Sale Invoice"',
            source,
        )


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
        self.assertIn("Legacy Ledgix Sale / Sales Return FBR execution is retired", source)
        self.assertIn("def reject_legacy_fbr_action", source)
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

    def test_phase9_closure_reads_validation_log_from_persisted_audit(self):
        source = (
            APP_ROOT / "migration" / "erpnext_phase9_fbr_closure_gate.py"
        ).read_text(encoding="utf-8")
        self.assertIn("Ledgix FBR Submission Log", source)
        self.assertIn('"reference_doctype": "Sales Invoice"', source)
        self.assertIn('"fbr_status": "Validated"', source)
        self.assertIn("validation_log_persisted", source)
        self.assertIn("production_adapter_modified", source)
        self.assertIn("payload = base.run()", source)

    def test_phase9_runner_is_fail_closed(self):
        runner = REPO_ROOT / "scripts" / "run_erpnext_phase9_final_gate.sh"
        if not runner.exists():
            self.fail("Phase 9 final gate runner is missing")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("test_erpnext_phase9_contract", text)
        self.assertIn("erpnext_phase9_fbr_closure_gate.run", text)
        self.assertIn("phase9_complete", text)
        self.assertIn("phase10_ready", text)


if __name__ == "__main__":
    unittest.main()
