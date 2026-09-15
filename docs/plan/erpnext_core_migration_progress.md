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
- Local runtime directories, sites, databases, secrets and Python environments are excluded from Git through `.gitignore`.
- Exact tested framework baseline is tracked in `config/framework.lock` instead of vendoring Frappe/ERPNext source code.

### Pending before production cutover

- Back up any meaningful Ledgix staging/production site/database before converting it.
- Inventory installed apps and framework versions on staging/production before deployment cutover.

---

## Phase 1 — ERPNext Dependency Plumbing — COMPLETE

### Implemented in code

- `apps/ledgix_saas/hooks.py`
  - declares `required_apps = ["erpnext"]`.
  - Frappe v15 `install_app` recursively installs required apps before the dependent app.

- `apps/ledgix_saas/pyproject.toml`
  - Ledgix support policy is explicitly Frappe v15 + ERPNext v15:
    - `frappe = ">=15.0.0,<16.0.0"`
    - `erpnext = ">=15.0.0,<16.0.0"`

- `install.sh`
  - adds `ERPNEXT_BRANCH` and `ERPNEXT_REPO` configuration.
  - fetches ERPNext `version-15` when absent.
  - validates ERPNext importability and `sites/apps.txt` registration.
  - validates Frappe/ERPNext branch alignment.
  - prints bench application versions.

- `deploy/ensure_erpnext.sh`
  - prepares ERPNext on local/production benches.
  - enforces Frappe/ERPNext branch policy.
  - optionally installs ERPNext on an existing site before Ledgix migration.

- `deploy/production_setup.sh`
  - prepares ERPNext before production app build/site install/full setup.

- `deploy/deploy_update_safe.sh`
  - installs ERPNext on an existing production site before Ledgix migrate when needed.

- `scripts/validate_erpnext_dependency.sh`
  - validates the ERPNext dependency contract statically.

- `scripts/ci_local.sh`
  - runs repository validation, ERPNext dependency validation and committed-secret checks.

- `scripts/check_secrets.sh`
  - ignores interactive hidden-password prompt text so prompt labels are not misidentified as hard-coded password assignments.

- `site_setup.sh`
  - fresh-site flow proved compatible with recursive ERPNext dependency installation.
  - repaired local secrets-index parsing for quoted `SITE_NAME` values.

- `.gitignore`
  - excludes generated Frappe/ERPNext bench, sites, logs, backups, databases, secrets, environments and local tooling state.

- `config/framework.lock`
  - records the exact framework baseline proven during this phase.

### Real bench evidence

`deploy/ensure_erpnext.sh` successfully fetched and prepared ERPNext `version-15` on the local Ledgix bench.

Proven framework baseline:

- ERPNext `15.121.3`, commit `26f06878346fb6861229ccb1fe3a53dc1bf5bad3`;
- Frappe `15.113.4`, commit `588e443808206a7bfe87429c5a55e16016ec7840`.

ERPNext assets built successfully during dependency preparation. The post-install Supervisor restart warning on the local development bench did not affect installation or runtime readiness.

### Fresh integration-site evidence

Fresh site: `ledgix-erpnext.local`

The site was created from scratch after old local site/data cleanup. Ledgix installation recursively installed ERPNext first, then Ledgix. The site completed migration and `after_migrate` hooks successfully.

Final installed applications were explicitly verified:

- `frappe` `15.113.4` on `version-15`;
- `erpnext` `15.121.3` on `version-15`;
- `ledgix_saas` `0.0.1` from `erpnext-core-migration`.

Final Phase 1 smoke evidence:

- `bench --site ledgix-erpnext.local list-apps` passed;
- `bench --site ledgix-erpnext.local migrate` passed;
- ERPNext assets had already built successfully during dependency preparation;
- Ledgix assets built successfully in the final smoke run;
- `sites/ledgix-erpnext.local/site_config.json` exists;
- `frappe.get_installed_apps()` returned exactly `frappe`, `erpnext`, `ledgix_saas`;
- local Git working tree was clean after runtime ignore rules were applied.

### Phase 1 exit decision

**PASS.** The Frappe v15 + ERPNext v15 + Ledgix installation model is proven on a real fresh local site. No production cutover has occurred.

---

## Phase 2 — ERPNext Native Capability / Gap Matrix — STARTED

### Objective

Prove, using the fresh integration site, which Ledgix business concepts can move directly to ERPNext native models and where Ledgix extensions are still required before any authority cutover.

### First probe scope

- Item / Item Group / UOM / barcode / serial / batch configuration;
- Customer / Supplier / Address / Contact;
- Price List / Item Price / Pricing Rule;
- Sales Invoice / POS Invoice / returns;
- Mode of Payment / Payment Entry / receivables;
- Purchase Order / Purchase Receipt / Purchase Invoice;
- Warehouse / Stock Entry / Stock Ledger;
- Batch / Serial No / Serial and Batch Bundle;
- POS Opening Entry / POS Closing Entry;
- fields needed for Ledgix FBR relinking and future transaction snapshots.

### First read-only probe evidence

The first schema probe ran successfully on `ledgix-erpnext.local` after a green local CI run and confirmed ERPNext is installed and active alongside Ledgix.

All targeted native DocTypes were present:

- masters: `Item`, `Item Group`, `UOM`, `Customer`, `Supplier`, `Address`, `Contact`;
- pricing: `Price List`, `Item Price`, `Pricing Rule`;
- sales: `Sales Invoice`, `POS Invoice`;
- payments: `Mode of Payment`, `Payment Entry`;
- buying: `Purchase Order`, `Purchase Receipt`, `Purchase Invoice`;
- stock: `Warehouse`, `Stock Entry`, `Stock Ledger Entry`, `Batch`, `Serial No`, `Serial and Batch Bundle`;
- POS workflow: `POS Profile`, `POS Opening Entry`, `POS Closing Entry`.

For the requested key-field probe, every tested field was present except `POS Invoice.update_stock` on the proven ERPNext `15.121.3` runtime schema. This is not yet classified as a Ledgix gap: the POS Invoice stock lifecycle must be validated behaviorally against this exact ERPNext baseline rather than inferred from a single field name.

The initial probe incorrectly reported every DocType as non-submittable because it read `meta.issubmittable` instead of Frappe v15's `meta.is_submittable`. The probe implementation has been corrected; a second read-only run is required to capture authoritative submit/cancel capability flags.

The probe also surfaced existing framework/ERPNext fields that look custom by naming/metadata, including Address/Contact extensions and Payment Entry `custom_remarks`. These are not assumed to be Ledgix-owned; ownership will be distinguished from standard ERPNext installation behavior before adding any new customization.

### Current Phase 2 conclusion

Schema coverage is already broad enough that the migration should proceed as **ERPNext-native first**, not as a second custom business engine. Remaining work is behavioral parity: create/submit/return/payment/stock/POS flows, tax/accounting parity, FBR datasource adaptation, and UX decisions.

### Safety rule

Phase 2 starts read-only. Existing Ledgix business DocTypes and services remain authoritative until each replacement path has explicit parity evidence.

---

## Safety Status

No sales, stock, payment, tax, FBR, POS, purchase, receivable, or master-data authority has been cut over yet. Existing Ledgix business DocTypes and services remain untouched while ERPNext capabilities are proven module-by-module.
