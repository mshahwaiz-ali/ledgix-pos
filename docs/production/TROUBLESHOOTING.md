# Ledgix Troubleshooting

**Status:** CURRENT

## Local site does not open

```bash
./start.sh --status
./start.sh --smoke --site ledgix-erpnext.local
```

Check:

- the canonical site exists;
- `/etc/hosts` resolves `ledgix-erpnext.local` to `127.0.0.1` where required;
- port `8000` belongs to this bench;
- Frappe, ERPNext and `ledgix_saas` are installed.

For site repair, prefer:

```bash
./site_setup.sh --ensure
```

Do not jump to destructive `--reset` unless local data may intentionally be destroyed.

---

## Required app missing

Check:

```bash
cd frappe-bench
bench --site ledgix-erpnext.local list-apps
bench version --format plain
```

Expected site stack:

```text
frappe
erpnext
ledgix_saas
```

ERPNext is mandatory. Do not fix a production/client site by manually installing only `ledgix_saas` onto a Frappe-only site.

For local repair use the supported installer/site workflow. For production use the dependency preflight and approved provisioning/update tooling.

---

## Python/module import errors

From the repository root:

```bash
bash scripts/ci_local.sh
```

Check that the repository app exists at:

```text
apps/ledgix_saas/
```

and that the bench copy/editable install resolves correctly under:

```text
frappe-bench/apps/ledgix_saas/
```

For local repair, `site_setup.sh --ensure` re-synchronizes the current Ledgix app and migrates/builds the canonical site.

---

## Migration/build problems

Local:

```bash
cd frappe-bench
bench --site ledgix-erpnext.local migrate
bench build --app ledgix_saas
bench --site ledgix-erpnext.local clear-cache
```

Production changes must go through the immutable-release updater rather than ad-hoc manual pulls/builds.

See `docs/production/release_install_update.md`.

---

## Nginx 502 / Supervisor failure

Check:

```bash
sudo supervisorctl status
sudo nginx -t
```

Inspect the relevant bench/service logs and verify the production site/domain mapping.

After an approved build/migrate, restart/reload only through the supported production workflow or deliberate service action.

Do not switch to `bench start` as a production workaround.

---

## Wrong site / 404 behind Nginx

Test the local upstream with the production Host header:

```bash
curl -I -H "Host: client.example.com" http://127.0.0.1
```

Verify:

- DNS points at the intended server;
- Nginx config includes the intended site/domain;
- the Frappe site folder matches the host;
- the site is not unintentionally left in maintenance mode.

---

## ERPNext outstanding/payment looks wrong

Do not correct balances in a parallel Ledgix ledger.

Inspect the authoritative ERPNext documents:

- `Sales Invoice.grand_total`;
- `Sales Invoice.outstanding_amount`;
- submitted `Payment Entry` references/allocated amounts;
- Credit Notes/returns;
- GL/customer ledger where needed.

For Ledgix B2B payments, current writes use native ERPNext `Payment Entry` allocations.

---

## POS return or closing issue

Inspect native ERPNext:

- source `POS Invoice`;
- return `POS Invoice.return_against`;
- return payment rows;
- active `POS Opening Entry`;
- `POS Closing Entry`;
- `POS Invoice.consolidated_invoice`.

Do not create or edit `Ledgix Sales Return`, `Ledgix POS Shift` or `Ledgix POS Hold` to repair current operations.

---

## Stock quantity mismatch

ERPNext Stock Ledger / `Bin` are authoritative.

Inspect the native vouchers affecting the item/warehouse:

- Purchase Receipt / stock-updating Purchase Invoice;
- POS/Sales stock effect;
- Stock Entry;
- Stock Reconciliation;
- returns;
- Batch/Serial records where relevant.

Do not repair current stock by writing `Ledgix Stock Movement` or legacy lot/serial DocTypes.

---

## FBR readiness/submission error

Use the current FBR docs first:

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
```

Check:

- source is a supported submitted ERPNext `Sales Invoice` / `POS Invoice`;
- seller identity is complete;
- buyer/item/FBR classifications are correct;
- immutable FBR snapshot is present;
- token presence matches the selected environment;
- mode/trigger/Production interlock are intentional;
- `Ledgix FBR Submission Log` contains the real attempt state.

### `Reconciliation Required`

Do **not** repeatedly retry.

This state means the Production request outcome is ambiguous and must be reconciled externally with FBR/PRAL before any supported retransmission decision.

Current FBR scheduler retry is intentionally disabled.

---

## FBR Production not ready

This can be the correct state even when application code/tests are green.

Production FBR remains blocked until real client Sandbox proof, Production credentials, fresh verified backup/release evidence and reconciliation requirements are complete.

Do not fabricate the missing evidence or manually edit readiness flags.

---

## Backup verification failure

Do not deploy/update based on an unverified recovery point.

Use:

```bash
bash deploy/verify_backup_set.sh \
  --metadata /absolute/path/to/ledgix-backup-...env \
  --site client.example.com
```

If checksums/artifacts fail, create a new safe backup before proceeding.

See `docs/production/backup_restore_rollback.md`.

---

## Shared bench update refused

This is expected when `deploy_update_safe.sh` detects multiple sites.

Use the shared-bench cohort workflow documented in `docs/production/multi_site_saas.md`. Do not bypass the safety check to update only one tenant against shared code.

---

## Need deeper evidence

Use the specific runbook for the affected area rather than modifying ERPNext core or reviving frozen legacy Ledgix business DocTypes.
