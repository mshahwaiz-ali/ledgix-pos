from __future__ import annotations

from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]

IDENTITY = (APP / "services" / "erpnext_fbr_identity.py").read_text(
    encoding="utf-8"
)
SETUP = (APP / "api" / "client_setup.py").read_text(encoding="utf-8")
READINESS = (APP / "api" / "client_readiness.py").read_text(
    encoding="utf-8"
)
PAGE = (
    APP / "ledgix" / "page" / "ledgix_setup" / "ledgix_setup.js"
).read_text(encoding="utf-8")
GATE = (
    APP / "migration" / "fbr_v2_client_setup_readiness_gate.py"
).read_text(encoding="utf-8")


class TestFBRV2ClientSetupReadinessContract(unittest.TestCase):
    def test_company_seller_identity_is_erpnext_owned_and_read_only(self):
        self.assertIn(
            "def resolve_company_seller_identity(company_name: str)",
            IDENTITY,
        )
        for required in (
            'company.get("tax_id")',
            'company.get("company_name")',
            'get_default_address("Company", company_name)',
            '"authority": "ERPNext"',
            '"database_write": False',
            '"fbr_network_call": False',
        ):
            self.assertIn(required, IDENTITY)

    def test_client_setup_requires_v2_profile_not_old_settings(self):
        self.assertIn(
            "fbr_v2_readiness.get_company_profile_state(company)",
            SETUP,
        )
        self.assertIn('"fbr_integration_profile"', SETUP)
        self.assertIn("Ledgix FBR Integration Profile", SETUP)
        self.assertIn("Tax & FBR Center", SETUP)
        self.assertNotIn("Ledgix FBR Settings", SETUP)
        self.assertNotIn('"fbr_settings"', SETUP)

    def test_client_readiness_uses_v2_profile_and_erpnext_identity(self):
        for required in (
            "fbr_v2_readiness.get_company_profile_state(company)",
            "erpnext_fbr_identity.resolve_company_seller_identity(company)",
            'state.get("production_post_armed")',
            "Ledgix FBR Integration Profile",
            "Company / Address",
        ):
            self.assertIn(required, READINESS)

        for forbidden in (
            'frappe.get_single("Ledgix FBR Settings")',
            "Ledgix FBR Settings",
            "seller_ntn_cnic",
            "seller_business_name",
            "seller_province",
            "seller_address",
        ):
            self.assertNotIn(forbidden, READINESS)

    def test_setup_page_opens_v2_tax_center(self):
        self.assertIn('__("Tax & FBR Center")', PAGE)
        self.assertIn('frappe.set_route("ledgix-tax-center")', PAGE)
        self.assertNotIn("Ledgix FBR Settings", PAGE)

    def test_runtime_gate_forbids_legacy_settings_and_network(self):
        self.assertIn('if doctype == "Ledgix FBR Settings"', GATE)
        self.assertIn("fbr_transport.get_json = _forbid_network", GATE)
        self.assertIn("fbr_transport.post_json = _forbid_network", GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertIn('"database_write": False', GATE)


if __name__ == "__main__":
    unittest.main()
