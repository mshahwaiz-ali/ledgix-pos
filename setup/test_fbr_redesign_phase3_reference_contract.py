from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = APP_ROOT / "ledgix" / "doctype"


class TestFBRRedesignPhase3ReferenceContract(unittest.TestCase):
    def test_v2_reference_service_uses_official_get_endpoints(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        for endpoint in (
            "https://gw.fbr.gov.pk/pdi/v1/provinces",
            "https://gw.fbr.gov.pk/pdi/v1/doctypecode",
            "https://gw.fbr.gov.pk/pdi/v1/transtypecode",
            "https://gw.fbr.gov.pk/pdi/v1/uom",
            "https://gw.fbr.gov.pk/pdi/v1/SroSchedule",
            "https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate",
            "https://gw.fbr.gov.pk/pdi/v2/HS_UOM",
            "https://gw.fbr.gov.pk/pdi/v2/SROItem",
        ):
            self.assertIn(endpoint, source)

        transport = (APP_ROOT / "api" / "fbr_transport.py").read_text(encoding="utf-8")
        self.assertIn("requests.get(", transport)
        self.assertNotIn("requests.post(", transport)
        self.assertNotIn("post_invoice(", source)
        self.assertNotIn("validate_invoice(", source)

    def test_v2_reference_service_is_independent_of_old_fbr_settings(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")
        transport = (APP_ROOT / "api" / "fbr_transport.py").read_text(encoding="utf-8")

        for text in (source, transport):
            for forbidden in (
                "Ledgix FBR Settings",
                "get_fbr_settings_internal",
                "get_active_fbr_token",
                "legacy_reference",
            ):
                self.assertNotIn(forbidden, text)

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
            "ratE_ID",
            "ratE_DESC",
            "srO_ID",
            "srO_DESC",
            "srO_ITEM_ID",
            "srO_ITEM_DESC",
            "description",
        ):
            self.assertIn(field, source)

        self.assertIn("unexpected non-list payload", source)
        self.assertIn("does not match the documented v1.12 response shape", source)

    def test_parameterized_query_contract_matches_fbr_v112(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")

        for method in (
            "def sync_rates(",
            "def sync_hs_uoms(",
            "def sync_sro_schedules(",
            "def sync_sro_items(",
        ):
            self.assertIn(method, source)

        for query_name in (
            '"date"',
            '"transTypeId"',
            '"originationSupplier"',
            '"hs_code"',
            '"annexure_id"',
            '"rate_id"',
            '"origination_supplier_csv"',
            '"sro_id"',
        ):
            self.assertIn(query_name, source)

    def test_contextual_cache_prevents_cross_query_collisions(self):
        source = (APP_ROOT / "api" / "fbr_reference_v2.py").read_text(encoding="utf-8")
        controller = (
            DOCTYPE_ROOT
            / "ledgix_fbr_reference_data"
            / "ledgix_fbr_reference_data.py"
        ).read_text(encoding="utf-8")
        schema = json.loads(
            (
                DOCTYPE_ROOT
                / "ledgix_fbr_reference_data"
                / "ledgix_fbr_reference_data.json"
            ).read_text(encoding="utf-8")
        )
        fields = {row["fieldname"]: row for row in schema["fields"]}

        self.assertIn("hashlib.sha256", source)
        self.assertIn("def _canonical_context(", source)
        self.assertIn('"context_key": context_key', source)
        self.assertIn('"context_json": context_json', source)

        self.assertIn("context_key", fields)
        self.assertIn("context_json", fields)
        self.assertEqual(fields["context_key"].get("default"), "GLOBAL")
        self.assertEqual(fields["context_key"].get("read_only"), 1)
        self.assertEqual(fields["context_json"].get("read_only"), 1)

        self.assertIn('"context_key": self.context_key', controller)

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

    def test_transport_is_credential_agnostic(self):
        source = (APP_ROOT / "api" / "fbr_transport.py").read_text(encoding="utf-8")

        self.assertIn("Credential-agnostic HTTP helpers", source)
        self.assertIn("def get_json(", source)
        self.assertIn('"Authorization": f"Bearer {token}"', source)
        for forbidden in (
            "production_post_armed",
            "sandbox_token",
            "production_token",
            "Ledgix FBR Integration Profile",
            "Ledgix FBR Settings",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
