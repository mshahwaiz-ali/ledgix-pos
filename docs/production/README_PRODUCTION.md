# Ledgix Production Operations Index

**Status:** CURRENT

This directory contains the active production runbooks for Ledgix after the ERPNext-core migration.

## Core rules

- Frappe v15 + ERPNext v15 + `ledgix_saas` is the supported stack.
- ERPNext is the business/accounting/stock authority.
- Production deploys an approved immutable SHA/tag, not a moving `main` branch.
- One client uses one Frappe site/database.
- Shared benches use one Ledgix release across all Ledgix tenants in that bench.
- Production credentials live outside the repository.
- Verified backup/rollback evidence is required before production changes.
- FBR Production activation is a separate external compliance gate.
- Ambiguous FBR Production POSTs fail closed as `Reconciliation Required`; there is no blind retry scheduler.

## Start here

For a new server/client:

1. `DEPLOYMENT.md` — production architecture and entrypoint.
2. `fresh_client_provisioning.md` — safe creation of a new client site.
3. `client_lifecycle.md` — ERPNext prerequisites, Business Profile and handover lifecycle.
4. `client_onboarding_readiness.md` — operational readiness evidence.
5. `PRODUCTION_CHECKLIST.md` — concise go-live checklist.
6. `final_release_gate.md` — final fail-closed release acceptance.

## Release and recovery

- `release_install_update.md` — immutable release/install/update contract.
- `backup_restore_rollback.md` — verified backup, restore drill and rollback.
- `multi_site_saas.md` — shared-bench tenant/release rules.

## Compliance and hardware

- `fbr_sandbox_production_activation.md` — detailed Sandbox proof and Production activation readiness.
- `../fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md` — current FBR architecture.
- `../fbr/FBR_PRODUCTION_CHECKLIST.md` — current FBR go-live checklist.
- `printing_devices_uat.md` — printer/scanner/device manual acceptance.

## Security and support

- `SECURITY.md` — production security and secret-handling rules.
- `TROUBLESHOOTING.md` — current support paths and fail-closed boundaries.

## Common production commands

Fresh site on a prepared bench:

```bash
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<approved-immutable-sha-or-tag>'
bash deploy/production_setup.sh --action site
```

Full production rollout:

```bash
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<approved-immutable-sha-or-tag>'
export PRODUCTION_URL='https://client.example.com'
bash deploy/production_setup.sh --yes --action full
```

Safe verified backup:

```bash
bash deploy/backup_safe.sh --site client.example.com
```

Single-site update:

```bash
bash deploy/deploy_update_safe.sh \
  --site client.example.com \
  --release '<approved-immutable-sha-or-tag>' \
  --url 'https://client.example.com'
```

Final production release gate:

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site client.example.com \
  --url https://client.example.com \
  --release <approved-immutable-release>
```

## Retired guidance

Older production instructions that use:

- `deploy/production.secrets.md` as the normal credential store;
- an unpinned fast-forward `git pull` as the release decision;
- `deploy/deploy_update.sh` instead of the current guarded update path;
- `deploy/backup.sh` instead of the verified backup contract;
- manual Ledgix-only `bench new-site` / `install-app ledgix_saas` flow;

must not be treated as current authority.

Use the active runbooks and current scripts in this directory/repository instead.
