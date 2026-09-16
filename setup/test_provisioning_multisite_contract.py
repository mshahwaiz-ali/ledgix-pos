from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
DEPLOY = REPO_ROOT / "deploy"
DOCS = REPO_ROOT / "docs" / "production"


class TestProvisioningAndMultisiteContract(unittest.TestCase):
    def test_fresh_client_provisioner_is_release_pinned_and_isolated(self):
        path = DEPLOY / "provision_client_site_safe.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "--site",
            "--release",
            "release must be a full 40-character commit SHA or immutable tag",
            "refusing to provision existing site",
            "passwordless sudo is required",
            "MariaDB passwordless sudo/socket administration is required",
            "LEDGIX_SITE_SECRETS_DIR",
            "$HOME/.config/ledgix/sites",
            "chmod 600",
            "business_masters_created_by_ledgix_provisioner=0",
            "business_profile_applied=0",
            "fbr_production_activated=0",
            "run_ledgix_client_preflight.sh",
            "smoke_test.sh",
            "fresh_client_provisioning_complete=true",
        ):
            self.assertIn(token, source)

        erpnext_install = source.index('install-app erpnext')
        ledgix_install = source.index('install-app "$APP"')
        self.assertLess(erpnext_install, ledgix_install)
        self.assertNotIn("admin@123", source)
        self.assertNotIn("LEDGIX_LOCAL_ADMIN_PASSWORD", source)
        self.assertNotIn("LEDGIX_LOCAL_DB_PASSWORD", source)

    def test_production_setup_routes_site_creation_to_safe_provisioner(self):
        source = (DEPLOY / "production_setup.sh").read_text(encoding="utf-8")
        for token in (
            "provision_client_site_safe.sh",
            "require_provision_target",
            "DEPLOY_RELEASE is required for site/full provisioning",
            "run_safe_provision_client",
            "run_provision_online_smoke",
            "PRODUCTION_URL not supplied; post-service online smoke skipped",
        ):
            self.assertIn(token, source)
        self.assertNotIn('FRAPPE_ADMIN_PASSWORD:-admin', source)
        self.assertNotIn("admin@123", source)
        self.assertNotIn('args+=(--url "$PRODUCTION_URL")', source)

        full_block = source[source.index('if [[ "$ACTION" == "full" ]]'):]
        self.assertLess(full_block.index("run_safe_provision_client"), full_block.index("run_services"))
        self.assertLess(full_block.index("run_services"), full_block.index("run_provision_online_smoke"))

    def test_single_site_updater_cannot_bypass_shared_bench_guard(self):
        source = (DEPLOY / "deploy_update_safe.sh").read_text(encoding="utf-8")
        self.assertIn("single-site updater refuses shared benches", source)
        self.assertIn("deploy/deploy_update_shared_safe.sh", source)
        self.assertNotIn("LEDGIX_ALLOW_SHARED_BENCH_UPDATE", source)

    def test_shared_bench_release_requires_complete_explicit_cohort(self):
        path = DEPLOY / "deploy_update_shared_safe.sh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        for token in (
            "--release REF",
            "--site SITE=URL",
            "at least two explicitly approved sites",
            "approved cohort must exactly match every $APP tenant on this bench",
            "VERIFIED BACKUP FOR EVERY TENANT",
            "MAINTENANCE MODE FOR FULL COHORT",
            "all approved tenants are in maintenance before shared code movement",
            "EXACT SHARED APP SYNC + BUILD ONCE",
            "MIGRATE + VERIFY EVERY TENANT",
            "ONLINE SMOKE EVERY TENANT",
            "putting the full cohort back into maintenance",
            "shared_bench_cohort_sha256",
            "shared_bench_release_complete=true",
        ):
            self.assertIn(token, source)

        self.assertLess(
            source.index("VERIFIED BACKUP FOR EVERY TENANT"),
            source.index("MAINTENANCE MODE FOR FULL COHORT"),
        )
        self.assertLess(
            source.index("MAINTENANCE MODE FOR FULL COHORT"),
            source.index("CHECKOUT APPROVED RELEASE"),
        )
        self.assertLess(
            source.index("EXACT SHARED APP SYNC + BUILD ONCE"),
            source.index("MIGRATE + VERIFY EVERY TENANT"),
        )

    def test_r1_r4_runbooks_document_single_codebase_and_tenant_isolation(self):
        fresh = DOCS / "fresh_client_provisioning.md"
        multisite = DOCS / "multi_site_saas.md"
        self.assertTrue(fresh.exists())
        self.assertTrue(multisite.exists())

        fresh_text = fresh.read_text(encoding="utf-8").lower()
        for token in (
            "erpnext before ledgix",
            "immutable release",
            "outside the repository",
            "business profile",
            "fbr production",
            "configuration-only",
        ):
            self.assertIn(token, fresh_text)

        multisite_text = multisite.read_text(encoding="utf-8").lower()
        for token in (
            "one site per client",
            "one database per site",
            "same ledgix application revision",
            "full cohort",
            "per-site backup",
            "per-site fbr",
            "separate bench",
            "no client fork",
            "tenant add",
            "tenant remove",
            "tenant restore",
        ):
            self.assertIn(token, multisite_text)


if __name__ == "__main__":
    unittest.main()
