from __future__ import annotations

from pathlib import Path
import ast
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    for candidate in APP_ROOT.parents:
        if (
            (candidate / "scripts").is_dir()
            and (candidate / "apps" / "ledgix_saas").is_dir()
        ):
            return candidate
    raise RuntimeError(f"Could not locate repository root from {APP_ROOT}")


REPO_ROOT = _repo_root()
PATCH_PATH = (
    APP_ROOT / "patches/v1_0/cleanup_retired_fbr_settings_metadata.py"
)
PATCH = PATCH_PATH.read_text(encoding="utf-8")
PATCHES_TXT = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")


class TestRetiredFBRSettingsMetadataCleanupContract(unittest.TestCase):
    def test_cleanup_module_is_valid_but_not_registered_yet(self):
        ast.parse(PATCH)
        self.assertNotIn(
            "ledgix_saas.patches.v1_0.cleanup_retired_fbr_settings_metadata",
            PATCHES_TXT,
        )
        self.assertIn('"registered_in_patches_txt": False', PATCH)

    def test_preview_is_read_only_and_names_all_cleanup_targets(self):
        self.assertIn("def preview_cleanup()", PATCH)
        preview = PATCH.split("def preview_cleanup()", 1)[1].split(
            "def execute()", 1
        )[0]
        for required in (
            '"Workspace Link"',
            '"DocPerm"',
            '"Custom DocPerm"',
            '"Singles"',
            '"read_only": True',
            '"database_write": False',
            '"fbr_network_call": False',
        ):
            self.assertIn(required, preview)

        for forbidden in (
            "frappe.db.delete(",
            "frappe.delete_doc(",
            "frappe.db.sql(",
            ".save(",
            ".insert(",
        ):
            self.assertNotIn(forbidden, preview)

    def test_execute_requires_exact_backup_authorization(self):
        self.assertIn(
            'AUTHORIZATION_KEY = "ledgix_legacy_fbr_settings_cleanup_authorization"',
            PATCH,
        )
        self.assertIn(
            'AUTHORIZATION_VALUE = "VERIFIED_BACKUP_AND_APPROVED_FBR_SETTINGS_CLEANUP"',
            PATCH,
        )
        self.assertIn("_assert_authorized()", PATCH)
        self.assertIn("_assert_safe_v2_state()", PATCH)

    def test_execute_fails_closed_if_v2_is_live_or_production_armed(self):
        safety = PATCH.split("def _assert_safe_v2_state()", 1)[1].split(
            "def _assert_authorized()", 1
        )[0]
        self.assertIn('row.get("enabled")', safety)
        self.assertIn('row.get("mode")', safety)
        self.assertIn('row.get("production_post_armed")', safety)
        self.assertIn("frappe.throw(", safety)

    def test_execute_targets_only_old_settings_metadata(self):
        execute = PATCH.split("def execute()", 1)[1]
        for required in (
            'frappe.db.delete("Workspace Link", {"link_to": LEGACY_DOCTYPE})',
            'frappe.db.delete("Custom DocPerm", {"parent": LEGACY_DOCTYPE})',
            'frappe.db.delete("DocPerm", {"parent": LEGACY_DOCTYPE})',
            'frappe.db.delete("Singles", {"doctype": LEGACY_DOCTYPE})',
            'frappe.delete_doc(',
            '"DocType"',
            "LEGACY_DOCTYPE",
            "force=True",
            "ignore_permissions=True",
            "for_reload=True",
        ):
            self.assertIn(required, execute)

        self.assertNotIn("delete_controllers(", execute)

        for forbidden in (
            "requests.",
            "fbr_transport",
            "fbr_v2_transport",
            "Production Post",
            "Sales Invoice",
            "POS Invoice",
            "GL Entry",
        ):
            self.assertNotIn(forbidden, execute)


if __name__ == "__main__":
    unittest.main()
