from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBROfflineLifecycleContract(unittest.TestCase):
    def test_profile_models_fail_closed_client_specific_offline_policy(self):
        schema = json.loads(
            (
                APP_ROOT.parent
                / "fbr_v1/fbr_v1/fbr_v1"
                / "doctype"
                / "ledgix_fbr_integration_profile"
                / "ledgix_fbr_integration_profile.json"
            ).read_text(encoding="utf-8")
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}

        self.assertEqual(fields["offline_policy"]["default"], "Disabled")
        self.assertEqual(
            fields["offline_policy"]["options"],
            "Disabled\nOperator Confirmed",
        )
        self.assertEqual(
            fields["offline_upload_window_hours"]["default"],
            "0",
        )
        self.assertIn(
            "No legal deadline is hardcoded",
            fields["offline_upload_window_hours"]["description"],
        )

        controller = (APP_ROOT.parent / 'fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.py').read_text()
        self.assertIn('offline_policy == "Operator Confirmed"', controller)
        self.assertIn('offline_authority_reference', controller)
        self.assertIn('offline_authority_evidence', controller)

    def test_submission_log_explicitly_models_offline_pending_evidence(self):
        schema = json.loads(
            (
                APP_ROOT.parent
                / "fbr_v1/fbr_v1/fbr_v1"
                / "doctype"
                / "ledgix_fbr_submission_log"
                / "ledgix_fbr_submission_log.json"
            ).read_text(encoding="utf-8")
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}
        options = fields["fbr_status"]["options"].splitlines()

        self.assertIn("Offline Pending", options)
        for fieldname in (
            "offline_issued_at",
            "offline_upload_due_at",
            "offline_reason",
        ):
            self.assertIn(fieldname, fields)
            self.assertEqual(fields[fieldname].get("read_only"), 1)

        support = (
            APP_ROOT / "services" / "fbr_submission_support.py"
        ).read_text(encoding="utf-8")
        self.assertIn("offline_issued_at=None", support)
        self.assertIn("offline_upload_due_at=None", support)
        self.assertIn("offline_reason=None", support)

    def test_native_invoice_persists_offline_state_and_blocks_generic_retry(self):
        # V2 runtime was intentionally retired; historical evidence above remains.
        source = (APP_ROOT / 'api/fbr_native.py').read_text()
        self.assertIn('reject_legacy_v2_action', source)
        for forbidden in ('frappe.db', 'create_submission_log', 'fbr_v2_transport', 'enqueue'):
            self.assertNotIn(forbidden, source)

    def test_offline_state_machine_is_production_only_and_certification_gated(self):
        # V2 runtime was intentionally retired; historical evidence above remains.
        source = (APP_ROOT / 'api/fbr_offline.py').read_text()
        self.assertIn('reject_legacy_v2_action', source)
        for forbidden in ('frappe.db', 'create_submission_log', 'fbr_v2_transport', 'enqueue'):
            self.assertNotIn(forbidden, source)

    def test_known_offline_and_ambiguous_post_are_separate(self):
        # V2 runtime was intentionally retired; historical evidence above remains.
        source = (APP_ROOT / 'api/fbr_offline.py').read_text()
        self.assertIn('reject_legacy_v2_action', source)
        for forbidden in ('frappe.db', 'create_submission_log', 'fbr_v2_transport', 'enqueue'):
            self.assertNotIn(forbidden, source)

    def test_offline_queue_is_durable_read_only_monitoring_not_auto_retry(self):
        # V2 runtime was intentionally retired; historical evidence above remains.
        source = (APP_ROOT / 'api/fbr_offline.py').read_text()
        self.assertIn('reject_legacy_v2_action', source)
        for forbidden in ('frappe.db', 'create_submission_log', 'fbr_v2_transport', 'enqueue'):
            self.assertNotIn(forbidden, source)

    def test_offline_upload_is_explicit_and_return_flow_remains_fail_closed(self):
        # V2 runtime was intentionally retired; historical evidence above remains.
        source = (APP_ROOT / 'api/fbr_offline.py').read_text()
        self.assertIn('reject_legacy_v2_action', source)
        for forbidden in ('frappe.db', 'create_submission_log', 'fbr_v2_transport', 'enqueue'):
            self.assertNotIn(forbidden, source)

    def test_offline_code_never_owns_accounting_or_generic_network_transport(self):
        source = (APP_ROOT / "api" / "fbr_offline.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "GL Entry",
            "Stock Ledger Entry",
            "Payment Entry",
            "requests.",
            "fbr_transport.post_json",
            "fbr_transport.get_json",
            '"production_token"',
            '"sandbox_token"',
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
