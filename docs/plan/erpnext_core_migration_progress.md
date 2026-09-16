# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `erpnext-core-migration`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This file records exercised evidence against `erpnext_core_migration_plan.md`. A phase is not marked complete merely because code exists; runtime gates must pass on the dedicated integration site where applicable.

---

## Phase 0 — Baseline / Safety

### Completed

- Repository architecture audit completed.
- ERPNext-core master plan locked.
- Rollback baseline recorded at `148b35e63371cb0bd5bd5408df69f5262e64680e`.
- Rollback tag `pre-erpnext-core-2026-09-16` created and pushed.
- Superseded plan removed.
- Repository CI, package validation, ERPNext dependency validation and secret scan established.
- Runtime bench/sites/databases/secrets/environments are excluded from Git.
- Tested Frappe/ERPNext baseline is tracked in `config/framework.lock` rather than vendoring framework source.

### Pending before production cutover

- Back up any meaningful staging/production Ledgix database/site.
- Record installed apps/framework versions on each staging/production site immediately before cutover work.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site — COMPLETE

### Dependency plumbing

- `required_apps = ["erpnext"]` is declared in Ledgix hooks.
- `pyproject.toml` declares Frappe v15 + ERPNext v15 support.
- Local and production install/deploy scripts prepare ERPNext before Ledgix site migration.
- ERPNext dependency validation is part of local CI.
- `site_setup.sh` is compatible with recursive required-app installation.

### Proven framework baseline

- Frappe `15.113.4`, commit `588e443808206a7bfe87429c5a55e16016ec7840`.
- ERPNext `15.121.3`, commit `26f06878346fb6861229ccb1fe3a53dc1bf5bad3`.
- Ledgix `0.0.1` from `erpnext-core-migration`.

### Fresh-site evidence

Integration site: `ledgix-erpnext.local`

Verified on the real bench:

- all three apps installed;
- migrate completed;
- Ledgix assets built;
- `site_config.json` exists;
- `frappe.get_installed_apps()` returned `frappe`, `erpnext`, `ledgix_saas`;
- runtime files/secrets remained outside Git.

**Phase 1 decision: PASS.**

---

## Phase 2 — Native ERPNext Capability / Gap Matrix — FINAL REGRESSION VALIDATION PENDING

### Objective

Prove what Ledgix can replace with ERPNext native authority before building adapters or retiring any existing Ledgix business model.

### Schema capability evidence

The integration-site schema probe confirmed native models for masters, pricing, selling, payments, buying, stock, serial/batch and POS opening/closing. The submittable probe was corrected to use Frappe v15 `meta.is_submittable`.

Pinned-source verification confirmed ERPNext `15.121.3` POS Invoice intentionally has no `update_stock` field. POS stock/accounting is evaluated through the native closing/consolidation lifecycle rather than by adding a compatibility field.

### Integration business bootstrap — PASS

The isolated test business was created through ERPNext setup logic:

- Company: `Ledgix ERPNext Integration` (`LEI`)
- Country: Pakistan
- Currency: PKR
- Fiscal year: 2026-07-01 through 2027-06-30
- Chart of Accounts: Standard

Post-bootstrap evidence included 82 accounts, 5 warehouses, 2 price lists, 5 modes of payment, required groups/UOMs and no behavioral preflight blockers.

### Core behavioral batch — PASS

Real integration-site execution passed all primary business-engine paths.

#### Invoice-only / FBR-style profile — PASS

Proven natively:

- non-stock Item;
- submitted Sales Invoice;
- GL posting;
- zero stock ledger effect;
- Payment Entry settlement;
- linked native return/Credit Note;
- no parallel `Ledgix Sale` creation.

**Decision:** invoice + FBR-only clients can use ERPNext non-stock Items and Sales Invoice/Payment Entry without fake or negative inventory.

#### Purchase / inventory / stock sale / return — PASS

Proven natively:

- Purchase Order -> Purchase Receipt -> Purchase Invoice;
- supplier Payment Entry and AP settlement;
- stock receipt, stock sale and linked stock return;
- GL posting throughout;
- no parallel Ledgix Sale/Purchase/Payment/Stock Movement creation.

