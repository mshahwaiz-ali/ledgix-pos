# Ledgix FBR Sandbox -> Production Activation

This runbook is the compliance/release workstream after R5 client onboarding readiness.

**Sandbox before Production.** Ledgix FBR remains an audit, payload, transport and safety layer over ERPNext-native `Sales Invoice` / `POS Invoice`. The Business Profile enabling FBR is never permission to send Production traffic.

## Safety boundary

The readiness gate is intentionally read-only with respect to FBR transport and Production activation.

It makes **no Production network call**, makes no Sandbox network call, never reads token values into evidence, and never arms `production_post_armed`.

Actual Sandbox traffic is exercised only from the existing ERPNext-native FBR flow after the client has supplied valid seller identity and Sandbox credentials.

The local/integration operator helpers added for certification are also fail-closed:

- they refuse any site other than `.local` / `.localhost`;
- the Sandbox token is prompted silently, never accepted as a CLI argument;
- plaintext staging exists only under the site's private `ledgix-fbr-activation` directory with owner-only permissions and is deleted after Frappe encrypts the Password value;
- Sandbox configuration forces `Manual` submit trigger and keeps Production unarmed;
- Production credentials are not changed by the Sandbox configuration helper;
- real network traffic requires the exact confirmation `SEND TO FBR SANDBOX`;
- the exercise helper calls only the existing ERPNext-native FBR validation/submission services while the current mode is exactly `Sandbox`;
- persisted successful submission logs are reused so a rerun does not intentionally retransmit already-proven Sandbox operations.

## Stage 1 — Sandbox configuration readiness

Before exercising FBR Sandbox, require:

- R5 client readiness green;
- FBR enabled by the selected Business Profile;
- seller NTN/CNIC;
- seller business name;
- seller province;
- seller address;
- Python requests transport available;
- `Ledgix FBR Settings` enabled in `Sandbox` mode;
- valid Sandbox token configured securely;
- Production posting still unarmed;
- no ERPNext-native invoice in `Reconciliation Required` state.

The readiness evaluator records only token **presence**, never token values.

### Secure local/integration configuration

After receiving the real client Sandbox identity/token, run:

```bash
bash scripts/configure_fbr_sandbox_local.sh ledgix-erpnext.local
```

The helper interactively asks for:

- Seller NTN/CNIC;
- Seller business name;
- Seller province;
- Seller address;
- optional software registration number;
- Sandbox token through a hidden prompt.

The token must not be pasted into a shell command, source file, Git commit, ticket, or readiness evidence.

Expected final marker:

```text
fbr_sandbox_configuration_complete=true
```

This command makes **no FBR network request**.

## Stage 2 — Sandbox proof

A token being configured is not proof that FBR works.

Persisted `Ledgix FBR Submission Log` evidence must show a real successful Sandbox network call for both validation and POST.

Required by profile:

- ERPNext `Sales Invoice`: successful Sandbox validate + Sandbox POST;
- ERPNext `POS Invoice`: successful Sandbox validate + Sandbox POST when POS is enabled;
- Credit Note/return: successful Sandbox validate + Sandbox POST when the client uses returns or when `--require-return-proof` is selected.

The activation evaluator reads the persisted `response_json` metadata (`fbr_mode`, `fbr_operation`, `network_call`, `success`) and the submission status. It does not reconstruct proof from UI state.

### Find representative native invoices without network traffic

After Sandbox configuration is green, list recent candidates:

```bash
bash scripts/run_fbr_sandbox_exercise_local.sh \
  ledgix-erpnext.local \
  --list-candidates
```

Expected marker:

```text
fbr_sandbox_candidate_listing_complete=true
```

Choose explicit submitted ERPNext-native references whose `payload_ready` result is true. Do not use a consolidated POS Sales Invoice as a second FBR source.

### Exercise real Sandbox validate + POST

For the current `Small Retail` profile, both Sales Invoice and POS Invoice proof are required. After selecting representative references, run:

