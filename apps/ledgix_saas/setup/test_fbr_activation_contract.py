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
            "fbr_v2_readiness.get_company_profile_state",
            "fbr_transport.requests_available",
            '"Ledgix FBR Integration Profile"',
            '"ERPNext Company + Company Address"',
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
            "get_fbr_settings_internal",
            "fbr_client.",
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
            '"sandbox_certification_complete"',
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

    def test_static_gate_uses_bench_python_for_frappe_aware_contracts(self):
        source = (SCRIPTS / "run_fbr_activation_static_gate.sh").read_text(encoding="utf-8")
        self.assertIn('BENCH_PYTHON="$BENCH_DIR/env/bin/python"', source)
        self.assertIn('[[ -x "$BENCH_PYTHON" ]]', source)
        self.assertEqual(source.count('"$BENCH_PYTHON" -m unittest -v'), 3)
        self.assertNotIn("  python3 -m unittest -v", source)

    def test_sandbox_operator_is_local_only_and_production_closed(self):
        path = APP_ROOT / "setup" / "fbr_sandbox_operator.py"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            'site.endswith(".local")',
            'site.endswith(".localhost")',
            'SANDBOX_CONFIRMATION = "SEND TO FBR SANDBOX"',
            'PRIVATE_SUBDIR = "ledgix-fbr-activation"',
            'profile.mode = "Sandbox"',
            'profile.submit_trigger = "Manual"',
            "profile.production_post_armed = 0",
            "get_v2_configuration_summary_internal",
            '"ERPNext Company + Company Address"',
            'input_path.unlink(missing_ok=True)',
            'fbr_native.validate_native_with_fbr_internal',
            'fbr_native.submit_native_to_fbr_internal',
            '_existing_sandbox_proof',
            '"production_credentials_changed": False',
            '"production_armed": False',
            '"contains_secrets": False',
        ):
            self.assertIn(token, source)
        for forbidden in (
            '"production_token":',
            'production_post_armed = 1',
            'fbr_client.post_invoice',
            'fbr_client.validate_invoice',
            'get_active_fbr_token',
            'get_fbr_settings_internal',
            'save_fbr_settings',
            '"seller_ntn_cnic"',
            '"seller_business_name"',
            '"seller_province"',
            '"seller_address"',
        ):
            self.assertNotIn(forbidden, source)

    def test_sandbox_shell_helpers_keep_token_out_of_cli_and_require_explicit_send(self):
        configure = SCRIPTS / "configure_fbr_sandbox_local.sh"
        exercise = SCRIPTS / "run_fbr_sandbox_exercise_local.sh"
        self.assertTrue(configure.exists())
        self.assertTrue(exercise.exists())
        configure_source = configure.read_text(encoding="utf-8")
        exercise_source = exercise.read_text(encoding="utf-8")

        for token in (
            "Sandbox token (hidden)",
            "read -r -s -p",
            "sandbox-config-input.$$.json",
            "chmod 600",
            "configure_sandbox_from_private_file",
            "fbr_sandbox_configuration_complete=true",
        ):
            self.assertIn(token, configure_source)
        self.assertIn(
            "Seller identity will be validated from ERPNext Company + Company Address",
            configure_source,
        )
        for forbidden in (
            "SELLER_NTN_CNIC",
            "SELLER_BUSINESS_NAME",
            "SELLER_PROVINCE",
            "SELLER_ADDRESS",
            '"seller_ntn_cnic"',
            '"seller_business_name"',
            '"seller_province"',
            '"seller_address"',
        ):
            self.assertNotIn(forbidden, configure_source)
        self.assertNotIn("--sandbox-token", configure_source)
        self.assertNotIn("--production-token", configure_source)

        for token in (
            "--list-candidates",
            '--confirm "SEND TO FBR SANDBOX"',
            "list_sandbox_candidates",
            "exercise_sandbox_reference",
            "fbr_sandbox_exercise_complete=true",
        ):
            self.assertIn(token, exercise_source)
        self.assertNotIn("--production-token", exercise_source)
        self.assertNotIn("post_invoice(", exercise_source)
        self.assertEqual(
            exercise_source.count(
                'LEDGIX_FBR_SANDBOX_NETWORK_EXERCISE="$CONFIRMATION"'
            ),
            1,
        )

    def test_sandbox_network_cutover_bypass_is_explicit_and_sandbox_only(self):
        source = (APP_ROOT / "api" / "fbr_native.py").read_text(encoding="utf-8")
        for token in (
            'V2_NETWORK_CUTOVER_ACTIVE = False',
            'SANDBOX_NETWORK_EXERCISE_ENV = "LEDGIX_FBR_SANDBOX_NETWORK_EXERCISE"',
            'SANDBOX_NETWORK_EXERCISE_CONFIRMATION = "SEND TO FBR SANDBOX"',
            'str(mode or "").strip() == "Sandbox"',
            'os.environ.get(SANDBOX_NETWORK_EXERCISE_ENV)',
            '_sandbox_network_exercise_allowed(mode)',
            'Production remains blocked.',
        ):
            self.assertIn(token, source)

        helper_start = source.index("def _sandbox_network_exercise_allowed")
        helper_end = source.index("\n\ndef _require_role", helper_start)
        helper = source[helper_start:helper_end]
        self.assertNotIn('"Production"', helper)

        exercise_source = (
            SCRIPTS / "run_fbr_sandbox_exercise_local.sh"
        ).read_text(encoding="utf-8")
        invocation = (
            'LEDGIX_FBR_SANDBOX_NETWORK_EXERCISE="$CONFIRMATION" '
            'bench_run --site "$SITE" execute '
            'ledgix_saas.setup.fbr_sandbox_operator.exercise_sandbox_reference'
        )
        self.assertIn(invocation, exercise_source)
        self.assertNotIn("export LEDGIX_FBR_SANDBOX_NETWORK_EXERCISE", exercise_source)

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
