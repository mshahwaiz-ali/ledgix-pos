from __future__ import annotations

from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1]
NATIVE = (APP / "api" / "fbr_native.py").read_text(encoding="utf-8")
SUPPORT = (APP / "services" / "fbr_submission_support.py").read_text(encoding="utf-8")
GATE = (APP / "migration" / "fbr_native_legacy_dependency_retirement_gate.py").read_text(encoding="utf-8")


class TestFBRNativeLegacyDependencyRetirementContract(unittest.TestCase):
    def test_native_no_longer_imports_legacy_payload_or_submission_modules(self):
        for forbidden in (
            "from ledgix_saas.api import fbr_payload",
            "ledgix_saas.api.fbr_submission",
            "fbr_payload.",
        ):
            self.assertNotIn(forbidden, NATIVE)

    def test_native_dead_legacy_payload_helper_chain_is_removed(self):
        for forbidden in (
            "def _seller_block(", "def _buyer_block(", "def _line_snapshot(",
            "def _tax_rows(", "def _original_for_return(",
        ):
            self.assertNotIn(forbidden, NATIVE)

    def test_native_uses_neutral_submission_support(self):
        self.assertIn("from ledgix_saas.services.fbr_submission_support import (", NATIVE)
        for symbol in (
            "create_submission_log,", "parse_fbr_response,",
            "resolve_submission_status,", "submission_lock,",
        ):
            self.assertIn(symbol, NATIVE)

    def test_support_is_transport_settings_and_payload_agnostic(self):
        for forbidden in (
            "fbr_client", "fbr_settings", "fbr_payload", "fbr_submission",
            "requests.", "get_fbr_settings_internal", "get_active_fbr_token",
            "fbr_v2_transport",
        ):
            self.assertNotIn(forbidden, SUPPORT)

    def test_support_only_contains_neutral_primitives(self):
        for required in (
            "def parse_fbr_response(", "def resolve_submission_status(",
            "def create_submission_log(", "class _SubmissionLock:",
            "def submission_lock(", 'frappe.new_doc("Ledgix FBR Submission Log")',
        ):
            self.assertIn(required, SUPPORT)

    def test_gate_compares_neutral_parser_and_resolver_to_legacy_behavior(self):
        self.assertIn("support.parse_fbr_response", GATE)
        self.assertIn("legacy.parse_fbr_response", GATE)
        self.assertIn("support.resolve_submission_status", GATE)
        self.assertIn("legacy._resolve_submission_status", GATE)

    def test_gate_exercises_log_and_lock_without_network(self):
        self.assertIn("support.create_submission_log(", GATE)
        self.assertIn("with support.submission_lock(", GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertNotIn("requests.", GATE)

    def test_gate_is_rollback_safe_and_cutover_stays_false(self):
        self.assertIn("frappe.db.rollback()", GATE)
        self.assertIn("frappe.db.commit = _no_commit", GATE)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE", GATE)
        self.assertIn('"rollback_clean"', GATE)


if __name__ == "__main__":
    unittest.main()
