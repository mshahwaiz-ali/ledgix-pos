from pathlib import Path
import ast
import json
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


class TestOldFBRSettingsSourceDeregistration(unittest.TestCase):
    def test_v2_center_no_longer_reports_old_settings_existence(self):
        text = (APP_ROOT / "api/fbr_v2_center.py").read_text(encoding="utf-8")
        self.assertNotIn("old_fbr_settings_exists", text)
        self.assertNotIn(
            'frappe.db.exists("DocType", "Ledgix FBR Settings")',
            text,
        )

    def test_product_shell_uses_v2_profile_navigation_label(self):
        text = (APP_ROOT / "api/product_shell.py").read_text(encoding="utf-8")
        self.assertNotIn('"FBR Settings":', text)
        self.assertNotIn('"FBR Settings",', text)
        self.assertIn('"FBR Integration Profiles":', text)
        self.assertIn('"FBR Integration Profiles",', text)

        workspace = json.loads(
            (
                APP_ROOT
                / "ledgix"
                / "workspace"
                / "ledgix"
                / "ledgix.json"
            ).read_text(encoding="utf-8")
        )
        matches = [
            row
            for row in workspace.get("links") or []
            if row.get("label") == "FBR Integration Profiles"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].get("link_to"),
            "Ledgix FBR Integration Profile",
        )
        self.assertEqual(matches[0].get("link_type"), "DocType")

    def test_permission_source_no_longer_registers_old_settings(self):
        text = (APP_ROOT / "setup/permissions.py").read_text(encoding="utf-8")
        self.assertNotIn('"Ledgix FBR Settings":', text)

    def test_repo_validator_no_longer_requires_old_api_import(self):
        text = (
            REPO_ROOT / "scripts" / "validate_repo.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"ledgix_saas.api.fbr_settings",', text)

    def test_no_live_non_migration_python_depends_on_old_settings_literal(self):
        offenders = []

        allowed_comment_only = {
            "api/fbr_client.py",
            "api/fbr_preflight.py",
            "services/sales.py",
            "ledgix/doctype/v2_test_utils.py",
        }

        for path in APP_ROOT.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue

            rel = str(path.relative_to(APP_ROOT)).replace("\\", "/")
            text = path.read_text(encoding="utf-8")
            ast.parse(text)

            if "Ledgix FBR Settings" not in text:
                continue
            if rel == "api/fbr_settings.py":
                continue
            if rel.startswith("ledgix/doctype/ledgix_fbr_settings/"):
                continue
            if rel.startswith("migration/"):
                continue
            if rel.startswith("setup/test_"):
                continue
            if rel == "patches/v1_0/cleanup_retired_fbr_settings_metadata.py":
                # Intentional, guarded retirement cleanup source. It must name
                # the legacy DocType in order to remove only that metadata.
                continue
            if rel in allowed_comment_only:
                continue

            offenders.append(rel)

        self.assertEqual(offenders, [])

    def test_old_settings_package_registration_is_removed(self):
        pyproject = (APP_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        migration = (
            APP_ROOT / "migration/fbr_redesign_v2_migration.py"
        ).read_text(encoding="utf-8")
        package = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_fbr_settings"
            / "ledgix_fbr_settings.py"
        )

        self.assertNotIn(
            '"ledgix.doctype.ledgix_fbr_settings",',
            pyproject,
        )
        self.assertIn("FBR_V2_LEGACY_MIGRATION_RETIRED", migration)
        self.assertIn("def preview_v2_migration(", migration)
        self.assertIn("def apply_v2_migration(", migration)
        self.assertNotIn(
            'LEGACY_SETTINGS = "Ledgix FBR Settings"',
            migration,
        )
        self.assertNotIn("get_decrypted_password(", migration)

        # Source tombstone remains only until the controlled DB metadata cleanup
        # phase; it is no longer an explicitly packaged application component.
        self.assertTrue(package.exists())


if __name__ == "__main__":
    unittest.main()
