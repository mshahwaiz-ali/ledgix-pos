# Ledgix POS — Testing and Release Gates

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Purpose:** distinguish code proof, runtime proof, client readiness, manual UAT, FBR certification and Production acceptance

## 1. Purpose

Ledgix uses multiple kinds of tests and gates.

They do not prove the same thing.

The central rule is:

> **Do not convert one kind of evidence into a stronger claim than it supports.**

Examples:

- unit tests are not client UAT;
- local runtime proof is not FBR Sandbox certification;
- a green readiness report is not Production activation;
- deployment success is not final production acceptance;
- a mocked FBR HTTP response is not legal/provider evidence.

This document defines the current evidence hierarchy.

---

## 2. Evidence hierarchy

From narrowest to strongest:

    source/static validation
      -> focused unit/contract tests
      -> local runtime/integration gates
      -> destructive recovery proof
      -> client configuration readiness
      -> release setup readiness
      -> manual human/device UAT
      -> real FBR Sandbox certification
      -> strict Production release readiness
      -> explicit Production activation

A later stage can depend on earlier stages.

It does not make earlier evidence retroactively stronger.

---

## 3. Repository CI

Basic repository check:

    bash scripts/ci_local.sh

Current ci_local.sh runs:

- ERPNext dependency contract;
- secret scan.

It is intentionally small.

Do not describe ci_local as the full Ledgix test suite.

---

## 4. Dependency contract

scripts/validate_erpnext_dependency.sh protects the current stack assumptions.

It verifies items such as:

- ERPNext is a required dependency;
- supported major/version expectations;
- update helpers do not silently install/modify ERPNext on existing-site Ledgix update paths;
- current app dependency structure remains ERPNext-native.

A dependency gate protects architecture.

It does not verify business workflows end-to-end.

---

## 5. Secret scan

scripts/check_secrets.sh protects the repository from accidental secret inclusion.

It should be run before release/push.

A green secret scan means no known matching secret pattern was found in the checked scope.

It does not prove an operational log or external ticket contains no secret.

---

## 6. Static contract gates

Static gates are used for contracts that can be proven without mutating a live/client site.

Examples include:

- release hardening;
- backup/restore helper behavior;
- client readiness;
- FBR activation;
- historical phase closure contracts.

They commonly run Python unittest modules and shell source checks.

Static gates should remain safe to rerun.

---

## 7. Release hardening static gate

Current command:

    bash scripts/run_release_hardening_static_gate.sh

This includes:

- ci_local;
- release-hardening unittest contract;
- non-mutating helper --help checks.

Its verdict proves contracts such as:

- explicit production-site handling;
- immutable release identity;
- backup/rollback metadata contract;
- fail-closed maintenance behavior;
- ERPNext-native smoke contract.

It does not deploy a site.

---

## 8. Focused unit/contract tests

The repository contains many setup/test_*.py modules.

Use focused modules when changing:

- POS;
- selling/payment;
- buying/inventory;
- permissions;
- FBR transport;
- FBR readiness;
- FBR certification;
- release tooling;
- backup/restore;
- legacy freeze.

Tests should protect a named contract rather than simply increase counts.

---

## 9. Full setup regression

The final forensic audit ran the broad setup regression suite.

Baseline evidence recorded:

- 472 passed;
- 0 failed.

This is a historical baseline for the inspected 2026-09-26 source.

It is not a permanent expected count; future legitimate tests can increase/decrease the count.

The important release condition is that the current intended suite is green.

---

## 10. Focused forensic regression

The final audit's focused blocker regression recorded:

- 19 passed;
- 0 failed.

It targeted the final FBR forensic blocker set, including:

- Sandbox certification proof hardening;
- company/profile proof isolation;
- Production POST crash-window durability.

Again, the number is baseline evidence, not a future hardcoded gate count.

---

## 11. Runtime gates

A runtime gate exercises real Frappe/ERPNext application state.

Runtime gates can verify behavior that static tests cannot, such as:

