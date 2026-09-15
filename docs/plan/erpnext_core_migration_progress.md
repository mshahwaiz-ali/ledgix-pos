# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `erpnext-core-migration`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This log records implementation evidence against `erpnext_core_migration_plan.md`. A task is not considered fully complete until its code path has been exercised on a real bench/site where applicable.

---

## Phase 0 — Baseline / Safety

### Completed

- Repository architecture audit completed.
- ERPNext-core master plan locked.
- Pre-functional-change commit recorded: `148b35e63371cb0bd5bd5408df69f5262e64680e`.
- Rollback tag `pre-erpnext-core-2026-09-16` created and pushed to origin.
- Superseded `docs/plan/new_plan.md` removed from both `main` and the migration branch.
- Full local CI passed on the migration branch after the secret-scan false-positive fix:
  - 20 shell files;
  - 192 Python files;
  - 54 JSON files;
  - 1 TOML file;
  - Ledgix package validation;
  - ERPNext v15 dependency-contract validation;
  - committed-secret scan.

### Pending evidence

- Back up any meaningful Ledgix site/database before converting an existing site.
- Inventory installed apps on staging/production before deployment cutover.

---

## Phase 1 — ERPNext Dependency Plumbing

### Implemented in code

- `apps/ledgix_saas/hooks.py`
  - declares `required_apps = ["erpnext"]`.
  - Frappe v15 `install_app` recursively installs required apps before the dependent app.

- `apps/ledgix_saas/pyproject.toml`
  - Ledgix support policy is now explicitly Frappe v15 + ERPNext v15:
    - `frappe = ">=15.0.0,<16.0.0"`
    - `erpnext = ">=15.0.0,<16.0.0"`

- `install.sh`
  - adds `ERPNEXT_BRANCH` and `ERPNEXT_REPO` configuration.
  - fetches ERPNext `version-15` when absent.
  - validates ERPNext importability and `sites/apps.txt` registration.
  - validates Frappe/ERPNext branch alignment.
  - prints bench application versions.

- `deploy/ensure_erpnext.sh`
  - new production/local dependency helper.
  - prepares ERPNext on the bench.
  - enforces Frappe/ERPNext branch policy.
  - optionally installs ERPNext on an existing site before Ledgix migration.

- `deploy/production_setup.sh`
  - prepares ERPNext before production app build/site install/full setup.

- `deploy/deploy_update_safe.sh`
  - during an existing production-site update, ERPNext is installed on the site before Ledgix migrate.

- `scripts/validate_erpnext_dependency.sh`
  - new static dependency-contract validation.

- `scripts/ci_local.sh`
  - now runs the ERPNext dependency-contract validation in addition to repository validation and secret checks.

- `scripts/check_secrets.sh`
  - ignores interactive hidden-password prompt text so prompt labels are not misidentified as hard-coded password assignments.

### Real bench evidence

On the local Ledgix bench, `deploy/ensure_erpnext.sh` successfully fetched and prepared ERPNext on `version-15`.

Observed versions during the first dependency-preparation run:

- ERPNext `15.121.3`, branch `version-15`, commit `26f0687`;
- Frappe `15.113.4`, branch `version-15`, commit `588e443`.

ERPNext assets built successfully and the helper completed with `ERPNext dependency is ready`.

The `bench get-app` post-build restart attempted a Supervisor group named `frappe:` and reported that the group did not exist. This is expected on a development bench that is not managed by that production Supervisor group and did not prevent ERPNext preparation.

### Fresh integration-site evidence

A new integration site, `ledgix-erpnext.local`, was created successfully through the Ledgix site setup flow after the old local site/data cleanup step.

The site completed migration and `after_migrate` hooks successfully. The site summary confirmed the following installed applications:

- `frappe` `15.113.4` on `version-15`;
- `erpnext` `15.121.3` on `version-15`;
- `ledgix_saas` `0.0.1` from `erpnext-core-migration`.

The Linux `/etc/hosts` entry for `ledgix-erpnext.local` was added by the site setup flow. This proves the Frappe -> ERPNext -> Ledgix dependency/install path works on a real fresh local site.

### Site-install ordering

Frappe v15's `frappe.installer.install_app` checks `required_apps` and recursively calls `install_app` for each prerequisite before installing the dependent app. Therefore, once ERPNext exists in the bench `apps.txt`, the existing Ledgix site-creation path can install `ledgix_saas` and Frappe will install ERPNext first. We intentionally avoid adding a second competing dependency-order implementation to `site_setup.sh`.

### Still pending for Phase 1 exit gate

- Run a final explicit `bench --site ledgix-erpnext.local migrate` confirmation.
- Run a full `bench build` after the fresh-site install.
- Run smoke checks against the new site.
- Confirm fresh-site setup is reproducible before any production deployment cutover.

---

## Safety Status

No sales, stock, payment, tax, FBR, POS, purchase, receivable, or master-data authority has been cut over yet. Existing Ledgix business DocTypes and services remain untouched in this phase.
