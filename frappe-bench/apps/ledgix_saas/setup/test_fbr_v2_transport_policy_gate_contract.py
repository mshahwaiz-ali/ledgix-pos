from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
GATE = (APP / "migration" / "fbr_v2_transport_policy_gate.py").read_text(
    encoding="utf-8"
)


class TestFBRV2TransportPolicyGateContract(unittest.TestCase):
    def test_gate_is_local_site_restricted(self):
        self.assertIn("INTEGRATION_SITE", GATE)
        self.assertIn("Refusing FBR V2 transport policy gate", GATE)

    def test_gate_replaces_real_http_transport(self):
        self.assertIn(
            "fbr_transport.post_json = _fake_post_json",
            GATE,
        )
        self.assertIn(
            "fbr_transport.requests_available = _fake_requests_available",
            GATE,
        )
        self.assertNotIn("requests.post(", GATE)

    def test_gate_replaces_profile_token_and_certification_in_memory(self):
        self.assertIn(
            "fbr_v2_transport._profile_for_company = _fake_profile",
            GATE,
        )
        self.assertIn(
            "fbr_v2_transport._token = _fake_token",
            GATE,
        )
        self.assertIn(
            "fbr_v2_transport._production_certification = _fake_production_certification",
            GATE,
        )

    def test_gate_covers_sandbox_validate_and_post_endpoints(self):
        self.assertIn("SANDBOX_VALIDATE_URL", GATE)
        self.assertIn("SANDBOX_POST_URL", GATE)
        self.assertIn('"sandbox_validate_uses_fixed_endpoint"', GATE)
        self.assertIn('"sandbox_post_uses_fixed_endpoint"', GATE)

    def test_gate_covers_production_certification_arm_and_validate_policy(self):
        self.assertIn(
            '"production_validate_allowed_while_post_unarmed"',
            GATE,
        )
        self.assertIn(
            '"production_post_requires_completed_certification"',
            GATE,
        )
        self.assertIn('"production_post_requires_arm"', GATE)

    def test_gate_covers_ambiguous_production_post_matrix(self):
        for marker in (
            '"production_network_error_requires_reconciliation"',
            '"production_http_503_requires_reconciliation"',
            '"production_http_408_requires_reconciliation"',
            '"production_malformed_2xx_requires_reconciliation"',
            '"production_valid_body_without_invoice_number_is_ambiguous"',
            '"production_valid_invoice_number_is_conclusive"',
            '"production_explicit_invalid_is_conclusive_rejection"',
        ):
            self.assertIn(marker, GATE)
        self.assertIn('"requires_reconciliation"', GATE)
        self.assertIn(
            "automatic recovery is intentionally disabled",
            GATE,
        )

    def test_gate_covers_invalid_fbr_body(self):
        self.assertIn('"http_200_invalid_body_fails"', GATE)
        self.assertIn('"FBR Invalid"', GATE)

    def test_gate_proves_no_secret_result_leak(self):
        self.assertIn('"tokens_not_exposed_in_results"', GATE)
        self.assertIn("SANDBOX_SECRET not in serialized_results", GATE)
        self.assertIn("PRODUCTION_SECRET not in serialized_results", GATE)

    def test_gate_intercepts_commit_and_restores_everything(self):
        self.assertIn("frappe.db.commit = _no_commit", GATE)
        self.assertIn("frappe.db.commit = original_commit", GATE)
        self.assertIn(
            "fbr_transport.post_json = original_post_json",
            GATE,
        )
        self.assertIn(
            "fbr_v2_transport._profile_for_company = original_profile",
            GATE,
        )


if __name__ == "__main__":
    unittest.main()