#### POS / split payment / opening-closing — PASS

Proven natively:

- POS Profile and POS Opening Entry;
- submitted POS Invoice;
- split tender using Cash + Credit Card;
- fully paid POS transaction;
- POS Closing Entry;
- consolidation into submitted Sales Invoice;
- no duplicate stock posting;
- no parallel Ledgix Sale/Payment/POS Shift/Stock Movement creation.

**Current POS decision:** keep the Ledgix POS UX over the ERPNext native engine unless later UI evaluation justifies using ERPNext's native screen directly.

### Extended final-gate first run — useful evidence, harness corrections applied

The first extended final-gate execution proved most of the remaining capability but exposed three harness/environment issues rather than business-engine failures:

1. Pricing Rule returned the expected `price_list_rate=1000` and `discount_percentage=10`; the test incorrectly treated a context-dependent raw `rate=0` as failure. The assertion now proves the native rule inputs/effective rate instead.
2. Stock Reconciliation submitted and produced the correct final bin quantity `7.0`; ERPNext v15 may represent reconciliation through `qty_after_transaction` even when `actual_qty=0`. The assertion now follows ERPNext's reconciliation semantics.
3. Draft POS proof reached a Redis Queue connection error on `127.0.0.1:11000`. The guarded final-gate runner now starts/stops temporary Redis cache/queue automatically through `deploy/bench_redis.sh`.

Tax architecture evidence already passed and confirms:

- ordinary percentage tax rows/item tax templates are native candidates;
- inclusive-tax primitives exist;
- zero-rated/not-applicable concepts have native financial primitives;
- a separate ERPNext withholding model exists but must not be blindly mapped to Ledgix Sales Tax Withheld at Source;
- Third Schedule/notified retail price and FBR legal classifications remain explicit Phase 4 extension/parity work.

### Phase 2 completion rule

The Phase 3 combined runner now re-runs the complete Phase 2 final gate after migration. Phase 2 is marked COMPLETE only when that regression gate passes on `ledgix-erpnext.local`.

No production authority cutover has occurred.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — IMPLEMENTED, FINAL GATE PENDING

### Goal

Establish the target Ledgix-on-ERPNext schema before transaction cutover, while preserving existing Ledgix compatibility until later migration phases.

### Standard master ownership locked

No new duplicate business masters were introduced. Target authority remains:

- ERPNext `Item` / `Item Group` / UOM;
- ERPNext `Customer` / `Supplier` / Address / Contact;
- ERPNext `Price List` / `Item Price` / `Pricing Rule`;
- ERPNext Mode of Payment, sales, purchase, payment, stock and POS documents.

### ERPNext Customer FBR extension — IMPLEMENTED

ERPNext `Customer` receives Ledgix-owned fields for:

- buyer registration type;
- NTN/CNIC;
- STRN;
- province;
- FBR address;
- verification status/date.

Commercial identity, contacts, addresses, pricing defaults, credit and receivables remain native ERPNext responsibilities.

### Item Tax Profile relink — IMPLEMENTED SAFELY

`Ledgix Item Tax Profile` now supports `ERPNext Item` as the target product reference.

- new ERPNext-native profiles can exist without a duplicate Ledgix Item;
- the old `Ledgix Item` link is retained as an optional migration compatibility reference;
- an idempotent backfill only links an existing ERPNext Item when a safe matching item code already exists;
- the Phase 3 synchronizer does not create/synchronize master Items and does not cut authority over.

### ERPNext sales/FBR envelope — IMPLEMENTED

Both `Sales Invoice` and `POS Invoice` receive server-managed Ledgix fields for:

- FBR status;
- FBR invoice number/reference;
- submitted timestamp;
- error code/message;
- reconciliation-required state;
- submission trigger;
- client-sale/idempotency identifier;
- immutable header snapshot version + JSON.

Returns/Credit Notes inherit the same target storage model through ERPNext's native return documents.

### Immutable line-level FBR snapshot — IMPLEMENTED

`Sales Invoice Item` and `POS Invoice Item` receive read-only/no-copy legal snapshot fields for:

