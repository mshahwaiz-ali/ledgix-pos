from __future__ import annotations

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

    def test_restore_drill_is_non_production_fail_closed(self):
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
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "verify_frozen_snapshot",
            "is_frozen",
            "Company",
            "Item",
            "Customer",
            "Sales Invoice",
            "Business Profile",
            "recovery_state_verified",
        ):
            self.assertIn(token, source)
        self.assertNotIn("freeze_legacy_history", source)
        self.assertNotIn("frappe.db.commit", source)

    def test_r3_gates_are_consolidated(self):
        static_path = SCRIPTS / "run_backup_restore_static_gate.sh"
        runtime_path = SCRIPTS / "run_backup_restore_runtime_gate.sh"
        self.assertTrue(static_path.exists())
        self.assertTrue(runtime_path.exists())
        static_source = static_path.read_text(encoding="utf-8")
        runtime_source = runtime_path.read_text(encoding="utf-8")
        self.assertIn("test_backup_restore_contract", static_source)
        self.assertIn("backup_restore_static_complete=true", static_source)
        for token in (
            "run_backup_restore_static_gate.sh",
            "backup_safe.sh",
            "restore_drill.sh",
            "backup_restore_runtime_complete=true",
            ".ledgix-non-production-recovery-target",
        ):
            self.assertIn(token, runtime_source)

    def test_backup_restore_runbook_exists(self):
        path = REPO_ROOT / "docs" / "production" / "backup_restore_rollback.md"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8").lower()
        for token in (
            "non-production",
            "checksum",
            "site_config",
            "encryption_key",
            "phase 12",
            "rollback",
            "off-host",
            "matching release",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
