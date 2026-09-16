# Ledgix Release Hardening — Execution Progress

**Track:** Client Acceptance + Production Provisioning + Release Hardening  
**Migration:** ERPNext Core Migration Phases 0–13 COMPLETE  
**Source of truth:** `main`

## Current status

| Workstream | Status | Evidence / implementation |
|---|---|---|
| R0 — Release baseline / deployment audit | COMPLETE | immutable release contract, explicit production inputs, hardened smoke/deploy contracts |
| R2 — Production install / update | COMPLETE | safe single-site updater, verified backup before mutation, fail-closed maintenance, release evidence |
| R3 — Backup / restore / rollback | COMPLETE | checksum-valid full backup, staged recovery outside site, destructive same-site wipe/recreate/restore, DB identity preservation, Phase 12 digest verification |
| R1 — Fresh-client provisioning | IMPLEMENTED — STATIC GATE PENDING | immutable fresh provisioner, isolated DB, ERPNext-before-Ledgix install, external generated credentials, preflight/smoke/evidence |
| R4 — Multi-site SaaS | IMPLEMENTED — STATIC GATE PENDING | single-site updater refuses shared bench; shared updater requires exact full tenant cohort with per-site backup/maintenance/migrate/smoke/evidence |
| R5 — Client onboarding/readiness | NEXT AFTER R1+R4 GATE | not started in this batch |
| FBR Sandbox -> Production activation | PLANNED | follows R5 |
| Printing/devices/UAT | PLANNED | follows FBR activation |
| Final production release gate | PLANNED | final workstream |

## R3 exercised recovery evidence

The local canonical site `ledgix-erpnext.local` completed the required destructive recovery sequence:

- source Frappe/ERPNext/Ledgix reads passed;
- Phase 12 frozen snapshot matched before reset;
- database/public/private/site-config backup completed;
- checksum verification passed;
- recovery set was staged outside the active site directory;
- the local site was wiped and freshly recreated with Frappe -> ERPNext -> Ledgix;
- the staged database/public/private files were restored;
- fresh local DB identity remained isolated;
- local password convention was reapplied;
- client dependency preflight passed;
- ERPNext-native offline smoke passed with zero failures/warnings;
- Phase 12 frozen snapshot and representative reads matched after restore.

The run then attempted an online smoke even though `--url` had not been supplied. Root cause was shell-variable leakage: sourcing the local credentials file populated `SITE_URL`. The required R3 recovery proof had already passed before that optional step. The runtime gate now uses a dedicated `ONLINE_URL` variable, so online smoke is strictly opt-in and cannot be enabled by sourced site credentials.

R3 is therefore closed; another destructive recovery cycle is not required solely to reproduce a final marker after that optional-smoke bug.

## R1 implementation

Canonical production fresh-site path:

```text
deploy/production_setup.sh --action site
        -> deploy/provision_client_site_safe.sh
```

Contract:

- explicit new site;
- immutable approved release;
- clean repository;
- supported pinned bench;
- dedicated database/user;
- strong generated production credentials outside Git;
- ERPNext installed before Ledgix;
- migrate/build/scheduler/cache refresh;
- dependency preflight;
- offline smoke;
- provisioning evidence;
- no client business masters created by the provisioner;
- no Business Profile automatically applied;
- no FBR Production activation.

## R4 implementation

A bench containing more than one site is refused by the single-site updater. There is no shared-bench bypass environment variable.

Canonical shared release path:

```text
deploy/deploy_update_shared_safe.sh
```

The operator must explicitly list every Ledgix tenant on the bench as `SITE=URL`. The approved list must exactly equal the discovered Ledgix tenant cohort.

The updater then performs:

```text
preflight every tenant
    -> verified backup every tenant
    -> maintenance every tenant
    -> checkout/sync/build shared release once
    -> migrate + preflight + offline smoke every tenant
    -> restart shared services once
    -> reopen full cohort
    -> online smoke every tenant
    -> per-site evidence with shared cohort digest
```

If one online smoke fails, the whole approved cohort is returned to maintenance.

Clients that require different Ledgix application revisions must use separate benches/hosts, not client forks.

## Next gate

Run:

```bash
bash scripts/run_r1_r4_static_gate.sh
```

Expected marker:

```text
r1_r4_static_complete=true
```

After that gate is green, continue to R5 client onboarding/readiness.
