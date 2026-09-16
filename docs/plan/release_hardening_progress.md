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
| R1 — Fresh-client provisioning | COMPLETE | R1+R4 static gate green; immutable fresh provisioner, isolated DB, ERPNext-before-Ledgix install, external generated credentials, preflight/smoke/evidence |
| R4 — Multi-site SaaS | COMPLETE | R1+R4 static gate green; single-site updater refuses shared bench; shared updater requires exact full tenant cohort with per-site backup/maintenance/migrate/smoke/evidence |
| R5 — Client onboarding/readiness | IMPLEMENTED — RUNTIME AUDIT PENDING | profile-aware ERPNext readiness, accounting/payment prerequisites, named Ledgix users/roles, FBR pre-activation safety, private evidence, setup-page visibility |
| FBR Sandbox -> Production activation | NEXT AFTER R5 | follows R5 runtime readiness audit/closure |
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

R3 is closed; another destructive recovery cycle is not required solely to reproduce a final marker after that optional-smoke bug.

## R1 exercised static evidence

The combined R1 + R4 static gate passed on `f54bb336ba17e8e046bc4b46e9a6d22f1466a903`.

Evidence:

- repository/local CI green;
- 47 shell files passed syntax validation;
- 276 Python files passed syntax validation;
- 59 JSON files and 1 TOML file passed validation;
- ERPNext v15 dependency contract green;
- secret scan green;
- R3 regression contract passed 12/12;
- R1 + R4 contract tests passed 5/5;
- provisioning/release helpers exposed safe non-mutating help paths;
- final marker `r1_r4_static_complete=true`.

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

## R4 exercised static evidence

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

## R5 implementation

R5 reuses the Phase 13 client setup evaluator instead of creating a second configuration engine.

Canonical service:

```text
ledgix_saas.api.client_readiness
```

It evaluates:

- Business Profile setup completion and current setup readiness;
- ERPNext Company Chart of Accounts and profile-relevant account defaults;
- Company Mode of Payment account mapping for selling/payment profiles;
- installed Ledgix Admin/Manager/Cashier role definitions;
- enabled named users carrying Ledgix operational roles;
- POS cashier coverage as a handover warning;
- FBR Settings presence for FBR-enabled profiles;
- a fail-closed pre-activation interlock: Production posting must remain unarmed during R5;
- provisioning/release and verified-backup evidence presence;
- site identity (Company/country/currency/timezone) without exposing secrets.

Readiness evidence is written owner-only under:

```text
private/ledgix-readiness/
```

`/app/ledgix-setup` now also displays an Operational onboarding section. R5 does not create ERPNext business masters, users, passwords or FBR tokens and does not activate FBR Production.

## Next gate

Run the non-destructive local/integration readiness audit:

```bash
bash scripts/run_r5_client_readiness_gate.sh ledgix-erpnext.local
```

Expected evaluator marker:

```text
r5_readiness_evaluation_complete=true
```

The same run also reports either `r5_client_ready=true` or `r5_client_ready=false`. If blockers remain, resolve those actual client prerequisites and rerun with `--require-ready` only when the site is intended to represent an accepted client configuration.
