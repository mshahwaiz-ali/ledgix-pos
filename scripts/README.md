# Ledgix scripts

Current operational script layout:

- `core/` — local install, site management, and development runtime entrypoints.
- `validation/` — repository/static validation and secret checks.
- `local/` — local client/demo preflight helpers.
- `release/` — current release, acceptance, backup/restore, and production-release gates.
- `archive/` — retained historical migration/certification helpers. Archived scripts are evidence/reference and are not current operational authority.

The canonical Ledgix-owned application source is edited directly under:

- `frappe-bench/apps/ledgix_saas`
- `frappe-bench/apps/fbr_v1`
- `frappe-bench/apps/fbr_v12`

There is no separate root `apps/` development source and no local source-to-bench synchronization step.
