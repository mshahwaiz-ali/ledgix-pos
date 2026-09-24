from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignV2MigrationContract(unittest.TestCase):
    def setUp(self):
        self.source = (
            APP_ROOT / "migration" / "fbr_redesign_v2_migration.py"
        ).read_text(encoding="utf-8")

    def test_historical_entry_points_remain_import_compatible_but_retired(self):
        self.assertIn("RETIREMENT_CODE", self.source)
        self.assertIn("FBR_V2_LEGACY_MIGRATION_RETIRED", self.source)
        self.assertIn("RETIREMENT_MESSAGE", self.source)
        self.assertIn("def preview_v2_migration(", self.source)
        self.assertIn("def apply_v2_migration(", self.source)

        preview_block = self.source.split(
            "def preview_v2_migration(", 1
        )[1].split("def apply_v2_migration(", 1)[0]
        apply_block = self.source.split("def apply_v2_migration(", 1)[1]

        self.assertIn("_retired()", preview_block)
        self.assertIn("_retired()", apply_block)

    def test_retired_helper_has_no_legacy_data_authority(self):
        for forbidden in (
            "Ledgix FBR Settings",
            "Ledgix Item Tax Profile",
            "LEGACY_SETTINGS",
            "LEGACY_ITEM_PROFILE",
            "get_decrypted_password(",
            "frappe.get_single(",
            "frappe.get_all(",
            "frappe.db.",
            ".insert(",
            ".save(",
            "APPLY FBR V2 LOCAL MIGRATION",
            "savepoint",
            "rollback",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_retired_helper_cannot_copy_credentials_or_business_mapping(self):
        for forbidden in (
            "_copy_password_if_present",
            "_apply_profile",
            "_create_item_mapping",
            "MIGRATED_ITEM_FIELDS",
            "IGNORED_MONETARY_FIELDS",
            "sandbox_token",
            "production_token",
            "seller_ntn_cnic",
            "scenario_id",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_retired_helper_contains_no_fbr_transport(self):
        for forbidden in (
            "requests.",
            "httpx.",
            "urllib.request",
            "fbr_transport",
            "fbr_v2_transport",
        ):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
