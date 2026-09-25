# Ledgix FBR Sandbox -> Production Activation

Use this runbook only after the software handoff gate passes.

## Safety boundary

Readiness performs no FBR request and never arms Production. Real Sandbox traffic requires the guarded helper and exact `SEND TO FBR SANDBOX` confirmation. Tokens must not appear in commands, Git or evidence.

## Stage 1 — Client legal/setup data

Enter/verify ERPNext Company legal name/Tax ID and linked registered Address. Configure Business Nature(s), Sector, provider/onboarding, software/POS registration where applicable and attach the authoritative FBR Digital Invoicing System logo. Keep Known Offline disabled unless its current rule/window is confirmed. Keep Production unarmed.

## Stage 2 — Sandbox configuration

```bash
bash scripts/configure_fbr_sandbox_local.sh ledgix-erpnext.local
```

Seller identity is validated from ERPNext Company + Address. The helper optionally records software registration, prompts for Sandbox token through hidden input, stores it via Frappe Password handling and makes no FBR request.

## Stage 3 — Official reference + mapping review

Use Tax & FBR Center to sync official references and review every active FBR Item Mapping. Do not clear `needs_review` without real evidence.

## Stage 4 — Sandbox proof

```bash
bash scripts/run_fbr_sandbox_exercise_local.sh ledgix-erpnext.local --list-candidates
```

Then exercise explicit payload-ready Sales/POS references with `--confirm "SEND TO FBR SANDBOX"`.

Do not exercise return/note until the current provider/FBR note contract is confirmed. Then retain real validate + POST evidence for the proven native flow.

## Stage 5 — Known Offline when applicable

Configure policy/window only after provider/legal confirmation. Use Tax & FBR Center -> Known Offline operations. Declaration requires `DECLARE KNOWN OFFLINE`; controlled upload requires `UPLOAD OFFLINE INVOICE`. Never use Known Offline after a Production POST attempt.

## Stage 6 — Print/correction certification

Confirm authoritative DI logo, software/POS registration, accepted FBR number/QR, final QR presentation, Offline Pending marker, proven return/note terminology and correction evidence/timing.

## Stage 7 — Readiness

```bash
bash scripts/run_fbr_activation_readiness_gate.sh ledgix-erpnext.local
```

Production readiness additionally requires the authoritative DI logo, Production credential, strict release evidence, fresh verified backup, approved release SHA and zero unresolved reconciliation.

## Stage 8 — Production activation

After formal approval only: final backup, release SHA, Production credential, intentional Production switch, intentional arm, manual/observed first-live submissions and retained go-live evidence.

ERPNext remains the accounting/transaction authority throughout.

## Certification safety statements

Sandbox before Production.

Certification evidence is retained against native ERPNext Sales Invoice and POS Invoice sources.

Older regression terminology may refer to Credit Note; this does not activate or assume an outbound Credit Note protocol. Return/note semantics remain fail-closed until current Sandbox/provider proof.

An ambiguous Production outcome remains Reconciliation Required.

The readiness workflow performs no Production network call.

Production activation requires a fresh verified backup.

The first live submission must be manually observed and its official response retained as go-live evidence.
