# Ledgix POS — Migration and Legacy Retirement

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**ERPNext-core migration:** COMPLETE  
**Migration phases:** 0–13 CLOSED  
**There is no Phase 14.**

## 1. Purpose

This document explains the completed Ledgix ERPNext-core migration and the current legacy-retirement boundary.

It is not a chronological phase plan.

Its goal is to answer:

- what was migrated;
- what is current authority now;
- which legacy data remains;
- why it remains;
- how frozen legacy history is protected;
- which old tax/FBR masters were physically retired;
- how rollback differs from ordinary operation;
- how future cleanup should be approached.

The central rule is:

> **Historical Ledgix business data may remain physically present for audit/migration evidence, but it is not current business authority.**

---

## 2. Migration closure

The ERPNext-core migration closed on 2026-09-16.

Final migration closure gate SHA:

    d813d26d16a11665522da98c7bd542a7cc09c53f

Final Phase 13 result recorded:

- phase13_complete=true;
- migration_complete=true;
- failed_cases=[];
- passed=true.

The project is no longer executing a migration phase.

---

## 3. Final authority after migration

ERPNext owns current:

- Items;
- Item Groups;
- Customers;
- Suppliers;
- Price Lists / Item Prices;
- Modes of Payment;
- Sales Invoice;
- POS Invoice;
- Payment Entry;
- Purchase Order;
- Purchase Receipt;
- Purchase Invoice;
- Stock Entry;
- Stock Reconciliation;
- Stock Ledger / Bin;
- Batch / Serial;
- accounting;
- monetary tax.

Ledgix owns product UX, compatibility and FBR/compliance extensions.

---

## 4. Migration phase outcomes

### Phase 0

Safety/baseline and rollback checkpoint.

### Phase 1

ERPNext dependency and integration site established.

### Phase 2

ERPNext capability/gap matrix proved standard business engines should move to ERPNext.

### Phase 3

Native masters + Ledgix extension schema.

### Phase 4

Native tax/accounting parity.

### Phase 5

Master-data migration.

### Phase 6

Selling/payments/returns cutover.

### Phase 7

Buying/inventory cutover.

### Phase 8

POS engine cutover.

### Phase 9

FBR source cutover to native invoices.

### Phase 10

BI/report/print cutover.

### Phase 11

Workspace/product simplification.

### Phase 12

Legacy freeze/reconciliation/retirement.

### Phase 13

Business Profiles / one-codebase SaaS productization.

All are complete.

---

## 5. Legacy business history strategy

The migration deliberately did not delete historical business rows.

Reasons include:

- audit history;
- migration provenance;
- rollback safety;
- reconciliation evidence;
- ability to verify historical counts/digests;
- avoidance of premature destructive schema cleanup.

Current operation therefore distinguishes:

    physically present
        !=
    authoritative

---

## 6. Frozen top-level legacy business DocTypes

Current retirement service tracks top-level legacy models including:

- Ledgix Item;
- Ledgix Category;
- Ledgix Customer;
- Ledgix Supplier;
- Ledgix Price List;
- Ledgix Item Price;
- Ledgix Payment Method;
- Ledgix Sale;
- Ledgix Purchase;
- Ledgix Sales Return;
- Ledgix POS Shift;
- Ledgix POS Hold;
- Ledgix Payment;
- Ledgix Stock Movement;
- Ledgix Stock Lot;
- Ledgix Stock Serial.

These must not receive new normal business writes once frozen.

---

## 7. Frozen child history

Retirement snapshot also covers historical child models such as:

- Ledgix Sale Item;
- Ledgix Sale Payment;
- Ledgix Purchase Item;
- Ledgix Sales Return Item;
- Ledgix POS Hold Item;
- Ledgix Payment Allocation;
- Ledgix Stock Lot Allocation.

Child rows remain part of the historical digest.

---

## 8. Freeze state

Current retirement state is stored in:

    Ledgix Legacy Retirement State

Important statuses include:

- Not Frozen;
- Blocked;
- Frozen.

Normal migrated production/integration state should remain Frozen.

---

## 9. Freeze prerequisites

Before the original freeze, retirement reconciliation required:

- migrated master provenance complete;
- no unresolved legacy drafts/open operations.

Examples of checked open historical operations include:

- draft Ledgix Sale;
- draft Ledgix Purchase;
- draft Ledgix Sales Return;
- draft Ledgix Payment;
- draft Ledgix Stock Movement;
- open Ledgix POS Shift;
- held Ledgix POS Hold.

Freeze fails closed if blockers exist.

---

## 10. Master provenance reconciliation

Retirement reconciliation checks that relevant legacy masters map into current ERPNext masters.

Examples:

- Ledgix Item -> Item;
- Ledgix Category -> Item Group;
- Ledgix Customer -> Customer;
- Ledgix Supplier -> Supplier;
- Ledgix Price List -> Price List;
- Ledgix Item Price -> Item Price;
- Ledgix Payment Method -> Mode of Payment.

