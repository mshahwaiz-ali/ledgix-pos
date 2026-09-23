from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignPhase3ReferenceContract(unittest.TestCase):
    def test_v2_reference_service_uses_only_official_get_endpoints(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        for endpoint in (
            "https://gw.fbr.gov.pk/pdi/v1/provinces",
            "https://gw.fbr.gov.pk/pdi/v1/doctypecode",
            "https://gw.fbr.gov.pk/pdi/v1/transtypecode",
            "https://gw.fbr.gov.pk/pdi/v1/uom",
        ):
            self.assertIn(endpoint, source)

        self.assertIn("fbr_client.requests.get(", source)
        self.assertNotIn("requests.post(", source)
        self.assertNotIn("post_invoice(", source)
        self.assertNotIn("validate_invoice(", source)

    def test_v2_reference_service_is_independent_of_old_fbr_settings(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        for forbidden in (
            "Ledgix FBR Settings",
            "get_fbr_settings_internal",
            "get_active_fbr_token",
            "legacy_reference",
        ):
            self.assertNotIn(forbidden, source)

        self.assertIn('PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"', source)
        self.assertIn("get_decrypted_password(", source)

    def test_documented_v112_response_shapes_are_explicit(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        for field in (
            "stateProvinceCode",
            "stateProvinceDesc",
            "docTypeId",
            "docDescription",
            "transactiON_TYPE_ID",
            "transactiON_DESC",
            "uoM_ID",
            "description",
        ):
            self.assertIn(field, source)

        self.assertIn("unexpected non-list payload", source)
        self.assertIn("does not match the documented v1.12 response shape", source)

    def test_sync_is_non_invoice_and_never_changes_production_arm(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        self.assertIn('"invoice_network_call": False', source)
        self.assertIn('"production_post_armed_changed": False', source)
        self.assertIn('"contains_secrets": False', source)
        self.assertNotIn('"production_post_armed": 1', source)
        self.assertNotIn("production_post_armed = 1", source)

    def test_core_sync_is_savepoint_isolated(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        self.assertIn("frappe.db.savepoint(savepoint)", source)
        self.assertIn("frappe.db.rollback(save_point=savepoint)", source)

    def test_reference_cache_is_non_destructive(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        self.assertIn('"stale"', source)
        self.assertIn('"active": 1', source)
        self.assertNotIn(".delete(", source)
        self.assertNotIn("frappe.delete_doc", source)


if __name__ == "__main__":
    unittest.main()