- source Ledgix FBR Item Profile;
- HS Code;
- FBR UOM;
- Sales Type;
- FBR rate description;
- Sandbox Scenario ID;
- SRO schedule/item references;
- transaction-value vs notified-retail-price tax basis;
- Notified Retail Price;
- Sales Tax Withheld at Source;
- Extra Tax;
- Further Tax;
- FED Payable;
- snapshot version + JSON.

These are storage contracts only in Phase 3. Phase 4 must prove monetary tax parity before ERPNext becomes authoritative for these tax amounts.

### Business/client profile configuration — IMPLEMENTED

A new site-level Single DocType, `Ledgix Business Profile`, configures product experience without duplicating standard masters.

Supported profiles:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

Feature flags cover Sales Invoice, POS, inventory, buying, advanced inventory, B2B, FBR and accounting-workspace exposure. These flags are UX/product configuration only; DocType/server permissions remain authoritative.

### Ledgix role mapping to standard ERPNext documents — IMPLEMENTED

Explicit additive `Custom DocPerm` grants map:

- `Ledgix Cashier` to customer/sales/POS/payment operations and read-only operational references;
- `Ledgix Manager` to operational masters, selling, buying, stock and controlled transaction correction;
- `Ledgix Admin` to broad Ledgix operational administration.

Native ERPNext roles/permissions are not deleted or replaced. Cashier purchase-write access is intentionally excluded.

### Migration-safe installation — IMPLEMENTED

Phase 3 schema is installed/maintained through:

- `ledgix_saas.patches.v1_0.sync_erpnext_extension_schema` after model sync;
- `ledgix_saas.setup.erpnext_extensions.after_migrate` for idempotent ongoing synchronization;
- existing Ledgix Custom Field fixture filtering;
- `apps/ledgix_saas/setup/test_erpnext_extensions.py` static contract tests.

Design contract:

- `docs/plan/erpnext_phase3_extension_schema.md`

### Phase 3 runtime final gate — READY

Combined runner:

- `scripts/run_erpnext_phase3_final_gate.sh`

It performs one guarded integration-site validation sequence:

1. local repository CI;
2. temporary Redis runtime startup;
3. `bench migrate` to apply Phase 3 schema/patches;
4. full Phase 2 regression final gate;
5. Phase 3 idempotent schema sync twice;
6. Custom Field type/options/read-only/no-copy validation;
7. duplicate-free Custom Field validation;
8. standard ERPNext Ledgix-role permission validation;
9. Business Profile default-resolution validation;
10. ERPNext Item-only FBR Item Profile persistence;
11. ERPNext Customer FBR field persistence;
12. draft Sales Invoice header/line FBR snapshot persistence;
13. temporary Redis cleanup.

### Phase 3 completion rule

Phase 3 is marked COMPLETE only when the combined runner proves both the Phase 2 regression and Phase 3 schema gate green on `ledgix-erpnext.local`.

No old Ledgix master, transaction, tax engine or FBR submission source has been retired by Phase 3.

---

## Phase 4 — Tax Parity and Accounting Foundation — NEXT AFTER COMBINED GATE

ERPNext will become monetary/tax authority only after an explicit parity matrix passes for:

- ordinary taxable sales;
- tax-inclusive pricing;
- zero-rated and exempt sales;
- Third Schedule/notified retail price;
- Further Tax;
- Extra Tax;
- FED;
- Sales Tax Withheld at Source;
- mixed invoices;
- full and partial returns;
- price-only credit notes where required.

The parity gate must compare ERPNext totals/GL with Ledgix/FBR-required values and adapt FBR preview to the ERPNext transaction source before any old tax engine is retired.

---

## Safety Status

- No production sales, purchase, stock, payment, tax, FBR, POS, receivable or master-data authority has been cut over.
- Existing Ledgix business DocTypes/services remain available while replacement paths are proven.
- Migration behavioral/schema helpers are hard-guarded to `ledgix-erpnext.local`.
- FBR has not been switched to ERPNext transaction sourcing yet.
- Phase 3 adds extension/storage contracts and permissions only; it does not perform master or transaction cutover.
