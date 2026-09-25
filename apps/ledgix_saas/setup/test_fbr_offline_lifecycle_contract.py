from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBROfflineLifecycleContract(unittest.TestCase):
    def test_profile_models_fail_closed_client_specific_offline_policy(self):
        schema = json.loads(
            (
                APP_ROOT
                / "ledgix"
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

        controller = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_fbr_integration_profile"
            / "ledgix_fbr_integration_profile.py"
        ).read_text(encoding="utf-8")
        self.assertIn('offline_policy == "Operator Confirmed"', controller)
        self.assertIn("offline_upload_window_hours", controller)
        self.assertIn(
            '"Offline Upload Window (Hours) must be configured from the current "',
            controller,
        )
        self.assertIn(
            '"client/provider rule before Known Offline Policy can be enabled."',
            controller,
        )

    def test_submission_log_explicitly_models_offline_pending_evidence(self):
        schema = json.loads(
            (
                APP_ROOT
                / "ledgix"
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
        extensions = (
            APP_ROOT / "setup" / "erpnext_phase9_extensions.py"
        ).read_text(encoding="utf-8")
        for marker in (
            '"Offline Pending"',
            '"custom_ledgix_fbr_upload_due_at"',
            '"custom_ledgix_fbr_offline_issued_at"',
            '"custom_ledgix_fbr_offline_reason"',
        ):
            self.assertIn(marker, extensions)

        native = (APP_ROOT / "api" / "fbr_native.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            'OFFLINE_PENDING = "Offline Pending"',
            "allow_offline_upload: bool = False",
            'status.get("fbr_status") == OFFLINE_PENDING',
            "Use the controlled ",
            "offline-upload workflow; generic submission is blocked.",
            "Controlled offline upload requires an Offline Pending invoice.",
            "clear_upload_due_at=bool(",
            "RECONCILIATION_REQUIRED, OFFLINE_PENDING",
        ):
            self.assertIn(marker, native)

    def test_offline_state_machine_is_production_only_and_certification_gated(self):
        source = (APP_ROOT / "api" / "fbr_offline.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            'DECLARE_OFFLINE_CONFIRMATION = "DECLARE KNOWN OFFLINE"',
            'UPLOAD_OFFLINE_CONFIRMATION = "UPLOAD OFFLINE INVOICE"',
            "V2_NETWORK_CUTOVER_ACTIVE",
            'state.get("mode")) != "Production"',
            "production_token_configured",
            "production_post_armed",
            'certification.get("complete")',
            'offline_policy != "Operator Confirmed"',
            "upload_window_hours <= 0",
        ):
            self.assertIn(marker, source)

        self.assertNotIn("24", source)
        self.assertNotIn("72", source)
        self.assertNotIn("168", source)

    def test_known_offline_and_ambiguous_post_are_separate(self):
        source = (APP_ROOT / "api" / "fbr_offline.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "Ambiguous Production POST is a reconciliation case, not Known Offline.",
            "Known Offline cannot be declared after a Production POST attempt.",
            "_prior_production_post_attempts(",
            'response.get("fbr_mode")) == "Production"',
            'response.get("fbr_operation")).lower() == "post"',
            "Reconciliation Required cannot use the Known Offline upload path.",
        ):
            self.assertIn(marker, source)

    def test_offline_queue_is_durable_read_only_monitoring_not_auto_retry(self):
        source = (APP_ROOT / "api" / "fbr_offline.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def list_offline_queue_internal(", source)
        self.assertIn('"custom_ledgix_fbr_status": OFFLINE_PENDING', source)
        self.assertIn('"overdue_count"', source)
        self.assertIn('"database_write": False', source)
        self.assertNotIn("enqueue(", source)
        self.assertNotIn("enqueue_after_commit", source)

        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertIn("scheduler_events = {}", hooks)

    def test_offline_upload_is_explicit_and_return_flow_remains_fail_closed(self):
        source = (APP_ROOT / "api" / "fbr_offline.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "def upload_offline_native_internal(",
            "allow_offline_upload=True",
            "offline_pending_preserved",
            "Known Offline return/note issuance remains blocked",
            "Debit/Credit Note contract is proven in Sandbox",
        ):
            self.assertIn(marker, source)

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
