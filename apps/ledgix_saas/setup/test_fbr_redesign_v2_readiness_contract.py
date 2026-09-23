from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignV2ReadinessContract(unittest.TestCase):
    def setUp(self):
        self.source = (
            APP_ROOT / "services" / "fbr_v2_readiness.py"
        ).read_text(encoding="utf-8")

    def test_readiness_combines_v2_authorities_without_building_payload(self):
        for marker in (
            "erpnext_fbr_identity.resolve_invoice_identity",
            "erpnext_fbr_snapshot.build_snapshot_candidate",
            'PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"',
            'REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"',
            '"payload_built": False',
        ):
            self.assertIn(marker, self.source)

        for forbidden in (
            "build_official_sale_invoice_payload",
            "post_invoice(",
            "validate_invoice(",
            "_send_fbr_request",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_readiness_is_read_only_and_non_secret(self):
        for forbidden in (
            "frappe.db.set_value(",
            ".insert(",
            ".save(",
            ".submit(",
        ):
            self.assertNotIn(forbidden, self.source)

        self.assertIn('"database_write": False', self.source)
        self.assertIn('"fbr_network_call": False', self.source)
        self.assertIn('"contains_secrets": False', self.source)

    def test_official_reference_evidence_is_required(self):
        for marker in (
            '"Province"',
            '"Item Code"',
            '"UOM"',
            '"Transaction Type"',
            '"HS-UOM"',
            '"Rate"',
            "has no cached HS-UOM proof",
            "has no cached SaleTypeToRate proof",
            "not verified against active FBR Item Code reference data",
        ):
            self.assertIn(marker, self.source)

        self.assertIn("fbr_reference_v2._canonical_context", self.source)
        self.assertIn('"annexure_id": "3"', self.source)
        self.assertIn('"originationSupplier": seller_province_id', self.source)

    def test_migrated_review_required_item_mapping_cannot_pass(self):
        self.assertIn('if cint(mapping.get("needs_review")):', self.source)
        self.assertIn("V2 FBR Item Mapping still requires review", self.source)

    def test_unclassified_nonzero_tax_rows_block_payload_readiness(self):
        self.assertIn("def _classify_tax_rows(", self.source)
        self.assertIn('"tax_amount_after_discount_amount"', self.source)
        self.assertIn(
            "non-zero tax/charge rows with no explicit FBR V2 classification",
            self.source,
        )
        self.assertIn('"unclassified": unclassified', self.source)

    def test_sro_rows_remain_fail_closed_until_runtime_semantics_are_proven(self):
        self.assertIn(
            "SRO mapping is present but V2 SRO payload semantics still require",
            self.source,
        )

    def test_transport_readiness_is_stricter_than_payload_input_readiness(self):
        self.assertIn("payload_input_ready = not errors", self.source)
        self.assertIn('profile_state["mode"] == "Sandbox"', self.source)
        self.assertIn('profile_state["sandbox_token_configured"]', self.source)
        self.assertIn('profile_state["mode"] == "Production"', self.source)
        self.assertIn('profile_state["production_token_configured"]', self.source)
        self.assertIn('profile_state["production_post_armed"]', self.source)
        self.assertIn('certification["complete"]', self.source)

    def test_tokens_are_used_only_as_configured_booleans(self):
        self.assertIn("get_decrypted_password(", self.source)
        self.assertIn('"sandbox_token_configured"', self.source)
        self.assertIn('"production_token_configured"', self.source)

        for marker in (
            '"sandbox_token":',
            '"production_token":',
            '"token":',
        ):
            self.assertNotIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