- DocType/schema presence;
- migrate behavior;
- actual native ERPNext document lifecycle;
- permissions after synchronization;
- read/write transaction interaction;
- backup/restore;
- client readiness against site data.

Runtime gates must clearly state whether they:

- write;
- rollback;
- preserve test transactions;
- call external networks.

---

## 12. Read-only runtime proof

Where possible, final audit preferred read-only/in-memory proof for already-closed architecture.

This avoids mutating state merely for cosmetic evidence.

Examples include:

- FBR readiness;
- activation state;
- client setup/readiness diagnostics;
- frozen historical snapshot verification.

---

## 13. Rollback-confirmed transactional gates

Some behavior requires real database transactions.

A safe local gate can:

1. create/use a controlled test fixture;
2. exercise the transaction;
3. verify result;
4. roll back/clean within the controlled test design;
5. prove no unintended production-like history remains.

Do not run write-heavy historical gates repeatedly on a real client just to reproduce an old phase report.

---

## 14. Real external network gates

FBR network exercises are a special class.

They must be:

- explicit;
- authorized;
- correctly credentialed;
- environment-scoped;
- evidence-preserving.

General local tests must not accidentally call FBR/PRAL.

The final forensic audit made:

    0 real FBR/PRAL network calls

---

## 15. Local Sandbox exercise

The repository includes an explicit local Sandbox exercise workflow.

It is not enabled by ordinary runtime.

A narrow confirmation/environment mechanism exists so real Sandbox traffic cannot happen accidentally.

Real Sandbox exercise can become certification evidence only when the resulting persisted proof matches the certification rules.

---

## 16. Backup/restore static proof

Current static backup/restore gate validates the recovery tooling contract without doing a destructive restore.

Use it before relying on recovery scripts after code changes.

---

## 17. Backup/restore runtime proof

Current local destructive recovery command:

    bash scripts/run_backup_restore_runtime_gate.sh \
      ledgix-erpnext.local \
      --confirm "RESET AND RESTORE ledgix-erpnext.local"

This is local-only.

It proves:

- fresh verified backup;
- recovery set survives site destruction;
- canonical local site recreation;
- DB identity isolation;
- encryption-key recovery;
- database/files restore;
- dependency preflight;
- offline smoke;
- representative reads;
- Phase 12 frozen snapshot survival.

It emits:

    backup_restore_runtime_complete=true

on success.

---

## 18. Client readiness

R5 client readiness evaluates an already provisioned/configured site.

Implementation:

    api/client_readiness.py

It does not:

- create business masters;
- activate FBR Production;
- replace ERPNext authority.

---

## 19. Client readiness gate

Current integration command:

    bash scripts/run_r5_client_readiness_gate.sh <site>

Optional flags include:

- --strict-evidence;
- --apply-setup;
- --require-ready;
- --url.

The gate can persist a private non-secret readiness snapshot.

---

## 20. Strict vs non-strict client evidence

Client readiness supports two evidence modes.

### Non-strict

Missing release/backup operational evidence can remain warnings while configuration readiness is evaluated.

### Strict

Missing:

- provisioning/release identity evidence;
- verified backup metadata

becomes blocking.

Strict mode is intended for Production acceptance.

---

## 21. Setup application guard

The local R5 gate can optionally apply setup only when:

- the only blocker is the unapplied setup marker;
- current resolved ERPNext prerequisites are already green.

It applies the existing resolved Business Profile/configuration.

It does not create business masters.

---

## 22. FBR activation readiness

Implementation:

    api/fbr_activation.py

Current gate:

    bash scripts/run_fbr_activation_readiness_gate.sh <site>

It is read-only regarding FBR transport/activation.

It:

- makes no FBR network call;
- never arms Production;
- can persist non-secret readiness evidence.

---

## 23. FBR readiness levels

The activation gate distinguishes:

### sandbox_ready

Configuration prerequisites exist.

### sandbox_proven

Required real persisted Sandbox Validate/POST evidence exists.

### production_switch_ready

