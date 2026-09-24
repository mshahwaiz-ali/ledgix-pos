from __future__ import annotations

import ast
from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]

CLIENT = (APP / "api" / "fbr_client.py").read_text(encoding="utf-8")
HEALTH = (APP / "api" / "fbr_health.py").read_text(encoding="utf-8")
STATUS = (APP / "services" / "fbr_v2_status.py").read_text(
    encoding="utf-8"
)
GATE = (
    APP / "migration" / "fbr_v2_health_client_status_gate.py"
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


class TestFBRV2HealthClientStatusContract(unittest.TestCase):
    def test_client_status_is_v2_owned(self):
        source = _function_source(CLIENT, "get_client_status")
        self.assertIn("assert_fbr_v2_view_permission()", source)
        self.assertIn("return get_fbr_v2_status_internal()", source)

    def test_legacy_client_transport_is_retired(self):
        for name in ("validate_invoice", "post_invoice"):
            source = _function_source(CLIENT, name)
            self.assertIn("_retired_result(", source)

        for forbidden in (
            "get_fbr_settings_internal",
            "get_active_fbr_token",
            "requests.post",
            "SANDBOX_VALIDATE_URL",
            "PRODUCTION_VALIDATE_URL",
            "SANDBOX_POST_URL",
            "PRODUCTION_POST_URL",
            "_send_fbr_request",
        ):
            self.assertNotIn(forbidden, CLIENT)

    def test_health_uses_v2_status_only(self):
        self.assertIn("get_fbr_v2_status_internal", HEALTH)
        for forbidden in (
            "ledgix_saas.api.fbr_settings",
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
            "fbr_client",
        ):
            self.assertNotIn(forbidden, HEALTH)

    def test_status_service_has_no_legacy_or_network_call(self):
        for forbidden in (
            "Ledgix FBR Settings",
            "get_fbr_settings_internal",
            "get_active_fbr_token",
            "requests.get",
            "requests.post",
        ):
            self.assertNotIn(forbidden, STATUS)

    def test_health_gate_uses_top_level_v2_status_shape(self):
        self.assertIn('health.get("source")', GATE)
        self.assertNotIn('(health.get("fbr") or {}).get("source")', GATE)

    def test_runtime_gate_has_no_old_settings_dependency_and_blocks_network(self):
        self.assertNotIn("fbr_settings", GATE)
        self.assertIn(
            "fbr_transport.get_json = _forbid_network",
            GATE,
        )
        self.assertIn(
            "fbr_transport.post_json = _forbid_network",
            GATE,
        )
        self.assertIn('"real_fbr_network_calls": 0', GATE)


if __name__ == "__main__":
    unittest.main()
