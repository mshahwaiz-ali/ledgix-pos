from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
SCRIPTS = REPO_ROOT / "scripts"
DOCS = REPO_ROOT / "docs" / "production"


class TestClientReadinessContract(unittest.TestCase):
    def test_readiness_reuses_existing_setup_and_erpnext_authority(self):
        path = APP_ROOT / "api" / "client_readiness.py"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "client_setup.evaluate_client_setup",
            'frappe.db.count("Account"',
            '"Mode of Payment Account"',
            '"Has Role"',
            '"Ledgix Admin"',
            '"Ledgix Manager"',
            '"Ledgix Cashier"',
            '"client_setup_applied"',
            '"payment_account_mapping"',
            '"named_operational_user"',
            '"fbr_pre_activation_interlock"',
            '"release_identity_evidence"',
            '"verified_backup_evidence"',
            '"ERPNext business configuration + Ledgix onboarding evidence"',
        ):
            self.assertIn(token, source)

        for forbidden in (
            "frappe.new_doc",
            ".insert(",
            "install-app",
            "production_token",
            "sandbox_token",
            "set-password",
        ):
            self.assertNotIn(forbidden, source)

    def test_fbr_is_safety_checked_but_not_activated_by_r5(self):
        source = (APP_ROOT / "api" / "client_readiness.py").read_text(encoding="utf-8")
        self.assertIn('doc.get("production_post_armed")', source)
        self.assertIn("must remain unarmed until the dedicated Sandbox-to-Production activation gate", source)
        self.assertIn('"next_workstream": "FBR Sandbox -> Production activation"', source)
        self.assertNotIn("production_post_armed = 1", source)
        self.assertNotIn('set_value("Ledgix FBR Settings"', source)

    def test_evidence_is_private_non_secret_and_release_identified(self):
        source = (APP_ROOT / "api" / "client_readiness.py").read_text(encoding="utf-8")
        for token in (
            'frappe.get_site_path("private", "ledgix-readiness")',
            '"contains_secrets": False',
            '"business_data_authority": "ERPNext"',
            "release_sha must be a full 40-character Git commit SHA",
            'os.chmod(evidence_path, 0o600)',
            'os.chmod(latest_path, 0o600)',
            '"latest_evidence_file": "private/ledgix-readiness/latest.json"',
        ):
            self.assertIn(token, source)

    def test_setup_page_surfaces_operational_onboarding_without_auto_activation(self):
        path = APP_ROOT / "ledgix" / "page" / "ledgix_setup" / "ledgix_setup.js"
        source = path.read_text(encoding="utf-8")
        for token in (
            "Operational onboarding",
            "Refresh Onboarding",
            "ledgix_saas.api.client_readiness.get_client_readiness",
            "strict_evidence: 0",
            "FBR Production remains a separate activation gate",
            "renderOnboarding",
        ):
            self.assertIn(token, source)
        self.assertNotIn("production_post_armed", source)

    def test_r5_gates_and_runbook_exist(self):
        static_gate = SCRIPTS / "run_r5_static_gate.sh"
        runtime_gate = SCRIPTS / "run_r5_client_readiness_gate.sh"
        runbook = DOCS / "client_onboarding_readiness.md"
        self.assertTrue(static_gate.exists())
        self.assertTrue(runtime_gate.exists())
        self.assertTrue(runbook.exists())

        static_source = static_gate.read_text(encoding="utf-8")
        self.assertIn("test_client_readiness_contract", static_source)
        self.assertIn("r5_static_complete=true", static_source)

        runtime_source = runtime_gate.read_text(encoding="utf-8")
        for token in (
            "R5 Client Readiness Gate",
            "run_r5_static_gate.sh",
            "EXACT LEDGIX BENCH APP SYNC",
            "run_ledgix_client_preflight.sh",
            "smoke_test.sh",
            "generate_client_readiness_evidence",
            "r5_readiness_evaluation_complete=true",
            "--require-ready",
        ):
            self.assertIn(token, runtime_source)
        self.assertNotIn("set-password", runtime_source)
        self.assertNotIn("production_post_armed", runtime_source)

        runbook_text = runbook.read_text(encoding="utf-8").lower()
        for token in (
            "erpnext remains the business authority",
            "named user",
            "mode of payment",
            "fbr production remains a separate gate",
            "strict evidence",
            "client-readiness",
            "no client fork",
        ):
            self.assertIn(token, runbook_text)

    def test_offline_smoke_includes_readiness_service(self):
        source = (REPO_ROOT / "deploy" / "smoke_test.sh").read_text(encoding="utf-8")
        self.assertIn('api/client_readiness.py" "client readiness service"', source)
        self.assertIn('"ledgix_saas.api.client_readiness"', source)


if __name__ == "__main__":
    unittest.main()
