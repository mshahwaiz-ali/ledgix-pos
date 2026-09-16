from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
SCRIPTS = REPO_ROOT / "scripts"
DOCS = REPO_ROOT / "docs" / "production"


class TestFBRActivationContract(unittest.TestCase):
    def test_activation_readiness_is_read_only_and_native(self):
        path = APP_ROOT / "api" / "fbr_activation.py"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            'NATIVE_DOCTYPES = ("Sales Invoice", "POS Invoice")',
            "client_readiness.evaluate_client_readiness",
            "get_fbr_settings_internal",
            "fbr_client.requests_available",
            '"Reconciliation Required"',
            '"sandbox_ready"',
            '"sandbox_proven"',
            '"production_switch_ready"',
            '"network_call_made": False',
            '"production_armed_by_gate": False',
            '"contains_secrets": False',
            '"ERPNext native Sales Invoice/POS Invoice + Ledgix FBR audit/safety layer"',
        ):
            self.assertIn(token, source)

        for forbidden in (
            "validate_invoice(",
            "post_invoice(",
            "get_active_fbr_token",
            "save_fbr_settings",
            "production_post_armed = 1",
            "frappe.new_doc",
            ".insert(",
        ):
            self.assertNotIn(forbidden, source)

    def test_sandbox_proof_requires_persisted_validate_and_post(self):
        source = (APP_ROOT / "api" / "fbr_activation.py").read_text(encoding="utf-8")
        for token in (
            '"Ledgix FBR Submission Log"',
            'response.get("fbr_mode")',
            'response.get("fbr_operation")',
            'response.get("network_call")',
            'response.get("success")',
            '"sandbox_sales_invoice_validate"',
            '"sandbox_sales_invoice_post"',
            '"sandbox_pos_invoice_validate"',
            '"sandbox_pos_invoice_post"',
            '"sandbox_return_validate"',
            '"sandbox_return_post"',
        ):
            self.assertIn(token, source)

    def test_production_switch_readiness_requires_release_backup_and_reconciliation_safety(self):
        source = (APP_ROOT / "api" / "fbr_activation.py").read_text(encoding="utf-8")
        for token in (
            'evaluate_client_readiness(strict_evidence=1)',
            '"fresh_verified_backup"',
            '"release_sha_recorded"',
            '"production_token_configured"',
            '"production_still_unarmed"',
            '"not_already_production"',
            '"no_unreconciled_production_state"',
            'DEFAULT_MAX_BACKUP_AGE_HOURS = 24',
        ):
            self.assertIn(token, source)

    def test_activation_evidence_is_private_and_non_secret(self):
        source = (APP_ROOT / "api" / "fbr_activation.py").read_text(encoding="utf-8")
        for token in (
            'frappe.get_site_path("private", "ledgix-fbr-activation")',
            'os.chmod(evidence_path, 0o600)',
            'os.chmod(latest_path, 0o600)',
            '"latest_evidence_file": "private/ledgix-fbr-activation/latest-readiness.json"',
        ):
            self.assertIn(token, source)
        self.assertNotIn('settings.get("sandbox_token")', source)
        self.assertNotIn('settings.get("production_token")', source)

    def test_static_and_runtime_gates_exist(self):
        static_gate = SCRIPTS / "run_fbr_activation_static_gate.sh"
        runtime_gate = SCRIPTS / "run_fbr_activation_readiness_gate.sh"
        runbook = DOCS / "fbr_sandbox_production_activation.md"
        self.assertTrue(static_gate.exists())
        self.assertTrue(runtime_gate.exists())
        self.assertTrue(runbook.exists())

        static_source = static_gate.read_text(encoding="utf-8")
        self.assertIn("test_fbr_activation_contract", static_source)
        self.assertIn("fbr_activation_static_complete=true", static_source)

        runtime_source = runtime_gate.read_text(encoding="utf-8")
        for token in (
            "generate_fbr_activation_evidence",
            "fbr_readiness_evaluation_complete=true",
            "fbr_sandbox_ready=",
            "fbr_sandbox_proven=",
            "fbr_production_switch_ready=",
            "--require-sandbox-ready",
            "--require-sandbox-proof",
            "--require-production-ready",
        ):
            self.assertIn(token, runtime_source)
        self.assertNotIn("post_invoice", runtime_source)
        self.assertNotIn("production_post_armed", runtime_source)

        runbook_text = runbook.read_text(encoding="utf-8").lower()
        for token in (
            "sandbox before production",
            "sales invoice",
            "pos invoice",
            "credit note",
            "reconciliation required",
            "fresh verified backup",
            "no production network call",
            "first live submission",
        ):
            self.assertIn(token, runbook_text)


if __name__ == "__main__":
    unittest.main()
