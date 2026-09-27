from __future__ import annotations

from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
LEGACY = (APP / "api" / "fbr_reference.py").read_text(encoding="utf-8")
V2 = (APP / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")
GATE = (
    APP / "migration" / "fbr_legacy_reference_retirement_gate.py"
).read_text(encoding="utf-8")


class TestFBRLegacyReferenceRetirementContract(unittest.TestCase):
    def test_legacy_reference_module_has_no_network_or_legacy_credentials(self):
        for forbidden in (
            "fbr_client",
            "fbr_settings",
            "get_active_fbr_token",
            "get_fbr_settings_internal",
            "requests.get",
            "requests.post",
            "Authorization",
            "Bearer",
        ):
            self.assertNotIn(forbidden, LEGACY)

    def test_legacy_reference_public_names_remain_fail_closed(self):
        for name in (
            "get_provinces",
            "get_document_types",
            "get_transaction_types",
            "get_uoms",
            "get_rates",
            "get_hs_uoms",
            "get_sro_schedules",
            "get_sro_items",
            "get_sales_tax_registration_status",
            "get_registration_type",
        ):
            self.assertIn(f"def {name}(", LEGACY)

        self.assertIn("LEGACY_REFERENCE_RETIRED_MESSAGE", LEGACY)
        self.assertIn("return _retired()", LEGACY)
        self.assertIn("Ledgix FBR Integration Profile", LEGACY)

    def test_canonical_v2_reference_service_remains_profile_scoped_get_only(self):
        self.assertIn(
            'PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"',
            V2,
        )
        self.assertIn("def _reference_get(", V2)
        self.assertIn("fbr_transport.get_json(", V2)
        self.assertNotIn("requests.post(", V2)
        self.assertNotIn("post_invoice(", V2)
        self.assertNotIn("validate_invoice(", V2)

    def test_gate_calls_all_legacy_public_reference_functions(self):
        for name in (
            "get_provinces",
            "get_document_types",
            "get_transaction_types",
            "get_uoms",
            "get_rates",
            "get_hs_uoms",
            "get_sro_schedules",
            "get_sro_items",
            "get_sales_tax_registration_status",
            "get_registration_type",
        ):
            self.assertIn(f"fbr_reference.{name}", GATE)

    def test_gate_forbids_any_real_fbr_transport(self):
        self.assertIn(
            "fbr_transport.get_json = _forbid_get",
            GATE,
        )
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE", GATE)


if __name__ == "__main__":
    unittest.main()