Sandbox proof plus strict Production prerequisites are green.

These states are intentionally separate.

---

## 24. FBR gate requirement flags

The current activation gate can require:

- Sandbox ready;
- Sandbox proof;
- Production ready;
- return/note proof;
- configurable maximum backup age.

Use the smallest requirement matching the workstream.

Do not require Production readiness during an early Sandbox configuration task.

---

## 25. Release acceptance service

Implementation:

    api/release_acceptance.py

This service combines:

- client readiness;
- print-format checks;
- read-only Phase 12 verification;
- manual UAT evidence;
- strict production evidence;
- optional FBR production readiness.

It does not deploy, post to FBR or arm Production.

---

## 26. Manual UAT

Manual UAT is explicit human/device evidence.

It is stored under the site private tree.

The release service does not infer it from:

- source code;
- unit tests;
- browser automation;
- existence of print formats.

Manual evidence is recorded only through an explicit confirmation workflow.

---

## 27. Profile-specific manual UAT

Required UAT keys depend on Business Profile features.

Base UAT can include general operational/browser/print checks.

POS-enabled profiles add POS/device-oriented checks.

Buying-enabled profiles add purchasing/inventory checks.

The implementation is authoritative for the exact current key set.

---

## 28. Printing UAT

Machine-verifiable checks can prove:

- print format exists;
- template contains expected FBR reference/QR surface;
- correct DocType association.

They cannot prove:

- printer hardware works;
- paper size is physically correct;
- QR scans reliably from the actual printer;
- client accepts layout.

Those require real UAT.

---

## 29. Release acceptance readiness gate

Local/integration command:

    bash scripts/run_release_acceptance_readiness_gate.sh ledgix-erpnext.local

It:

- runs static release acceptance contract;
- syncs current repository Ledgix source into local bench;
- migrates/builds;
- runs dependency preflight;
- runs offline smoke;
- generates release acceptance evidence.

It can report release setup ready even when manual/external evidence remains pending.

---

## 30. release_setup_ready vs production_release_ready

These are deliberately different.

### release_setup_ready

Machine-verifiable application/setup checks are green.

### production_release_ready

Also requires:

- manual UAT;
- strict client release/backup evidence;
- FBR Production readiness if explicitly required.

Do not announce Production ready when only release_setup_ready is true.

---

## 31. Final production release gate

Current command:

    bash scripts/run_ledgix_production_release_gate.sh \
      --site client.example.com \
      --url https://client.example.com \
      --release <full-sha-or-tag>

This is an audit-only acceptance gate.

Production code must already be deployed through the supported updater.

---

## 32. Final production gate preconditions

The final gate requires:

- clean repository;
- immutable approved release;
- deployed HEAD exactly equals approved release;
- explicit site;
- HTTPS URL;
- client preflight;
- offline and online smoke;
- strict release acceptance;
- Phase 12 frozen snapshot;
- manual UAT;
- release/backup evidence.

Optional FBR Production requirement can be added.

---

## 33. Final production gate does not mutate deployment

It does not:

- checkout/sync deployment code;
- deploy a new release;
- post to FBR;
- arm Production.

Its job is to decide whether the already-deployed site has sufficient acceptance evidence.

---

## 34. Final production marker

A fully green final gate emits:

    ledgix_production_release_gate_complete=true

Do not manually write this marker as a substitute for running the gate.

---

## 35. FBR Production flag

Use:

    --require-fbr-production

only when FBR Production is actually part of this client's go-live.

If FBR is not yet externally certified, the application can still be technically installed/configured while the Production FBR requirement remains red.

---

## 36. Phase 12 read-only verification

Release/recovery acceptance uses:

    setup/phase12_read_only.py

This verifier compares frozen snapshot with current historical rows without updating the retirement record.

This is intentionally different from the administrative legacy verifier, which may update verification metadata.

Acceptance proof must not mutate the evidence being checked.

---

## 37. Historical migration gates

The repository retains many scripts named:

