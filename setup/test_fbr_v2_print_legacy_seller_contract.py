from __future__ import annotations

from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]

PRINTING = (APP / "api" / "printing.py").read_text(encoding="utf-8")
SALES = (APP / "services" / "sales.py").read_text(encoding="utf-8")
GATE = (
    APP / "migration" / "fbr_v2_print_legacy_seller_gate.py"
).read_text(encoding="utf-8")


class TestFBRV2PrintLegacySellerContract(unittest.TestCase):
    def test_native_print_has_no_old_fbr_settings_identity_source(self):
        for forbidden in (
            "Ledgix FBR Settings",
            "seller_ntn_cnic",
            "seller_business_name",
            "seller_province",
            "seller_address",
        ):
            self.assertNotIn(forbidden, PRINTING)

    def test_native_print_prefers_hash_verified_persisted_v2_identity(self):
        for required in (
            "fbr_v2_snapshot_persistence.SNAPSHOT_VERSION",
            "fbr_v2_snapshot_persistence.read_persisted_v2_snapshot(",
            '"persisted_v2"',
            '"identity_source": identity_source',
            '"identity_snapshot_hash": identity_snapshot_hash',
        ):
            self.assertIn(required, PRINTING)

    def test_native_print_fallback_is_erpnext_identity(self):
        self.assertIn(
            "erpnext_fbr_identity.resolve_invoice_identity(doc)",
            PRINTING,
        )
        self.assertIn('"erpnext_live"', PRINTING)

    def test_print_uses_only_non_secret_v2_profile_metadata(self):
        self.assertIn("Ledgix FBR Integration Profile", PRINTING)
        self.assertIn("software_registration_number", PRINTING)
        self.assertIn('"digital_invoicing_logo": ""', PRINTING)
        for forbidden in (
            "sandbox_token",
            "production_token",
            "get_decrypted_password",
        ):
            self.assertNotIn(forbidden, PRINTING)

    def test_legacy_sale_seller_snapshot_no_longer_reads_fbr_settings(self):
        for forbidden in (
            "ledgix_saas.api.fbr_settings",
            "get_fbr_settings_internal",
        ):
            self.assertNotIn(forbidden, SALES)
        self.assertIn(
            "erpnext_fbr_identity.resolve_company_seller_identity(company)",
            SALES,
        )
        self.assertIn("Legacy Brand Snapshot Fallback", SALES)
        self.assertIn("Legacy-only seller snapshot compatibility", SALES)

    def test_runtime_gate_uses_rollback_safe_real_native_fixture(self):
        self.assertIn('if doctype == "Ledgix FBR Settings"', GATE)
        self.assertIn("core._require_native_foundation()", GATE)
        self.assertIn("core._enable_fixture_items()", GATE)
        self.assertIn("core._new_price_list()", GATE)
        self.assertIn("erpnext_selling.build_sales_invoice(", GATE)
        self.assertIn("fbr_v2_snapshot_persistence._profile_active = _force_snapshot_profile", GATE)
        self.assertIn("frappe.db.commit = _no_commit", GATE)
        self.assertIn("frappe.db.rollback()", GATE)
        self.assertIn("fbr_transport.get_json = _forbid_network", GATE)
        self.assertIn("fbr_transport.post_json = _forbid_network", GATE)
        self.assertIn("fbr_v2_transport.validate_invoice = _forbid_v2_transport", GATE)
        self.assertIn("fbr_v2_transport.post_invoice = _forbid_v2_transport", GATE)
        self.assertIn("legacy_retirement.is_frozen()", GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)
        self.assertIn('result["database_persistence"] = (', GATE)
        self.assertIn('"ROLLBACK_CONFIRMED"', GATE)
        self.assertIn('== "ROLLBACK_CONFIRMED"', GATE)
        self.assertIn('"rollback_clean"', GATE)


if __name__ == "__main__":
    unittest.main()
