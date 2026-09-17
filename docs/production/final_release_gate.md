# Ledgix Final Production Release Gate

The final gate is an **acceptance audit**, not a deployment mechanism. Production code must already have been installed/updated by the approved immutable-release deployment tooling.

## Required command

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site client.example.com \
  --url https://client.example.com \
  --release <full-40-character-SHA-or-immutable-tag>
```

If the client is intended to activate FBR Production, add:

```text
--require-fbr-production
```

## Fail-closed contract

The gate requires:

- clean repository;
- immutable release SHA or tag; moving branch names are rejected;
- deployed repository HEAD equal to the approved release;
- explicit site and HTTPS URL;
- client dependency preflight green;
- offline + online smoke green;
- R5 client readiness still green;
- native A4 and profile-required thermal print formats installed;
- Phase 12 frozen historical snapshot matching through the true read-only verifier;
- profile-specific manual UAT evidence complete;
- strict production release/provisioning evidence present;
- verified backup evidence present;
- FBR Production prerequisites only when `--require-fbr-production` is requested.

The gate itself makes **no Production network call to FBR**, does not validate/post an FBR invoice, and never arms Production posting.

## External FBR state

FBR code/setup can be complete while external certification remains pending because the client has not yet supplied seller identity or tokens. That state does not invalidate the Ledgix application setup.

When FBR Production is required for go-live, the final gate will remain red until the separate Sandbox -> Production workflow has real persisted evidence, a Production token, fresh verified backup, exact release identity, and no unresolved reconciliation state.

## Manual UAT

Manual printer/scanner/device acceptance is intentionally not inferred from source code. Evidence is stored owner-only under `private/ledgix-acceptance/` and must be recorded from actual operator testing.

## Rollback / backup

A verified backup and rollback identity must exist before final production approval. The final gate consumes that evidence; it does not create or overwrite a backup implicitly.

## Phase 12 safety

The final gate uses `ledgix_saas.setup.phase12_read_only.verify_frozen_snapshot_read_only`. Unlike the Phase 12 administrative verifier, this acceptance verifier does not update `last_verified_at`, reconciliation JSON, or any retirement-state field.

## Result

Only a fully green production run emits:

```text
ledgix_production_release_gate_complete=true
```

If external FBR certification or physical/manual UAT is not yet available, use the local acceptance readiness gate to prove that application setup is ready without claiming production acceptance:

```bash
bash scripts/run_release_acceptance_readiness_gate.sh ledgix-erpnext.local
```
