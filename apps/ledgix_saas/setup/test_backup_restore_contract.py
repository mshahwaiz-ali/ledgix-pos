from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
DEPLOY = REPO_ROOT / "deploy"
SCRIPTS = REPO_ROOT / "scripts"


class TestBackupRestoreContract(unittest.TestCase):
    def test_backup_is_complete_checksummed_and_site_explicit(self):
        source = (DEPLOY / "backup_safe.sh").read_text(encoding="utf-8")
        for token in (
            "--site",
            "--backup-path-db",
            "--backup-path-files",
            "--backup-path-private-files",
            "--backup-path-conf",
            "sha256sum -c",
            "verified_site_config=1",
            "verified_checksums=1",
            "frappe_version",
            "erpnext_version",
            "ledgix_version",
            "rollback_owner",
            "--copy-to",
        ):
            self.assertIn(token, source)
        self.assertNotIn('SITE="${PRODUCTION_SITE:-ledgix.local}"', source)

    def test_backup_verifier_is_read_only_and_checksum_driven(self):
        path = DEPLOY / "verify_backup_set.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "--metadata",
            "metadata must not be group/world accessible",
            "verified_database",
            "verified_public_files",
            "verified_private_files",
            "verified_site_config",
            "verified_checksums",
            "sha256sum -c",
            "backup_set_verified=true",
        ):
            self.assertIn(token, source)
        for forbidden in (" bench restore ", " migrate", "set-maintenance-mode"):
            self.assertNotIn(forbidden, source)

    def test_production_restore_drill_stays_non_production_fail_closed(self):
        path = DEPLOY / "restore_drill.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "recovery target must be different from the source site",
            ".ledgix-non-production-recovery-target",
            "RESTORE $SOURCE_SITE TO $TARGET_SITE",
            "verify_backup_set.sh",
            "RECOVERY TARGET SAFETY BACKUP",
            "MERGE SOURCE ENCRYPTION KEY SAFELY",
            'target["encryption_key"] = key',
            "TARGET_DB_IDENTITY_BEFORE",
            'restore "$database_file"',
            '--with-public-files "$public_files_file"',
            '--with-private-files "$private_files_file"',
            "target database identity changed",
            "run_ledgix_client_preflight.sh",
            "smoke_test.sh",
            "ledgix_saas.setup.recovery.verify_recovery_state",
            "restore_drill_complete=true",
        ):
            self.assertIn(token, source)
        self.assertNotIn('cp "$site_config_file" "$TARGET_CONFIG"', source)

    def test_recovery_verifier_is_read_only_and_checks_phase12(self):
        path = APP_ROOT / "setup" / "recovery.py"
        profile_schema_path = (
            APP_ROOT
            / "ledgix"
            / "doctype"
            / "ledgix_business_profile"
            / "ledgix_business_profile.json"
        )
        self.assertTrue(path.exists())
        self.assertTrue(profile_schema_path.exists())

        source = path.read_text(encoding="utf-8")
        profile_schema = json.loads(profile_schema_path.read_text(encoding="utf-8"))
        self.assertEqual(profile_schema.get("name"), "Ledgix Business Profile")
        self.assertEqual(profile_schema.get("issingle"), 1)

        for token in (
            "verify_frozen_snapshot",
            "is_frozen",
            "Company",
            "Item",
            "Customer",
            "Sales Invoice",
            "Ledgix Business Profile",
            "frappe.get_single",
            "business_profile_read_available",
            "recovery_state_verified",
        ):
            self.assertIn(token, source)

        self.assertNotIn('"Business Profile"', source)
        self.assertNotIn("frappe.db.count(LEDGIX_BUSINESS_PROFILE_DOCTYPE)", source)
        self.assertNotIn("freeze_legacy_history", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_site_setup_is_standard_single_site_ledgix_stack(self):
        source = (REPO_ROOT / "site_setup.sh").read_text(encoding="utf-8")
        for token in (
            "ledgix-erpnext.local",
            "Frappe -> ERPNext -> ledgix_saas",
            "install_standard_stack",
            "ensure_erpnext.sh",
            "install-app ledgix_saas",
            "--reset",
            'RESET $SITE',
            "single-site local standard enforced",
            "multiple active local sites found",
            "bench Ledgix app now mirrors repository source exactly",
            "LEDGIX_LOCAL_ADMIN_PASSWORD:-admin",
            "LEDGIX_LOCAL_USER_PASSWORD:-admin@123",
            "LEDGIX_LOCAL_DB_PASSWORD:-admin@123",
            "set-admin-password",
            "set-password",
            "DEFAULT_USER_PASSWORD",
            "local login password convention applied",
        ):
            self.assertIn(token, source)
        for forbidden in (
            "Select apps for this site",
            "Choose app numbers",
            "select_apps",
            "Create another site?",
        ):
            self.assertNotIn(forbidden, source)

    def test_local_db_admin_is_generated_stored_outside_git_and_localhost_only(self):
        path = DEPLOY / "local_db_admin.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            ".secrets/local-db-admin.env",
            "openssl rand",
            "@'localhost'",
            "WITH GRANT OPTION",
            "chmod 600",
            "LOCAL_DB_ADMIN_USER",
            "LOCAL_DB_ADMIN_PASSWORD",
        ):
            self.assertIn(token, source)
        self.assertNotIn("@'%'", source)

    def test_interrupted_local_r3_recovery_is_resumable(self):
        path = DEPLOY / "recover_local_r3.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "local recovery helper refuses non-local site",
            "recovery-staging",
            "sha256sum -c",
            "local_db_admin.sh",
            "--db-root-username",
            "--db-root-password",
            "--with-public-files",
            "--with-private-files",
            "set-admin-password",
            "set-password",
            "verify_recovery_state",
            "local_r3_recovery_complete=true",
        ):
            self.assertIn(token, source)

    def test_runtime_gate_is_single_site_destructive_restore_proof(self):
        path = SCRIPTS / "run_backup_restore_runtime_gate.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "RESET AND RESTORE $SITE",
            "local-only",
            "PRE-RESET PHASE 12 / READ PROOF",
            "VERIFIED SOURCE RECOVERY POINT",
            "STAGE RECOVERY SET OUTSIDE SITE",
            "DESTRUCTIVE SINGLE-SITE RESET",
            'site_setup.sh"',
            '--confirm "RESET $SITE"',
            "source encryption key merged without copying old DB credentials",
            "local_db_admin.sh",
            "--db-root-username \"$LOCAL_DB_ADMIN_USER\"",
            "--db-root-password \"$LOCAL_DB_ADMIN_PASSWORD\"",
            "--admin-password \"$ADMIN_PASSWORD\"",
            "LOCAL LOGIN PASSWORD CONVENTION",
            "set-admin-password",
            "set-password",
            "single active local site enforced",
            "ledgix_saas.setup.recovery.verify_recovery_state",
            "backup_restore_runtime_complete=true",
        ):
            self.assertIn(token, source)
        self.assertNotIn("ledgix-recovery.local", source)
        self.assertNotIn("SOURCE_SITE TARGET_SITE", source)

    def test_local_weak_credentials_do_not_leak_into_production_setup(self):
        production_source = (DEPLOY / "production_setup.sh").read_text(encoding="utf-8")
        updater_source = (DEPLOY / "deploy_update_safe.sh").read_text(encoding="utf-8")
        for source in (production_source, updater_source):
            self.assertNotIn("LEDGIX_LOCAL_ADMIN_PASSWORD", source)
            self.assertNotIn("LEDGIX_LOCAL_USER_PASSWORD", source)
            self.assertNotIn("LEDGIX_LOCAL_DB_PASSWORD", source)
            self.assertNotIn("admin@123", source)

    def test_r3_static_gate_is_consolidated(self):
        static_path = SCRIPTS / "run_backup_restore_static_gate.sh"
        self.assertTrue(static_path.exists())
        source = static_path.read_text(encoding="utf-8")
        self.assertIn("ci_local.sh", source)
        self.assertIn("test_backup_restore_contract", source)
        self.assertIn("backup_restore_static_complete=true", source)

    def test_backup_restore_runbook_exists(self):
        path = REPO_ROOT / "docs" / "production" / "backup_restore_rollback.md"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8").lower()
        for token in (
            "single canonical local site",
            "in-place local recovery drill",
            "non-production",
            "checksum",
            "site_config",
            "encryption_key",
            "phase 12",
            "rollback",
            "off-host",
            "matching release",
            "frappe -> erpnext -> ledgix",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
