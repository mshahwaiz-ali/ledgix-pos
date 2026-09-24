from __future__ import annotations

import ast
from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]

CLIENT = (APP / "api" / "fbr_client.py").read_text(encoding="utf-8")
PAYLOAD = (APP / "api" / "fbr_payload.py").read_text(encoding="utf-8")
SUBMISSION = (APP / "api" / "fbr_submission.py").read_text(
    encoding="utf-8"
)
SUPPORT = (
    APP / "services" / "fbr_submission_support.py"
).read_text(encoding="utf-8")
HOOKS = (APP / "hooks.py").read_text(encoding="utf-8")
NATIVE = (APP / "api" / "fbr_native.py").read_text(encoding="utf-8")
GATE = (
    APP / "migration" / "fbr_v2_legacy_transport_retirement_gate.py"
).read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return "\n".join(
                    lines[node.lineno - 1 : node.end_lineno]
                )
    raise AssertionError(f"Function not found: {name}")


class TestFBRV2LegacyTransportRetirementContract(unittest.TestCase):
    def test_legacy_client_has_no_direct_transport_or_old_settings(self):
        for forbidden in (
            "ledgix_saas.api.fbr_settings",
            "get_fbr_settings_internal",
            "get_active_fbr_token",
            "requests.post",
            "_send_fbr_request",
            "SANDBOX_VALIDATE_URL",
            "PRODUCTION_VALIDATE_URL",
            "SANDBOX_POST_URL",
            "PRODUCTION_POST_URL",
        ):
            self.assertNotIn(forbidden, CLIENT)

        for name in ("validate_invoice", "post_invoice"):
            source = _function_source(CLIENT, name)
            self.assertIn("_retired_result(", source)

    def test_submission_engine_is_compatibility_shell(self):
        for forbidden in (
            "from ledgix_saas.api import fbr_client",
            "from ledgix_saas.api.fbr_payload",
            "ledgix_saas.api.fbr_settings",
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
            "fbr_client.validate_invoice",
            "fbr_client.post_invoice",
            "frappe.db.set_value(",
        ):
            self.assertNotIn(forbidden, SUBMISSION)

        self.assertIn(
            "fbr_submission_support as support",
            SUBMISSION,
        )
        self.assertIn(
            "create_submission_log = support.create_submission_log",
            SUBMISSION,
        )
        self.assertIn(
            "status\": \"Retired\"",
            SUBMISSION,
        )

    def test_historical_payload_serializer_has_no_live_settings_authority(self):
        for forbidden in (
            "ledgix_saas.api.fbr_settings",
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
            "get_active_fbr_token",
            "has_any_role",
        ):
            self.assertNotIn(forbidden, PAYLOAD)

        self.assertIn(
            'LEGACY_PAYLOAD_AUTHORITY = "Historical Ledgix Snapshot Serializer"',
            PAYLOAD,
        )
        self.assertIn(
            "legacy_sales.get_seller_identity()",
            PAYLOAD,
        )
        self.assertIn(
            "fbr_legacy_guard.reject_legacy_fbr_action",
            PAYLOAD,
        )

    def test_neutral_support_remains_separate(self):
        for required in (
            "def parse_fbr_response(",
            "def create_submission_log(",
            "def resolve_submission_status(",
            "def submission_lock(",
        ):
            self.assertIn(required, SUPPORT)

        for forbidden in (
            "fbr_client",
            "fbr_settings",
            "fbr_payload",
            "requests.post",
        ):
            self.assertNotIn(forbidden, SUPPORT)

    def test_hooks_and_scheduler_remain_fail_closed(self):
        for method in (
            "fbr_payload.validate_sale_fbr_readiness",
            "fbr_payload.build_sale_invoice_payload",
            "fbr_payload.build_return_invoice_payload",
            "fbr_submission.dry_run_sale_fbr_payload",
            "fbr_submission.validate_sale_with_fbr",
            "fbr_submission.validate_sale_with_fbr_production",
            "fbr_submission.submit_sale_to_fbr",
            "fbr_submission.release_sale_after_fbr_reconciliation",
            "fbr_submission.submit_return_to_fbr",
            "fbr_submission.release_return_after_fbr_reconciliation",
        ):
            self.assertIn(method, HOOKS)

        self.assertIn("scheduler_events = {}", HOOKS)

    def test_native_runtime_does_not_import_legacy_execution_stack(self):
        for forbidden in (
            "from ledgix_saas.api import fbr_client",
            "from ledgix_saas.api import fbr_payload",
            "from ledgix_saas.api import fbr_submission",
            "from ledgix_saas.api.fbr_submission import",
            "from ledgix_saas.api.fbr_payload import",
        ):
            self.assertNotIn(forbidden, NATIVE)

    def test_runtime_gate_forbids_old_settings_and_network(self):
        self.assertIn(
            "fbr_settings.get_fbr_settings_internal = _forbid_legacy",
            GATE,
        )
        self.assertIn(
            "fbr_transport.get_json = _forbid_network",
            GATE,
        )
        self.assertIn(
            "fbr_v2_transport.validate_invoice = _forbid_network",
            GATE,
        )
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertIn('"database_write": False', GATE)


if __name__ == "__main__":
    unittest.main()
