# Phase 12 — Legacy Freeze, Reconciliation and Retirement

**Implementation branch:** `main`  
**Integration site:** `ledgix-erpnext.local`  
**Pinned stack:** Frappe 15.113.4 / ERPNext 15.121.3

## Goal

Phase 12 does **not** delete old business data. It converts duplicate Ledgix business-engine records into immutable historical audit sources after the ERPNext cutovers have already proven authority.

The sequence is:

1. reconcile migration provenance;
2. resolve old draft/open operations;
3. capture a deterministic historical snapshot;
4. mark legacy business records Frozen;
5. reduce Ledgix business-role permissions to read/report/export/print only;
6. observe the frozen snapshot across subsequent migrations/releases;
7. only consider physical code/schema deletion in a later destructive migration after observation and production reconciliation.

## ERPNext authority

Current business authority remains:

- Item / Item Group / UOM / pricing -> ERPNext;
- Customer / Supplier / Address / Contact -> ERPNext;
- sales / POS / returns -> Sales Invoice / POS Invoice / native returns;
- payments / AR / AP -> Payment Entry / GL;
- purchases -> ERPNext buying documents;
- inventory -> Warehouse / Stock Entry / Reconciliation / SLE / Bin;
- serial/batch -> ERPNext Serial No / Batch / Serial and Batch Bundle.

Ledgix continues to own active product/compliance capabilities:

- Business Profile;
- Brand Settings;
- Item Tax Profile and legal/FBR classification;
- FBR Settings / Submission Log / Tax Audit Log / correction workflow;
- POS UX, Tax & FBR Center, Inventory Intelligence UX;
- migration/retirement audit metadata.

Those active Ledgix product/compliance DocTypes are explicitly excluded from the legacy freeze list.

## Legacy freeze scope

Top-level duplicated business records include:

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

Their child rows are included in the digest snapshot so later mutation is detectable.

## Why current native totals are not forced to equal legacy totals

After Phases 6–11, ERPNext intentionally continues receiving new transactions while the old Ledgix business ledgers no longer do. Therefore current stock, receivable, payable, sales and purchase totals are expected to diverge from stale legacy tables after cutover.

Phase 12 does not manufacture parity by writing fake legacy/native balancing transactions.

Retirement reconciliation instead proves:

- one-time master provenance mapping is complete;
- no unresolved legacy draft/open transaction remains;
- prior cutover gates already proved AR/AP, sales, stock, tax, FBR, BI/report and product-shell authority at their transition boundary;
- the historical legacy snapshot becomes immutable from the Phase 12 freeze point forward.

## Master provenance gate

Required source -> target provenance:

- Ledgix Item -> Item `custom_ledgix_legacy_item`;
- Ledgix Category -> Item Group `custom_ledgix_legacy_category`;
- Ledgix Customer -> Customer `custom_ledgix_legacy_customer`;
- Ledgix Supplier -> Supplier `custom_ledgix_legacy_supplier`;
- Ledgix Price List -> Price List `custom_ledgix_legacy_price_list`;
- enabled Ledgix Item Price -> Item Price `custom_ledgix_legacy_item_price`;
- Ledgix Payment Method -> Mode of Payment `custom_ledgix_legacy_payment_method`.

Any unmapped required master blocks the freeze.

## Open-operation blockers

The freeze is blocked while unresolved legacy operational records exist, including:

- draft Ledgix Sale;
- draft Ledgix Purchase;
- draft Ledgix Sales Return;
- draft Ledgix Payment;
- draft Ledgix Stock Movement;
- open Ledgix POS Shift;
- active Ledgix POS Hold.

Because the freeze is explicit rather than automatic on migrate, a site with blockers remains repairable until those records are reconciled.

## Persisted retirement state

Single DocType:

`Ledgix Legacy Retirement State`

It stores:

- status (`Not Frozen`, `Frozen`, `Blocked`);
- freeze timestamp/user/commit;
- deterministic JSON snapshot;
- reconciliation JSON;
- last verification timestamp/user.

The snapshot records each legacy top-level/child DocType count, latest modification and SHA-256 identity digest over name/modified/docstatus metadata.

Subsequent verification must produce the exact same snapshot before physical retirement can ever be considered.

## Write guard

Once status is `Frozen`, document-event hooks reject:

- insert;
- save/update;
- submit;
- cancel;
- trash/delete.

The guard is independent of normal permission checks, so `ignore_permissions=True` does not silently bypass the retirement boundary.

A controlled internal bypass exists only through the explicit `legacy_write_bypass(...)` context for rollback/migration code. It is never enabled globally.

## Permission retirement

After successful freeze:

- System Manager -> read/report/export/print legacy records;
- Ledgix Admin -> read/report/export/print legacy records;
- Ledgix Manager -> read/report/export/print legacy records;
- Ledgix Cashier -> no legacy business-DocType access.

Frappe/ERPNext permissions remain authoritative for current work.

The normal Ledgix permission policy is intentionally left unchanged until the explicit freeze succeeds. This prevents installation of Phase 12 from trapping a site that still has reconciliation blockers.

On every future migrate, if retirement state is already Frozen, Phase 12 reapplies the audit-only permissions after the normal permission sync.

## Controlled rollback

Rollback release requires the exact confirmation phrase:

`UNFREEZE LEGACY LEDGERS FOR CONTROLLED ROLLBACK`

Release:

- changes retirement state to `Not Frozen`;
- restores the pre-retirement Ledgix permission policy;
- does not delete the frozen snapshot/reconciliation evidence;
- is intended only for a controlled rollback window.

Normal operation must reconcile and freeze again afterward.

## Compatibility cleanup

The old `ledgix_saas.api.pos` method names are retained for old clients but now read/write only ERPNext-native data/services.

The old Business Intelligence RPC is overridden to the Phase 10 ERPNext-native Inventory Intelligence adapter.

Older implementation modules remain in the repository only as historical/transition source until observation is complete. The write guard makes any accidental legacy mutation fail closed after freeze.

## No-delete rule

Phase 12 itself must not:

- delete a legacy DocType;
- delete historical business rows;
- drop/truncate legacy tables;
- rewrite historical values to fake parity.

Physical deletion belongs to a later explicit destructive migration after observation, backup and rollback planning.

## Final gate

Runner:

`scripts/run_erpnext_phase12_final_gate.sh ledgix-erpnext.local`

The gate must prove:

- master provenance complete;
- zero unresolved legacy drafts/open POS operations;
- explicit freeze succeeds;
- persisted snapshot/reconciliation evidence exists;
- snapshot verification matches exactly;
- read-only audit permissions are active;
- normal document-event write path is blocked;
- controlled bypass can be entered without actually saving a document;
- old POS compatibility list returns ERPNext POS Invoice data;
- a second freeze is idempotent;
- legacy top-level and child row counts are unchanged;
- no legacy schema/data deletion occurred.

Phase 12 closes only when `phase12_complete=true`, `phase13_ready=true`, every case passes and `legacy_snapshot_matches=true`.

## Next

Phase 13 — Client Profiles and SaaS Productization.
