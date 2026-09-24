from __future__ import annotations

from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    for candidate in (APP, *APP.parents):
        if (candidate / "scripts" / "configure_fbr_sandbox_local.sh").is_file():
            return candidate
    raise RuntimeError(
        "Could not locate Ledgix repository root from activation contract."
    )


REPO = _repo_root()

ACTIVATION = (APP / "api" / "fbr_activation.py").read_text(encoding="utf-8")
OPERATOR = (APP / "setup" / "fbr_sandbox_operator.py").read_text(
    encoding="utf-8"
)
READINESS = (APP / "services" / "fbr_v2_readiness.py").read_text(
    encoding="utf-8"
)
CONFIGURE = (REPO / "scripts" / "configure_fbr_sandbox_local.sh").read_text(
    encoding="utf-8"
)
GATE = (
    APP / "migration" / "fbr_v2_activation_profile_gate.py"
).read_text(encoding="utf-8")


class TestFBRV2ActivationProfileContract(unittest.TestCase):
    def test_safe_company_profile_state_exists(self):
        self.assertIn(
            "def get_company_profile_state(company: str)",
            READINESS,
        )
        self.assertIn(
            '"sandbox_certification": _sandbox_certification(profile)',
            READINESS,
        )
        self.assertIn('"contains_secrets": False', READINESS)

    def test_activation_uses_v2_profile_and_erpnext_identity(self):
        for forbidden in (
            "get_fbr_settings_internal",
            "get_active_fbr_token",
            "save_fbr_settings",
            "fbr_client.",
            "Ledgix FBR Settings",
        ):
            self.assertNotIn(forbidden, ACTIVATION)

        for required in (
            "fbr_v2_readiness.get_company_profile_state",
            "fbr_transport.requests_available",
            '"source": "Ledgix FBR Integration Profile"',
            '"seller_identity_source": "ERPNext Company + Company Address"',
            '"sandbox_certification_complete"',
        ):
            self.assertIn(required, ACTIVATION)

    def test_operator_writes_only_v2_fbr_specific_state(self):
        for forbidden in (
            "get_fbr_settings_internal",
            "save_fbr_settings",
            '"seller_ntn_cnic"',
            '"seller_business_name"',
            '"seller_province"',
            '"seller_address"',
        ):
            self.assertNotIn(forbidden, OPERATOR)

        for required in (
            "get_v2_configuration_summary_internal",
            'profile.mode = "Sandbox"',
            'profile.submit_trigger = "Manual"',
            "profile.production_post_armed = 0",
            'profile.set_password("sandbox_token", sandbox_token)',
            '"seller_identity_source": "ERPNext Company + Company Address"',
        ):
            self.assertIn(required, OPERATOR)

    def test_configure_shell_stages_no_duplicate_seller_identity(self):
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
            self.assertNotIn(forbidden, CONFIGURE)

        self.assertIn(
            "Seller identity will be validated from ERPNext Company + Company Address",
            CONFIGURE,
        )
        self.assertIn("Sandbox token (hidden)", CONFIGURE)

    def test_runtime_gate_has_no_old_control_plane_dependency_and_blocks_network(self):
        self.assertNotIn("fbr_settings", GATE)
        self.assertNotIn("fbr_client.requests_available", GATE)
        self.assertIn("fbr_transport.get_json = _forbid_network", GATE)
        self.assertIn("fbr_transport.post_json = _forbid_network", GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE", GATE)


if __name__ == "__main__":
    unittest.main()
