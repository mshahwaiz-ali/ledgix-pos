# Ledgix Release Hardening — Execution Progress

**Track:** Client Acceptance + Production Provisioning + Release Hardening  
**Migration:** ERPNext Core Migration Phases 0–13 COMPLETE  
**Source of truth:** `main`

## Current status

| Workstream | Status | Evidence / implementation |
|---|---|---|
| R0 — Release baseline / deployment audit | COMPLETE | immutable release contract, explicit production inputs, hardened smoke/deploy contracts |
| R2 — Production install / update | COMPLETE | safe single-site updater, verified backup before mutation, fail-closed maintenance, release evidence |
| R3 — Backup / restore / rollback | COMPLETE | checksum-valid full backup, destructive same-site wipe/recreate/restore, DB identity preservation, Phase 12 digest verification |
| R1 — Fresh-client provisioning | COMPLETE | immutable isolated provisioner, ERPNext-before-Ledgix install, external generated credentials, preflight/smoke/evidence |
| R4 — Multi-site SaaS | COMPLETE | shared-bench updater requires exact full tenant cohort with per-site backup/maintenance/migrate/smoke/evidence |
| R5 — Client onboarding/readiness | COMPLETE | runtime gate green with guarded existing-profile apply; no blocking onboarding checks remain |
| FBR Sandbox -> Production activation | ACTIVE — READINESS GATE IMPLEMENTED | read-only activation evaluator, Sandbox validate/POST proof, reconciliation safety, strict release/backup gate; awaiting real client seller identity/tokens and Sandbox evidence |
| Printing/devices/UAT | PLANNED | follows FBR Sandbox/activation proof |
| Final production release gate | PLANNED | final workstream |

## R3 exercised recovery evidence

The canonical local site `ledgix-erpnext.local` completed a checksum-valid full backup, staged recovery outside the active site, destructive wipe/recreate, restore of database/public/private files, fresh DB-identity preservation, dependency/offline smoke checks, and Phase 12 frozen-snapshot verification. R3 is closed.

## R1 + R4 exercised evidence

The combined R1 + R4 gate passed on `f54bb336ba17e8e046bc4b46e9a6d22f1466a903` with:

- repository/local CI green;
- R3 regression contract green;
- R1/R4 contract tests green;
- safe non-mutating helper interfaces;
- final marker `r1_r4_static_complete=true`.

Production fresh-site authority is `deploy/provision_client_site_safe.sh`. Shared-bench release authority is `deploy/deploy_update_shared_safe.sh`. There is no per-client application fork.

## R5 exercised runtime evidence

The R5 runtime gate was completed on `ledgix-erpnext.local` at HEAD `e50bf5e96bc5c7e5d7ce07552138b530d263847d`.

Before the guarded apply, every current ERPNext/accounting/payment/user/FBR-safety prerequisite was green and the sole blocker was `client_setup_applied`.

The explicit `--apply-setup` path then reused the already-resolved existing configuration:

- Business Profile: `Small Retail`;
- Company: `Ledgix ERPNext Integration`;
- Selling Price List: `Standard Selling`;
- Warehouse: `Stores - LEI`;
- POS Profile: `Ledgix ERPNext POS Spike`.

The guarded adapter reused the existing Phase 13 configuration-only service, created no business masters, did not activate FBR Production, and re-evaluated readiness immediately.

Final R5 evidence:

```text
r5_static_complete=true
r5_client_ready=true
r5_readiness_evaluation_complete=true
```

Additional exercised checks included:

- Chart of Accounts and Company receivable/income/payable/expense defaults green;
- 3 Mode of Payment account mappings;
- Ledgix Admin/Manager/Cashier role definitions present;
- one enabled named Ledgix operational user with required role coverage;
- FBR Settings installed;
- FBR mode `Disabled`;
- Production posting unarmed;
- private non-secret readiness evidence written.

Seller identity plus production release/backup evidence remain inputs for the dedicated FBR activation workstream rather than R5 blockers.

## FBR Sandbox -> Production activation implementation

Canonical read-only service:

```text
ledgix_saas.api.fbr_activation
```

Canonical local/integration audit:

```bash
bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local
```

The gate makes no FBR network call and never arms Production.

### Sandbox-ready contract

Requires:

- R5 client readiness green;
- FBR enabled by the selected Business Profile;
- complete seller identity;
- requests transport available;
- FBR Settings enabled in `Sandbox` mode;
- Sandbox token configured;
- Production posting unarmed;
- no ERPNext-native invoice in `Reconciliation Required` state.

### Sandbox-proven contract

Persisted `Ledgix FBR Submission Log` evidence must show successful real Sandbox network calls for:

- Sales Invoice validate + POST;
- POS Invoice validate + POST when POS is enabled;
- Credit Note/return validate + POST when explicitly required/applicable.

Proof is derived from persisted `fbr_mode`, `fbr_operation`, `network_call` and `success` metadata in the stored FBR response plus final submission status. Token values are never read into readiness evidence.

### Production-switch-ready contract

Requires:

- required Sandbox proof complete;
- Production token configured;
- Production still unarmed and not already switched;
- strict client release/provisioning evidence green;
- verified backup metadata present;
- fresh verified backup within the configured window (default 24 hours);
- exact approved 40-character release SHA recorded;
- no unresolved `Reconciliation Required` state.

Readiness evidence is retained owner-only under:

```text
private/ledgix-fbr-activation/
```

The readiness implementation deliberately does **not** include a Production-arm action. Real client seller identity and Sandbox credentials must be supplied and the required Sandbox flows must pass first. Production switching/arming remains a later explicit operator/compliance action with observed first-live submission.

## Next gate

Run the non-network activation audit:

```bash
bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local
```

Expected health marker:

```text
fbr_readiness_evaluation_complete=true
```

The same run reports the current real state:

```text
fbr_sandbox_ready=true|false
fbr_sandbox_proven=true|false
fbr_production_switch_ready=true|false
```

On the current integration site, missing real seller identity/Sandbox credentials are expected to keep Sandbox readiness false until client data is supplied. Do not fabricate these values.
