from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
NEUTRAL = (APP / "api" / "fbr_transport.py").read_text(encoding="utf-8")
V2 = (APP / "api" / "fbr_v2_transport.py").read_text(encoding="utf-8")
REFERENCE = (APP / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")
NATIVE = (APP / "api" / "fbr_native.py").read_text(encoding="utf-8")


class TestFBRV2TransportContract(unittest.TestCase):
    def test_official_di_invoice_endpoints_are_fixed(self):
        for endpoint in (
            "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb",
            "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata",
            "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb",
            "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata",
        ):
            self.assertIn(endpoint, V2)

    def test_credentials_are_company_scoped_v2_profile_passwords(self):
        self.assertIn('PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"', V2)
        self.assertIn('{"company": company}', V2)
        self.assertIn("get_decrypted_password(", V2)
        self.assertIn('"sandbox_token"', V2)
        self.assertIn('"production_token"', V2)
        for forbidden in (
            "get_fbr_settings_internal",
            "get_active_fbr_token",
            "Ledgix FBR Settings",
        ):
            self.assertNotIn(forbidden, V2)

    def test_neutral_transport_is_credential_agnostic(self):
        self.assertIn("def get_json(", NEUTRAL)
        self.assertIn("def post_json(", NEUTRAL)
        self.assertIn("requests.get(", NEUTRAL)
        self.assertIn("requests.post(", NEUTRAL)
        for forbidden in (
            "production_post_armed",
            "sandbox_token",
            "production_token",
            "Ledgix FBR Integration Profile",
            "Ledgix FBR Settings",
        ):
            self.assertNotIn(forbidden, NEUTRAL)

    def test_reference_service_remains_get_only(self):
        self.assertIn("fbr_transport.get_json(", REFERENCE)
        self.assertNotIn("fbr_transport.post_json(", REFERENCE)
        self.assertNotIn("requests.post(", REFERENCE)
        self.assertNotIn("post_invoice(", REFERENCE)
        self.assertNotIn("validate_invoice(", REFERENCE)

    def test_production_post_requires_certification_and_explicit_arm(self):
        self.assertIn('CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"', V2)
        self.assertIn("def _production_certification(profile)", V2)
        self.assertIn('certification.get("complete")', V2)
        self.assertIn("completed Sandbox Certification", V2)
        self.assertIn('mode == "Production"', V2)
        self.assertIn('operation == "post"', V2)
        self.assertIn('profile.get("production_post_armed")', V2)
        self.assertIn("Production posting is not armed", V2)

    def test_uncertain_production_post_requires_reconciliation(self):
        self.assertIn("def _production_post_is_ambiguous", V2)
        self.assertIn('result.get("status") == "Network Error"', V2)
        self.assertIn("http_status in (408,)", V2)
        self.assertIn("http_status >= 500", V2)
        self.assertIn('result.get("status") == "FBR Response Uncertain"', V2)
        self.assertIn("not _invoice_number(response)", V2)
        self.assertIn('"ambiguous_outcome": ambiguous', V2)
        self.assertIn('"requires_reconciliation": ambiguous', V2)
        self.assertIn("automatic recovery is intentionally disabled", V2)

    def test_transport_results_do_not_expose_tokens(self):
        self.assertIn('"contains_secrets": False', V2)
        self.assertNotIn('"token": context["token"]', V2)
        self.assertNotIn('"sandbox_token":', V2)
        self.assertNotIn('"production_token":', V2)

    def test_v2_transport_does_not_persist_business_or_audit_state(self):
        for forbidden in (
            "frappe.db.set_value(",
            ".insert(",
            ".save(",
            ".submit(",
            "create_submission_log",
            "mark_native_fbr_status",
        ):
            self.assertNotIn(forbidden, V2)

    def test_native_network_cutover_is_still_disabled(self):
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE = False", NATIVE)


if __name__ == "__main__":
    unittest.main()