Migration marker fields preserve provenance.

---

## 11. Why current balances are not forced to match legacy ledgers

The legacy retirement policy explicitly does not force:

- current ERPNext stock;
- current receivables;
- current balances

to equal stale historical Ledgix tables after cutover.

Once ERPNext became authority, new business continued there.

The legacy snapshot is historical evidence, not a live reconciliation ledger.

---

## 12. Deterministic frozen snapshot

Freeze captures a deterministic snapshot for every tracked legacy DocType.

Per DocType evidence includes:

- existence;
- count;
- latest modified timestamp;
- SHA-256 digest over stable row identity/status metadata.

The combined snapshot is stored in the retirement state.

---

## 13. Snapshot verification

Current administrative verification can compare:

    persisted frozen snapshot
      vs
    current legacy rows

A mismatch fails retirement verification.

This detects post-freeze historical mutation.

---

## 14. Read-only acceptance verifier

Release/recovery acceptance uses:

    setup/phase12_read_only.py

This version performs digest comparison without updating verification timestamps or retirement metadata.

Use this for evidence/audit gates.

---

## 15. Document-event write guard

hooks.py registers the legacy write guard on frozen historical models for:

- before_insert;
- before_save;
- before_submit;
- before_cancel;
- on_trash.

When Frozen, ordinary mutation raises a validation error.

---

## 16. Internal bypass

legacy_retirement.py includes an explicit internal bypass flag/context for controlled migration/rollback work.

This is not a public operational escape hatch.

Do not use it to make ordinary new legacy transactions.

---

## 17. Read-only legacy permissions

When Frozen, Phase 12 setup reapplies audit-only Custom DocPerm.

Expected audit roles:

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

Allowed intent:

- read;
- report;
- export;
- print.

Disallowed:

- write;
- create;
- delete;
- submit;
- cancel;
- amend;
- share;
- email.

Ledgix Cashier receives no legacy business access.

---

## 18. Why retirement runs after normal permission sync

Normal Ledgix permission policy still contains historical rows needed for pre-freeze/rollback behavior.

After-migrate ordering applies normal permissions first, then:

    erpnext_phase12_legacy_retirement.after_migrate

If retirement state is Frozen, the final step rewrites the tracked legacy business DocTypes to audit-only.

This prevents migrate from accidentally reopening frozen ledgers.

---

## 19. Controlled unfreeze for rollback

A controlled rollback can release the freeze only through the exact confirmation:

    UNFREEZE LEGACY LEDGERS FOR CONTROLLED ROLLBACK

The action requires:

- System Manager or Ledgix Admin.

It changes retirement state to Not Frozen and restores pre-retirement Ledgix permission policy.

This is a rollback window, not normal operation.

---

## 20. Refreeze requirement

After any controlled rollback/migration work using legacy writes:

- reconcile;
- freeze again;
- restore read-only permissions;
- verify snapshot.

Do not leave legacy ledgers writable.

---

## 21. Freeze confirmation

Original/administrative freeze requires exact confirmation:

    FREEZE LEGACY LEDGERS AFTER RECONCILIATION

This prevents accidental retirement activation.

---

## 22. Idempotent freeze

If already Frozen, freeze operation verifies the existing snapshot.

It does not silently create a new baseline over mutated history.

If snapshot changed, it fails closed.

---

## 23. Business history vs FBR tax-master retirement

This distinction is critical.

### Historical business engine

Kept physically, frozen/read-only.

### Old mixed tax/FBR configuration engine

Key old source masters were physically retired from current source/schema authority during the FBR redesign/cleanup.

These are different retirement strategies.

Do not assume "all legacy is merely frozen."

---

## 24. Physically retired old tax/FBR source concepts

The current architecture no longer uses old mixed configuration masters such as:

- Ledgix Tax Profile;
- Ledgix Tax Category;
- Ledgix Tax Rate;
- Ledgix Item Tax Profile;
- global Ledgix FBR Settings as the active V2 configuration authority.

Current replacements are:

- ERPNext native monetary tax;
- Company-scoped Ledgix FBR Integration Profile;
- current FBR mappings/reference/certification/submission evidence.

Historical audit/detail evidence can remain where needed.

---

## 25. Stale historical comments/files

Some source comments, package declarations or archived documents can still mention retired concepts because they describe earlier phases.

Current runtime wiring and actual source tree win.

Do not resurrect a retired model simply because an old comment/package name references it.

---

## 26. Compatibility IDs

Current services can accept historical identifiers and resolve them to migrated ERPNext records.

This supports:

- old frontend contracts;
- migration provenance;
- historical references.

Compatibility lookup is not permission to write a new legacy record.

---

## 27. Compatibility RPCs

