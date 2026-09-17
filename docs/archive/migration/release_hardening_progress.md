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
| R4 — Multi-site SaaS | COMPLETE | shared-bench updater requires exact full tenant cohort; fresh-tenant provisioning cannot silently mutate an existing shared-bench Ledgix release |
| R5 — Client onboarding/readiness | COMPLETE | runtime gate green with guarded existing-profile apply; no blocking onboarding checks remain |
| FBR Sandbox -> Production activation | CODE/SETUP COMPLETE — EXTERNAL CERTIFICATION PENDING | read-only gate green; secure Sandbox configuration/exercise helpers ready; remaining inputs are real seller identity/tokens, real Sandbox proof, and production evidence |
| Printing/devices/UAT | TOOLING + MACHINE SETUP COMPLETE — PHYSICAL UAT PENDING | ERPNext-native A4/thermal print surfaces, device/UAT contract and acceptance evaluator implemented; machine-verifiable setup green |
| Final production release gate | IMPLEMENTED — REAL PRODUCTION EVIDENCE PENDING | immutable final gate implemented; local release setup readiness green; production verdict intentionally waits for manual UAT, release/backup evidence, online smoke and FBR certification when applicable |

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

The later shared-bench safety audit also closed the remaining mutation gap: adding a tenant to an existing shared bench cannot sync the bench to a different Ledgix release. The requested release must already match the deployed shared release or provisioning fails closed and directs the operator to the shared cohort updater. The `production_setup --action full` path no longer performs a generic pre-provision Ledgix code mutation.

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

### Exercised readiness evidence

The activation audit passed its static/runtime infrastructure gate on `ledgix-erpnext.local` at HEAD `4057d5bab2cc545c1295177b3b4815f831fa106c`.

Exercised evidence:

- 51 shell files passed syntax validation;
- 281 Python files, 59 JSON files and 1 TOML file passed repository validation;
- ERPNext dependency and secret scans green;
- Phase 9 FBR regression contract passed 12/12;
- R5 regression contract passed 8/8;
- FBR activation contract passed 6/6;
- dependency preflight green;
- ERPNext-native offline smoke: 0 failures / 0 warnings;
- requests transport available;
- R5 client readiness green;
- selected Business Profile `Small Retail` enables FBR and therefore requires Sales Invoice + POS Invoice Sandbox proof;
- zero `Reconciliation Required` native invoices;
- Production posting remained unarmed;
- activation audit made zero FBR network calls;
- private non-secret FBR readiness evidence written;
- final marker `fbr_readiness_evaluation_complete=true`.

Expected real-input blockers were reported rather than fabricated:

- seller NTN/CNIC, business name, province and address missing;
- FBR mode still `Disabled`;
- Sandbox token not configured;
- no real Sandbox Sales Invoice validate/POST proof;
- no real Sandbox POS Invoice validate/POST proof;
- Production token not configured;
- strict release/provisioning evidence absent on the local integration site;
- no current verified backup metadata in the active site backup directory.

Therefore the exercised state correctly reported:

```text
fbr_sandbox_ready=false
fbr_sandbox_proven=false
fbr_production_switch_ready=false
```

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

### Secure Sandbox operator tooling

Local/integration-only helpers now exist for the real client credential stage:

```text
scripts/configure_fbr_sandbox_local.sh
scripts/run_fbr_sandbox_exercise_local.sh
ledgix_saas.setup.fbr_sandbox_operator
```

Safety contract:

- seller identity is entered interactively;
- Sandbox token is read through a hidden prompt and is never accepted as a command-line argument;
- plaintext token staging is owner-only under the site's private activation directory and removed after Frappe stores the encrypted Password value;
- helper refuses non-local/non-integration sites;
- Sandbox configuration forces `Manual` trigger and keeps Production unarmed;
- Production credentials are not modified;
- candidate listing makes no network request;
- real Sandbox traffic requires exact `SEND TO FBR SANDBOX` confirmation;
- exercise uses only explicit ERPNext `Sales Invoice` / `POS Invoice` references;
- existing persisted successful Sandbox proof is reused instead of deliberately retransmitting it.

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

## Printing / device / UAT acceptance

The printing/device/profile acceptance tooling and runbook are implemented. The local machine-verifiable release acceptance gate has been exercised successfully on `ledgix-erpnext.local`.

Verified setup-side evidence includes:

```text
release_acceptance_static_complete=true
release_setup_ready=true
release_acceptance_readiness_complete=true
```

The evaluator verifies the native ERPNext print surfaces, Phase 12 frozen snapshot, R5 setup state and profile/device/UAT requirements without fabricating hardware evidence. Physical printer/barcode/payment-terminal observations remain manual acceptance evidence by design.

The expected local state therefore keeps manual acceptance false until a human actually exercises the devices:

```text
manual_uat_ready=false
```

This is not a software/setup defect.

## Final production release gate

The immutable production release gate is implemented and intentionally does not deploy code, arm FBR Production or manufacture evidence. It verifies an already-deployed approved release against strict production prerequisites.

Production readiness requires the applicable combination of:

- exact immutable Ledgix release identity;
- strict release/provisioning evidence;
- fresh verified backup evidence;
- online/offline smoke;
- manual device/UAT evidence;
- no unresolved reconciliation state;
- FBR Sandbox/Production certification only when the client is going live with FBR Production.

The canonical final command remains:

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site <client-site> \
  --url https://<client-domain> \
  --release <immutable-sha-or-tag>
```

Add `--require-fbr-production` only for a client whose go-live scope includes FBR Production.

## Retained Ledgix product Pages

The ERPNext migration does **not** delete the product-specific Ledgix Pages. The retained first-class UX surfaces are:

- `ledgix-pos` — Ledgix POS;
- `business-intelligence-center` — Inventory Intelligence;
- `ledgix-tax-center` — Tax & FBR Center;
- `ledgix-setup` — Setup Wizard.

They are exposed as profile/role-aware shortcuts in the Ledgix workspace. ERPNext remains authoritative underneath them.

The post-migration source alignment now includes:

- Inventory Intelligence item filter -> ERPNext `Item`;
- Inventory navigation -> ERPNext `Item`, Stock Ledger/Stock Balance and `Batch`;
- inventory timeline references -> whitelisted ERPNext-native transaction DocTypes;
- POS customer link -> ERPNext `Customer`;
- POS post-sale printing -> native `Sales Invoice` / `POS Invoice` + Ledgix ERPNext print formats;
- legacy `Ledgix Sale` print URLs removed from the active POS source;
- Tax & FBR Center remains a Ledgix orchestration surface while its active FBR source is ERPNext `Sales Invoice` / `POS Invoice`;
- Setup Wizard remains the guarded configuration-only onboarding surface.

The combined Phase 10 + Phase 11 custom-page/native-authority contract was re-exercised after these changes and passed:

```text
Ran 25 tests
OK
```

This preservation requirement is regression-tested so later release work must modernize these Pages rather than delete them.

## Next FBR operator sequence

Once the real client Sandbox details are available:

```bash
bash scripts/configure_fbr_sandbox_local.sh ledgix-erpnext.local

bash scripts/run_fbr_sandbox_exercise_local.sh \
  ledgix-erpnext.local \
  --list-candidates
```

Then select explicit payload-ready Sales Invoice/POS Invoice references and run the confirmed Sandbox exercise documented in `docs/production/fbr_sandbox_production_activation.md`.

Do not fabricate seller identity, token, scenario, or official FBR evidence.