- run_erpnext_phase*_gate.sh;
- migration probes;
- FBR redesign gates.

These are historical architecture/migration evidence.

They should not all be run on every future release.

Use current release gates for current operation.

Rerun an old phase gate only when:

- changing the subsystem it uniquely protects;
- investigating historical migration compatibility;
- explicitly validating a migrated-site transition.

---

## 38. Test selection by change

### UI/product-shell change

Run:

- focused page/product-shell tests;
- relevant role/permission tests;
- build;
- local smoke;
- profile-specific UAT if release-bound.

### POS change

Run:

- POS contract tests;
- native POS runtime gate where required;
- return/closing regression;
- print checks;
- manual device UAT when hardware-facing.

### Accounting/tax change

Run:

- native tax contract;
- sales/payment/return tests;
- GL/stock runtime proof;
- FBR reconciliation/payload tests if tax evidence feeds FBR.

### FBR change

Run:

- FBR focused contracts;
- readiness;
- certification evidence;
- transport policy;
- ambiguity/crash-window regression;
- zero-network local runtime proof;
- real Sandbox only in explicit authorized certification phase.

### Deployment change

Run:

- release hardening static;
- backup/restore static;
- helper --help/static contracts;
- local recovery runtime if recovery path changed.

---

## 39. Test data discipline

Use:

- synthetic local data;
- purpose-built local fixtures;
- rollback-confirmed transactions.

Do not:

- mutate production accounting to make tests pass;
- create fake FBR evidence;
- use client secrets in unit tests;
- erase submitted history casually.

---

## 40. Evidence storage

Current private evidence locations can include:

- private/ledgix-readiness/;
- private/ledgix-acceptance/;
- private/ledgix-release/;
- private/backups/;
- private/ledgix-recovery/.

These are site-private operational evidence.

Do not commit them to Git.

---

## 41. Test result interpretation

A test can prove only its declared scope.

Examples:

- "payload builder rejects missing identity" does not prove real FBR acceptance;
- "print contains QR element" does not prove physical QR scan quality;
- "backup checksum passes" does not prove restore unless restore is exercised;
- "site responds 200" does not prove accounting correctness;
- "release setup ready" does not prove Production go-live.

---

## 42. Current final forensic baseline

The 2026-09-26 audit recorded:

- software-side inspected blockers closed;
- focused forensic tests: 19 passed, 0 failed;
- setup regression: 472 passed, 0 failed;
- final runtime gates passed;
- real FBR/PRAL calls: 0;
- Production posting: unarmed;
- general V2 cutover: false.

Status at that baseline:

- Software Ready for Client Certification: YES;
- Sandbox Certified: NO;
- Production Ready: NO;
- Production Active: NO.

---

## 43. Known permission regression to add

Documentation consolidation identified a current mismatch:

- FBR Submission Log JSON intends read-only Desk evidence;
- centralized setup/permissions.py still contains broader historical rights;
- fast_permissions can apply that policy during migrate.

A future code-fix should add a migrate-level regression proving effective permissions after permission synchronization.

Until then, a JSON-only permission test is insufficient.

---

## 44. Release checklist

Before approving release:

- [ ] relevant focused tests green;
- [ ] ci_local green;
- [ ] release-hardening static green when deployment/release scope warrants it;
- [ ] app builds;
- [ ] migrate succeeds in appropriate test environment;
- [ ] dependency preflight green;
- [ ] offline smoke green;
- [ ] backup/restore contract unchanged or re-proven;
- [ ] client readiness evaluated;
- [ ] manual UAT complete for release-bound client;
- [ ] final production gate green before final acceptance;
- [ ] FBR requirement matches actual client go-live scope;
- [ ] no test result is mislabeled as external certification.

---

## 45. Summary

> **Ledgix release evidence is layered: static/unit/runtime proof establishes software behavior, client readiness establishes configuration, human UAT establishes real operational acceptance, real FBR Sandbox evidence establishes certification, and only the strict final gate over an already deployed immutable release supports Production acceptance.**