hooks.py redirects historical Ledgix RPC names to:

- ERPNext-native compatibility services; or
- fail-closed retirement guards.

This strangler pattern allowed the frontend/API surface to evolve independently of storage authority.

---

## 28. No physical business-history deletion yet

Phase 12 intentionally preserved rows/schema.

Physical deletion of frozen business history remains a separate destructive project.

It requires:

- observation period;
- backup;
- rollback plan;
- retention/legal review;
- import/caller analysis;
- migration upgrade analysis;
- proof no historical read/audit dependency remains.

Do not delete merely because a DocType is no longer authoritative.

---

## 29. Cleanup after documentation

A future source-cleanup project can assess:

- historical API modules;
- historical services;
- migration probes;
- old scripts;
- stale package declarations;
- duplicate docs;
- obsolete assets;
- physical legacy schema.

Each deletion requires dependency proof.

---

## 30. Fresh sites vs migrated sites

### Fresh site

May have legacy schema from the app but no historical legacy data.

### Migrated site

Can have frozen historical records and retirement snapshot.

Current code must work safely for both.

Do not assume every site has migration history.

---

## 31. Migration archive

Historical phase plans/evidence remain under:

    docs/archive/migration/

They intentionally preserve period wording.

Do not rewrite them into current status.

Use them to answer:

> "Why did we make this migration decision?"

Do not use them as current operations runbooks.

---

## 32. Current documentation authority

For current operation/development use:

- docs/developer/ARCHITECTURE.md;
- BUSINESS_WORKFLOWS.md;
- module-specific developer docs;
- production/current client docs once completed.

Archived migration docs are background only.

---

## 33. Recovery behavior

A migrated-site restore should preserve:

- retirement state Frozen;
- historical rows;
- frozen snapshot;
- read-only policy.

Recovery gates verify this.

A restored site whose digest no longer matches is not considered safely recovered.

---

## 34. Security behavior

Frozen legacy ledgers are a security boundary as well as architecture boundary.

Reopening them can create:

- alternate transaction path;
- audit ambiguity;
- conflicting accounting;
- hidden unauthorized writes.

Do not grant write access for convenience.

---

## 35. FBR migration closure

Phase 9 cut FBR source from historical Ledgix Sale to native:

- Sales Invoice;
- POS Invoice.

Later FBR V2 redesign further replaced old configuration with company-scoped V2 evidence/configuration.

Current FBR architecture is documented separately.

---

## 36. Reporting migration closure

Current reports/BI read ERPNext-native data.

Do not fix a current report by switching it back to frozen Ledgix Sale/Purchase/Stock tables.

If a historical report is desired, label it historical/audit explicitly.

---

## 37. Product migration closure

Phase 11/13 established:

- Ledgix custom product shell;
- native ERPNext forms/lists for operational work;
- Business Profile configuration;
- one codebase across client types;
- permissions remain server authority.

No per-client fork is required.

---

## 38. Migration safety principles

Future migrations should preserve lessons from the completed cutover:

- establish authority before moving data;
- prove native capability;
- migrate masters before transactions;
- preserve source provenance;
- use idempotent operations;
- gate destructive actions;
- test rollback;
- freeze old engines only after reconciliation;
- separate current truth from historical evidence;
- do not mutate accounting merely to make tests pass.

---

## 39. Never do

Do not:

- create new current Ledgix Sale/Purchase/Payment records;
- unfreeze legacy ledgers for normal operation;
- overwrite frozen snapshot after mutation;
- delete historical schema without retention/rollback proof;
- follow archived "active phase" wording as current instruction;
- bring back old monetary tax engine;
- treat legacy current balance as superior to ERPNext;
- run destructive historical migration gates on Production casually.

---

## 40. Current migration closure baseline

Final migration progress recorded:

- Phases 0–13 COMPLETE;
- no Phase 14;
- ERPNext authority established;
- legacy business history frozen;
- client profile SaaS architecture complete.

Post-migration workstreams are:

- client onboarding;
- production provisioning;
- release hardening;
- FBR client certification;
- normal product development.

---

## 41. Source map

| Concern | Current source |
|---|---|
| Retirement state / guard | api/legacy_retirement.py |
| Read-only permission enforcement | setup/erpnext_phase12_legacy_retirement.py |
| Read-only digest verifier | setup/phase12_read_only.py |
| Hooked write guards | hooks.py |
| Historical phase evidence | docs/archive/migration/ |
| Migration closure ledger | docs/archive/migration/erpnext_core_migration_progress.md |

---

## 42. Summary

> **The ERPNext migration is finished: ERPNext owns current business truth, historical duplicate Ledgix business rows remain frozen and hash-verifiable for audit/rollback, old mixed tax/FBR masters were retired separately, and any future physical cleanup must be a new explicitly approved destructive project rather than an extension of the completed migration.**
