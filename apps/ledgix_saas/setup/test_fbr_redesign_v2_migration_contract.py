from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignV2MigrationContract(unittest.TestCase):
    def setUp(self):
        self.source = (
            APP_ROOT / "migration" / "fbr_redesign_v2_migration.py"
        ).read_text(encoding="utf-8")

    def test_migration_is_local_integration_site_only(self):
        self.assertIn("INTEGRATION_SITE", self.source)
        self.assertIn("frappe.local.site != INTEGRATION_SITE", self.source)
        self.assertIn("restricted to {INTEGRATION_SITE!r}", self.source)

    def test_preview_is_read_only_and_non_secret(self):
        self.assertIn("def preview_v2_migration(", self.source)
        self.assertIn('"read_only": True', self.source)
        self.assertIn('"contains_secrets": False', self.source)
        self.assertIn('"production_post_armed_changed": False', self.source)

        preview_block = self.source.split(
            "def preview_v2_migration(", 1
        )[1].split("def _copy_password_if_present(", 1)[0]
        for forbidden in (
            "get_decrypted_password(",
            ".insert(",
            ".save(",
            "frappe.db.set_value(",
        ):
            self.assertNotIn(forbidden, preview_block)

    def test_destination_profile_is_always_fail_closed(self):
        for marker in (
            'doc.enabled = 0',
            'doc.mode = "Disabled"',
            'doc.submit_trigger = "Manual"',
            'doc.production_post_armed = 0',
            '"production_post_armed": False',
            '"fbr_submission_enabled": False',
        ):
            self.assertIn(marker, self.source)

        self.assertNotIn("production_post_armed = 1", self.source)
        self.assertNotIn('"mode": "Production"', self.source)

    def test_passwords_can_copy_without_being_returned(self):
        self.assertIn("def _copy_password_if_present(", self.source)
        self.assertIn("get_decrypted_password(", self.source)
        self.assertIn("target_doc.set_password(", self.source)
        self.assertIn('"sandbox_token_copied"', self.source)
        self.assertIn('"production_token_copied"', self.source)
        self.assertIn('"contains_secrets": False', self.source)

        for secret_return in (
            '"sandbox_token": value',
            '"production_token": value',
            '"token": value',
        ):
            self.assertNotIn(secret_return, self.source)

    def test_monetary_tax_authority_is_explicitly_not_migrated(self):
        for field in (
            "default_tax_rate",
            "sales_tax_withheld_at_source_per_unit",
            "extra_tax_per_unit",
            "further_tax_per_unit",
            "fed_payable_per_unit",
        ):
            self.assertIn(field, self.source)

        self.assertIn("IGNORED_MONETARY_FIELDS", self.source)
        self.assertIn('"ignored_monetary_fields"', self.source)
        self.assertIn("Monetary tax fields and Sandbox scenario were intentionally not migrated", self.source)

    def test_sandbox_scenario_does_not_move_to_item_mapping(self):
        self.assertIn('"scenario_id": row.get("scenario_id") or ""', self.source)
        self.assertIn('"ignored_sandbox_scenarios"', self.source)

        create_block = self.source.split(
            "def _create_item_mapping(", 1
        )[1].split("def apply_v2_migration(", 1)[0]
        self.assertNotIn('"scenario_id"', create_block)

    def test_item_mapping_is_review_required(self):
        self.assertIn('"needs_review": True', self.source)
        self.assertIn('"create_review_required"', self.source)
        self.assertIn("Review against official FBR reference data before use.", self.source)

    def test_apply_requires_explicit_confirmation_and_zero_blockers(self):
        self.assertIn(
            'APPLY_CONFIRMATION = "APPLY FBR V2 LOCAL MIGRATION"',
            self.source,
        )
        self.assertIn("if str(confirmation or "") != APPLY_CONFIRMATION:", self.source)
        self.assertIn('if preview["blockers"]:', self.source)
        self.assertIn("Resolve the preview blockers before apply", self.source)
        self.assertIn('frappe.db.savepoint(savepoint)', self.source)
        self.assertIn('frappe.db.rollback(save_point=savepoint)', self.source)

    def test_duplicated_legacy_seller_identity_is_not_migrated(self):
        self.assertIn('"duplicated_seller_identity_present"', self.source)
        self.assertIn('"duplicated_seller_identity"', self.source)

        profile_apply = self.source.split(
            "def _apply_profile(", 1
        )[1].split("def _create_item_mapping(", 1)[0]
        for field in (
            "seller_ntn_cnic",
            "seller_business_name",
            "seller_province",
            "seller_address",
        ):
            self.assertNotIn(f"doc.{field}", profile_apply)


if __name__ == "__main__":
    unittest.main()