```bash
bash scripts/run_fbr_sandbox_exercise_local.sh \
  ledgix-erpnext.local \
  --sales-invoice <SALES-INVOICE-NAME> \
  --pos-invoice <POS-INVOICE-NAME> \
  --confirm "SEND TO FBR SANDBOX"
```

If a Credit Note/return must also be certified, add:

```text
--return-doctype "Sales Invoice" --return-name <RETURN-NAME>
```

or use `POS Invoice` when the native return source is a POS Invoice.

The exercise helper validates then posts each explicit reference to **Sandbox only**. It commits the resulting FBR submission/status audit evidence and then reruns the read-only activation evaluator.

Expected markers:

```text
fbr_sandbox_exercise_complete=true
fbr_sandbox_proven=true
```

If the FBR response rejects a document, stop and correct the real payload/configuration issue. Do not manufacture a successful log and do not change Production settings to bypass Sandbox validation.

## Stage 3 — Production-switch readiness

Production switching remains blocked until all required Sandbox proof is present and:

- Production token is configured securely;
- `production_post_armed` is still false;
- current mode is still pre-Production;
- strict client release/provisioning evidence is green;
- verified backup metadata exists;
- a fresh verified backup exists within the configured activation window (default 24 hours);
- exact approved 40-character release SHA is recorded;
- no native invoice remains `Reconciliation Required`.

If a Production POST ever has an ambiguous network outcome, Ledgix intentionally requires reconciliation with FBR/PRAL before retransmission. Automatic retry/recovery remains disabled.

## Local/integration readiness command

Run:

```bash
bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local
```

This can safely be run before client credentials exist. It reports the real missing configuration/proof without sending anything to FBR.

Expected evaluator marker:

```text
fbr_readiness_evaluation_complete=true
```

It also prints:

```text
fbr_sandbox_ready=true|false
fbr_sandbox_proven=true|false
fbr_production_switch_ready=true|false
```

Fail-closed options:

```bash
bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local \
  --require-sandbox-ready

bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local \
  --require-sandbox-proof \
  --require-return-proof

bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local \
  --require-production-ready \
  --max-backup-age-hours 24
```

The local/integration gate exact-syncs only `.local` / `.localhost` sites. Production uses the already approved deployed release and calls the same readiness service without development code sync.

## Evidence

Readiness snapshots are owner-only under:

```text
private/ledgix-fbr-activation/fbr-activation-readiness-<UTC timestamp>.json
private/ledgix-fbr-activation/latest-readiness.json
```

Evidence includes:

- site and release SHA;
- selected Business Profile;
- seller identity completeness (field names missing, not secret values where unnecessary);
- Sandbox/Production token configured booleans only;
- Sandbox validate/POST proof counts and log names;
- reconciliation-required references;
- verified backup age/metadata file;
- Sandbox-ready / Sandbox-proven / Production-switch-ready booleans.

Evidence never contains Sandbox token values or Production token values.

## Production activation boundary

The readiness and local Sandbox helpers do not perform the Production switch.

Only after `fbr_production_switch_ready=true` should a separate explicit operator/compliance action:

- record the approving owner/operator;
- capture the fresh verified backup and exact release SHA;
- configure the Production credential through the authorized production settings path;
- switch to Production intentionally;
- arm Production posting intentionally;
- start with manual/observed submission rather than silently enabling broad automatic traffic;
- observe the **first live submission** and record its official FBR response/reference;
- know the immediate disable/pause path before the switch.

Automatic retry remains off until a reconciliation-safe design can prove that an ambiguous Production POST was not received by FBR.

## Authority

ERPNext remains authoritative for Sales Invoice, POS Invoice, Credit Note/return, accounting, payment and stock state. Ledgix owns the FBR adapter, immutable legal snapshots, submission logs, reconciliation safeguards, official reference/QR metadata and activation evidence.
