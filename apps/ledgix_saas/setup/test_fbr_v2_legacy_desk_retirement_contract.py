from __future__ import annotations

import ast
from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]

PREFLIGHT = (APP / "api" / "fbr_preflight.py").read_text(encoding="utf-8")
PREVIEW = (APP / "api" / "fbr_preview.py").read_text(encoding="utf-8")
TAX = (APP / "api" / "tax_center.py").read_text(encoding="utf-8")
HOOKS = (APP / "hooks.py").read_text(encoding="utf-8")
GATE = (
    APP / "migration" / "fbr_v2_legacy_desk_retirement_gate.py"
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


class TestFBRV2LegacyDeskRetirementContract(unittest.TestCase):
    def test_preflight_is_v2_wrapper_only(self):
        self.assertIn(
            "from ledgix_saas.api import fbr_v2_center",
            PREFLIGHT,
        )
        self.assertIn(
            "return fbr_v2_center.get_fbr_readiness()",
            PREFLIGHT,
        )
        for forbidden in (
            "fbr_settings",
            "get_fbr_settings",
            "get_fbr_control_state",
            "Ledgix Item Tax Profile",
            "Ledgix Sales Return",
        ):
            self.assertNotIn(forbidden, PREFLIGHT)

    def test_legacy_sale_preview_is_fail_closed_in_source(self):
        self.assertIn(
            "fbr_legacy_guard.reject_legacy_fbr_action",
            PREVIEW,
        )
        for forbidden in (
            "fbr_payload",
            "fbr_settings",
            "get_fbr_control_state",
            "_build_sale_invoice_payload_internal",
        ):
            self.assertNotIn(forbidden, PREVIEW)

    def test_tax_center_has_no_old_fbr_settings_dependency(self):
        for forbidden in (
            "ledgix_saas.api.fbr_settings",
            "get_fbr_settings(",
            "get_fbr_control_state(",
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
        ):
            self.assertNotIn(forbidden, TAX)

        self.assertIn(
            "legacy_tax_guard.reject_legacy_tax_action",
            TAX,
        )
        self.assertIn(
            "fbr_v2_center.get_fbr_readiness()",
            TAX,
        )

    def test_tax_center_fbr_readiness_is_only_v2_delegate(self):
        source = _function_source(TAX, "get_fbr_readiness")
        self.assertIn("_require_tax_view()", source)
        self.assertIn(
            "return fbr_v2_center.get_fbr_readiness()",
            source,
        )
        for forbidden in (
            "Ledgix Item Tax Profile",
            "Ledgix Sales Return",
            "_readiness_check(",
        ):
            self.assertNotIn(forbidden, source)

    def test_existing_hook_guards_remain_intact(self):
        self.assertIn(
            '"ledgix_saas.api.tax_center.get_fbr_readiness": '
            '"ledgix_saas.api.fbr_v2_center.get_fbr_readiness"',
            HOOKS,
        )
        self.assertIn(
            '"ledgix_saas.api.fbr_preview.get_fbr_sale_preview": '
            '"ledgix_saas.api.fbr_legacy_guard.reject_legacy_fbr_action"',
            HOOKS,
        )

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
