# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `erpnext-core-migration`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`

This log records implementation evidence against `erpnext_core_migration_plan.md`. A task is not considered fully complete until its code path has been exercised on a real bench/site where applicable.

---

## Phase 0 — Baseline / Safety

### Completed

- Repository architecture audit completed.
- ERPNext-core master plan locked.
- Pre-functional-change commit recorded: `148b35e63371cb0bd5bd5408df69f5262e64680e`.
- Superseded `docs/plan/new_plan.md` removed from both `main` and the migration branch.

### Pending evidence

- Run `./scripts/ci_local.sh` on the known-good baseline/current branch.
- Create a local named pre-ERPNext git tag pointing to `148b35e63371cb0bd5bd5408df69f5262e64680e`.
- Back up any meaningful Ledgix site/database before converting an existing site.
- Inventory installed apps on staging/production before deployment cutover.

---

## Phase 1 — ERPNext Dependency Plumbing

### Implemented in code

- `apps/ledgix_saas/hooks.py`
  - declares `required_apps = ["erpnext"]`.
  - Frappe will install required apps before installing Ledgix on a site.

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
  - new production dependency helper.
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

### Site-install ordering note

The existing `site_setup.sh` already installs selected apps through Frappe's `install-app` path. With Ledgix now declaring `required_apps = ["erpnext"]`, Frappe recursively installs ERPNext before Ledgix as long as ERPNext is available on the bench. The updated local installer prepares ERPNext before `site_setup.sh` is entered. A fresh-site test is still required before this is marked proven.

### Still pending for Phase 1 exit gate

- Run the repository validation suite on the migration branch.
- Prepare a fresh local bench/site with Frappe v15 + ERPNext v15 + Ledgix.
- Confirm `bench --site <integration-site> list-apps` shows `frappe`, `erpnext`, and `ledgix_saas`.
- Run `bench --site <integration-site> migrate`.
- Run `bench build` and smoke checks.
- Confirm fresh-site creation is reproducible before touching an existing working Ledgix site's business data.

---

## Safety Status

No sales, stock, payment, tax, FBR, POS, purchase, receivable, or master-data authority has been cut over yet. Existing Ledgix business DocTypes and services remain untouched in this phase.
