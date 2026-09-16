# Ledgix FBR Sandbox -> Production Activation

This runbook is the compliance/release workstream after R5 client onboarding readiness.

**Sandbox before Production.** Ledgix FBR remains an audit, payload, transport and safety layer over ERPNext-native `Sales Invoice` / `POS Invoice`. The Business Profile enabling FBR is never permission to send Production traffic.

## Safety boundary

The readiness gate is intentionally read-only with respect to FBR transport and Production activation.

It makes **no Production network call**, makes no Sandbox network call, never reads token values into evidence, and never arms `production_post_armed`.

Actual Sandbox traffic is exercised only from the existing FBR Center/native invoice flow after the client has supplied valid seller identity and Sandbox credentials.

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

## Stage 2 — Sandbox proof

A token being configured is not proof that FBR works.

Persisted `Ledgix FBR Submission Log` evidence must show a real successful Sandbox network call for both validation and POST.

Required by profile:

- ERPNext `Sales Invoice`: successful Sandbox validate + Sandbox POST;
- ERPNext `POS Invoice`: successful Sandbox validate + Sandbox POST when POS is enabled;
- Credit Note/return: successful Sandbox validate + Sandbox POST when the client uses returns or when `--require-return-proof` is selected.

The activation evaluator reads the persisted `response_json` metadata (`fbr_mode`, `fbr_operation`, `network_call`, `success`) and the submission status. It does not reconstruct proof from UI state.

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

## Actual Sandbox exercise

After the client provides real Sandbox details:

1. configure seller identity and Sandbox token in `Ledgix FBR Settings`;
2. keep Production unarmed;
3. select `Sandbox` and enable FBR;
4. use ERPNext-native source documents only;
5. validate a representative Sales Invoice;
6. POST the representative Sales Invoice to Sandbox;
7. for POS-enabled profiles, validate and POST a representative POS Invoice;
8. exercise a Credit Note/return when applicable;
9. verify `Ledgix FBR Submission Log` contains successful Sandbox evidence;
10. verify official reference / QR persistence and print behavior for the exercised flow;
11. rerun the readiness gate with `--require-sandbox-proof`.

Do not manufacture seller identity, token, scenario or client legal data for the test.

## Production activation boundary

The readiness gate does not perform the switch.

Only after `fbr_production_switch_ready=true` should a separate explicit operator/compliance action:

- record the approving owner/operator;
- capture the fresh verified backup and exact release SHA;
- switch to Production intentionally;
- arm Production posting intentionally;
- start with manual/observed submission rather than silently enabling broad automatic traffic;
- observe the **first live submission** and record its official FBR response/reference;
- know the immediate disable/pause path before the switch.

Automatic retry remains off until a reconciliation-safe design can prove that an ambiguous Production POST was not received by FBR.

## Authority

ERPNext remains authoritative for Sales Invoice, POS Invoice, Credit Note/return, accounting, payment and stock state. Ledgix owns the FBR adapter, immutable legal snapshots, submission logs, reconciliation safeguards, official reference/QR metadata and activation evidence.
