from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
DEPLOY = REPO_ROOT / "deploy"
SCRIPTS = REPO_ROOT / "scripts"


class TestReleaseHardeningContract(unittest.TestCase):
    def test_production_wrapper_has_no_weak_admin_default(self):
        source = (DEPLOY / "production_setup.sh").read_text(encoding="utf-8")
        self.assertNotIn('FRAPPE_ADMIN_PASSWORD="${FRAPPE_ADMIN_PASSWORD:-admin}"', source)
        self.assertIn("require_production_site", source)
        self.assertIn("DEPLOY_RELEASE", source)
        self.assertIn("PRODUCTION_URL", source)
        self.assertIn("$HOME/.config/ledgix/production-sites.md", source)
        self.assertIn("relocate_legacy_secrets", source)

    def test_deploy_update_requires_immutable_release_and_fails_closed(self):
        source = (DEPLOY / "deploy_update_safe.sh").read_text(encoding="utf-8")
        for token in (
            "--release",
            "full 40-character commit SHA or tag",
            "moving branch names are not accepted",
            'checkout --detach "$TARGET_SHA"',
            "backup_safe.sh",
            "release_contract.env",
            "run_ledgix_client_preflight.sh",
            "--offline",
            "--online",
            "maintenance mode remains ON",
            "last-successful.env",
            "LEDGIX_ALLOW_SHARED_BENCH_UPDATE",
        ):
            self.assertIn(token, source)
        self.assertNotIn("pull --ff-only origin", source)
        self.assertNotIn('SITE="${PRODUCTION_SITE:-ledgix.local}"', source)
        self.assertNotIn("ensure_erpnext.sh", source)

    def test_verified_backup_is_site_explicit_and_records_rollback_metadata(self):
        source = (DEPLOY / "backup_safe.sh").read_text(encoding="utf-8")
        self.assertIn("--site", source)
        self.assertIn("backup --with-files", source)
        self.assertIn("verified_database=1", source)
        self.assertIn("verified_public_files=1", source)
        self.assertIn("verified_private_files=1", source)
        self.assertIn("from_release", source)
        self.assertIn("to_release", source)
        self.assertNotIn("ledgix.local", source)

    def test_smoke_test_targets_active_erpnext_ledgix_surfaces(self):
        source = (DEPLOY / "smoke_test.sh").read_text(encoding="utf-8")
        for token in (
            "api/client_setup.py",
            "api/product_shell.py",
            "api/fbr_native.py",
            "services/erpnext_selling.py",
            "services/erpnext_pos.py",
            "ledgix_setup/ledgix_setup.json",
        ):
            self.assertIn(token, source)
        self.assertNotIn("doctype/ledgix_sale/ledgix_sale.json", source)
        self.assertNotIn("doctype/ledgix_sales_return/ledgix_sales_return.json", source)
        self.assertNotIn("ledgix_saas.validation.run_all", source)
        self.assertNotIn("ledgix_saas.api.fbr_health.check", source)

    def test_release_contract_pins_supported_stack(self):
        path = DEPLOY / "release_contract.env"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        self.assertIn("LEDGIX_EXPECTED_FRAPPE_VERSION=15.113.4", source)
        self.assertIn("LEDGIX_EXPECTED_ERPNEXT_VERSION=15.121.3", source)
        self.assertIn("LEDGIX_APP=ledgix_saas", source)
        self.assertIn(
            "LEDGIX_MIGRATION_CLOSURE_GATE_SHA=d813d26d16a11665522da98c7bd542a7cc09c53f",
            source,
        )

    def test_release_hardening_gate_is_consolidated(self):
        path = SCRIPTS / "run_release_hardening_static_gate.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        self.assertIn("ci_local.sh", source)
        self.assertIn("test_release_hardening_contract", source)
        self.assertIn("release_hardening_static_complete=true", source)

    def test_release_runbook_exists(self):
        path = REPO_ROOT / "docs" / "production" / "release_install_update.md"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        self.assertIn("immutable", source.lower())
        self.assertIn("DEPLOY_RELEASE", source)
        self.assertIn("PRODUCTION_SITE", source)
        self.assertIn("PRODUCTION_URL", source)
        self.assertIn("rollback", source.lower())
        self.assertIn("no per-client forks", source.lower())


if __name__ == "__main__":
    unittest.main()
