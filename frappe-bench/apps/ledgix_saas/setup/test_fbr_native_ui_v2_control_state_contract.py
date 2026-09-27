from __future__ import annotations

from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
UI = (APP / "api" / "fbr_native_ui.py").read_text(encoding="utf-8")
NATIVE = (APP / "api" / "fbr_native.py").read_text(encoding="utf-8")
GATE = (
    APP / "migration" / "fbr_native_ui_v2_control_state_gate.py"
).read_text(encoding="utf-8")


class TestFBRNativeUIV2ControlStateContract(unittest.TestCase):
    def test_native_ui_has_no_old_global_settings_dependency(self):
        for forbidden in (
            "ledgix_saas.api.fbr_settings",
            "get_fbr_control_state_internal",
            "Ledgix FBR Settings",
        ):
            self.assertNotIn(forbidden, UI)

    def test_control_state_is_derived_from_v2_validation(self):
        self.assertIn("def _v2_control_state(validation: dict)", UI)
        self.assertIn('settings = dict(validation.get("settings") or {})', UI)
        self.assertIn('v2 = dict(validation.get("v2") or {})', UI)
        self.assertIn('"Ledgix FBR Integration Profile"', UI)

    def test_ui_respects_hard_network_cutover(self):
        self.assertIn(
            "cutover_active = bool(fbr_native.V2_NETWORK_CUTOVER_ACTIVE)",
            UI,
        )
        self.assertIn("fbr_native.V2_NETWORK_CUTOVER_MESSAGE", UI)
        self.assertIn('"network_cutover_active": cutover_active', UI)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE = False", NATIVE)

    def test_sandbox_and_production_readiness_are_not_conflated(self):
        self.assertIn(
            'sandbox_transport_ready = bool(v2.get("sandbox_transport_ready"))',
            UI,
        )
        self.assertIn(
            'production_transport_ready = bool(v2.get("production_transport_ready"))',
            UI,
        )
        self.assertIn('mode == "Sandbox"', UI)
        self.assertIn('mode == "Production"', UI)

    def test_production_submit_requires_v2_production_transport_readiness(self):
        self.assertIn(
            "production_post_ready = bool(",
            UI,
        )
        self.assertIn(
            "and production_transport_ready",
            UI,
        )
        self.assertIn(
            "can_manual_submit = production_post_ready",
            UI,
        )

    def test_preview_uses_v2_control_state(self):
        self.assertIn("control = _v2_control_state(validation)", UI)
        self.assertIn('control.get("can_manual_submit")', UI)
        self.assertIn('control.get("can_manual_validate")', UI)

    def test_gate_proves_current_cutover_is_fail_closed(self):
        self.assertIn('"sandbox_actions_blocked_by_cutover"', GATE)
        self.assertIn('"production_actions_blocked_by_cutover"', GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE", GATE)


if __name__ == "__main__":
    unittest.main()
