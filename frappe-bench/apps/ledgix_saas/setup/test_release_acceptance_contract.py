from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
SCRIPTS = REPO_ROOT / "scripts"
DOCS = REPO_ROOT / "docs" / "production"


class TestReleaseAcceptanceContract(unittest.TestCase):
    def test_phase12_release_verifier_is_transitively_read_only(self):
        verifier = APP_ROOT / "setup" / "phase12_read_only.py"
        recovery = APP_ROOT / "setup" / "recovery.py"
        self.assertTrue(verifier.exists())
        source = verifier.read_text(encoding="utf-8")
        for token in (
            "verify_frozen_snapshot_read_only",
            "legacy_retirement.capture_legacy_snapshot",
            "legacy_retirement.build_reconciliation",
            '"read_only": True',
        ):
            self.assertIn(token, source)
        for forbidden in (
            ".save(",
            "frappe.db.set_value",
            "frappe.db.commit",
            "freeze_legacy_history",
            "release_legacy_freeze_for_rollback",
            "verify_frozen_snapshot()",
        ):
            self.assertNotIn(forbidden, source)

        recovery_source = recovery.read_text(encoding="utf-8")
        self.assertIn("verify_frozen_snapshot_read_only", recovery_source)
        self.assertNotIn("legacy_retirement.verify_frozen_snapshot()", recovery_source)
        self.assertIn("phase12_verification_is_read_only", recovery_source)

    def test_acceptance_reuses_native_readiness_prints_and_phase12(self):
        source = (APP_ROOT / "api" / "release_acceptance.py").read_text(encoding="utf-8")
        for token in (
            "client_readiness.evaluate_client_readiness",
            "fbr_activation.evaluate_fbr_activation_readiness",
            "verify_frozen_snapshot_read_only",
            'A4_PRINT_FORMAT = "Ledgix ERPNext Tax Invoice"',
            'POS_PRINT_FORMAT = "Ledgix ERPNext POS Receipt"',
            '"Sales Invoice"',
            '"POS Invoice"',
            '"release_setup_ready"',
            '"manual_uat_ready"',
            '"fbr_external_certification_complete"',
            '"production_release_ready"',
            '"business_data_authority": "ERPNext"',
        ):
            self.assertIn(token, source)
        for forbidden in (
            "validate_native_with_fbr_internal",
            "submit_native_to_fbr_internal",
            "production_post_armed = 1",
            "frappe.new_doc",
        ):
            self.assertNotIn(forbidden, source)

    def test_manual_uat_is_explicit_private_profile_aware_evidence(self):
        source = (APP_ROOT / "api" / "release_acceptance.py").read_text(encoding="utf-8")
        for token in (
            'MANUAL_UAT_CONFIRMATION = "RECORD LEDGIX MANUAL UAT"',
            '"sales_invoice_a4"',
            '"role_boundary"',
            '"pos_thermal_receipt"',
            '"barcode_item_selection"',
            '"checkout_payment"',
            '"pos_return"',
            '"pos_closing"',
            '"stock_effect"',
            '"cashier_device_login"',
            '"purchase_receipt_valuation"',
            '"stock_entry_reconciliation"',
            'frappe.get_site_path("private", "ledgix-acceptance", "manual-uat.json")',
            "os.chmod(path, 0o600)",
            '"manual_human_evidence": True',
        ):
            self.assertIn(token, source)

    def test_release_gates_are_fail_closed_and_non_sending(self):
        static_gate = SCRIPTS / "run_release_acceptance_static_gate.sh"
        local_gate = SCRIPTS / "run_release_acceptance_readiness_gate.sh"
        prod_gate = SCRIPTS / "run_ledgix_production_release_gate.sh"
        for path in (static_gate, local_gate, prod_gate):
            self.assertTrue(path.exists(), path.name)

        static_source = static_gate.read_text(encoding="utf-8")
        for token in (
            "test_erpnext_phase10_contract",
            "test_backup_restore_contract",
            "test_client_readiness_contract",
            "test_fbr_activation_contract",
            "test_release_acceptance_contract",
            "release_acceptance_static_complete=true",
        ):
            self.assertIn(token, static_source)

        local_source = local_gate.read_text(encoding="utf-8")
        for token in (
            "generate_release_acceptance_evidence",
            "release_setup_ready=",
            "manual_uat_ready=",
            "fbr_external_certification_complete=",
            "production_release_ready=",
            "release_acceptance_readiness_complete=true",
        ):
            self.assertIn(token, local_source)
        self.assertNotIn("submit_native_to_fbr", local_source)
        self.assertNotIn("validate_native_with_fbr", local_source)

        prod_source = prod_gate.read_text(encoding="utf-8")
        for token in (
            "--site",
            "--url",
            "--release",
            "--require-fbr-production",
            "moving branch names are not accepted",
            "smoke_test.sh",
            "--all",
            "production_release_ready",
            "ledgix_production_release_gate_complete=true",
        ):
            self.assertIn(token, prod_source)
        for forbidden in (
            "git checkout",
            "git pull",
            "deploy_update_safe.sh",
            "submit_native_to_fbr",
            "production_post_armed=1",
        ):
            self.assertNotIn(forbidden, prod_source)

    def test_runbooks_exist_and_keep_external_certification_separate(self):
        printing = DOCS / "printing_devices_uat.md"
        final = DOCS / "final_release_gate.md"
        self.assertTrue(printing.exists())
        self.assertTrue(final.exists())
        printing_text = printing.read_text(encoding="utf-8").lower()
        final_text = final.read_text(encoding="utf-8").lower()
        for token in ("a4", "thermal", "barcode", "pos closing", "role boundary", "manual uat"):
            self.assertIn(token, printing_text)
        for token in (
            "immutable release",
            "verified backup",
            "online smoke",
            "phase 12",
            "fbr",
            "external",
            "no production network call",
        ):
            self.assertIn(token, final_text)


if __name__ == "__main__":
    unittest.main()
