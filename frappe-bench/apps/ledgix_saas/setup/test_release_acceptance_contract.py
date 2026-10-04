from __future__ import annotations

import unittest
from unittest.mock import patch
from contextlib import ExitStack
import frappe
from fbr_v1.setup.v1_test_support import NoNetworkTest, Row
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[2]
SCRIPTS = REPO_ROOT / "scripts" / "release"
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
            "fbr_v1_bridge.get_company_readiness",
            "verify_frozen_snapshot_read_only",
            'A4_PRINT_FORMAT = "Ledgix ERPNext Tax Invoice"',
            'POS_PRINT_FORMAT = "Ledgix ERPNext POS Receipt"',
            '"Sales Invoice"',
            '"POS Invoice"',
            '"release_setup_ready"',
            '"manual_uat_ready"',
            '"fbr_external_production_approval_complete"',
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
            "test_fbr_v1_bridge_contract",
            "test_fbr_v1_readiness_runtime",
            "test_sandbox_acceptance_runtime",
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
            "fbr_external_production_approval_complete=",
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


class TestReleaseAcceptanceBehavior(NoNetworkTest):
    def inspect(self, sandbox_complete, production_ready=False, approval=False, missing_gate=None, enable_fbr=True):
        from ledgix_saas.api import release_acceptance as api
        operational = {'ready': True, 'features': {'enable_fbr': enable_fbr},
                       'identity': {'company': 'Shop'}, 'blockers': []}
        state = {'sandbox_transport_acceptance_complete': sandbox_complete,
                 'external_production_approval_complete': approval,
                 'production_configuration_ready': production_ready,
                 'network_cutover_active': True, 'production_cutover_active': True,
                 'profile_state': {'production_post_armed': 1, 'transport_enabled': 1},
                 'database_write': False, 'fbr_network_call': False}
        if missing_gate in ('production_post_armed', 'transport_enabled'):
            state['profile_state'][missing_gate] = 0
        elif missing_gate:
            state[missing_gate] = False
        with ExitStack() as stack:
            stack.enter_context(patch.object(frappe, 'get_roles', return_value=['Ledgix Admin']))
            stack.enter_context(patch.object(api.client_readiness, 'evaluate_client_readiness', return_value=operational))
            stack.enter_context(patch.object(api, 'verify_frozen_snapshot_read_only', return_value={'frozen': True, 'matches': True, 'read_only': True}))
            stack.enter_context(patch.object(api, '_print_checks', return_value=([], {})))
            stack.enter_context(patch.object(api, '_load_manual_uat', return_value={'valid': True, 'results': {}}))
            stack.enter_context(patch.object(api, '_required_uat_keys', return_value=[]))
            bridge = stack.enter_context(patch.object(api.fbr_v1_bridge, 'get_company_readiness', return_value=state))
            result = api.evaluate_release_acceptance(require_fbr_production=1)
            if enable_fbr:
                bridge.assert_called_once_with('Shop')
            else:
                bridge.assert_not_called()
        self.db.set_value.assert_not_called()
        self.db.commit.assert_not_called()
        self.assertFalse(result['network_call_made'])
        self.assertFalse(result['production_armed_by_gate'])
        return result

    def test_v1_sandbox_completion_is_consumed_but_not_production_authority(self):
        result = self.inspect(True)
        self.assertFalse(result['fbr_external_production_approval_complete'])
        self.assertTrue(result['fbr_sandbox_transport_acceptance_complete'])
        self.assertFalse(result['production_release_ready'])

    def test_missing_v1_sandbox_evidence_blocks_required_fbr_release(self):
        result = self.inspect(False, production_ready=True)
        self.assertFalse(result['fbr_external_production_approval_complete'])
        self.assertFalse(result['production_release_ready'])

    def test_separate_sandbox_and_production_requirements_must_both_pass(self):
        self.assertTrue(self.inspect(True, production_ready=True, approval=True)['production_release_ready'])

    def test_every_production_prerequisite_is_independent(self):
        for gate in ('sandbox_transport_acceptance_complete', 'external_production_approval_complete',
                     'production_configuration_ready', 'network_cutover_active', 'production_cutover_active',
                     'production_post_armed', 'transport_enabled'):
            with self.subTest(gate=gate):
                self.assertFalse(self.inspect(True, True, True, missing_gate=gate)['production_release_ready'])

    def test_non_fbr_client_unaffected(self):
        self.assertTrue(self.inspect(False, enable_fbr=False)['production_release_ready'])

    def test_configuration_alone_and_approval_alone_block(self):
        self.assertFalse(self.inspect(True, True)['production_release_ready'])
        self.assertFalse(self.inspect(True, False, True)['production_release_ready'])


if __name__ == "__main__":
    unittest.main()
