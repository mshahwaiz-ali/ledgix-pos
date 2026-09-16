# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `erpnext-core-migration`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This ledger records exercised evidence against `erpnext_core_migration_plan.md`. Code existence alone never closes a phase; the guarded integration-site runtime gate must pass where applicable.

---

## Phase 0 — Baseline / Safety — COMPLETE FOR MIGRATION DEVELOPMENT

Completed:

- repository architecture audit and ERPNext-core master plan;
- rollback baseline/tag;
- repository CI/package validation/dependency validation/secret scan;
- runtime bench/sites/databases/secrets/environments excluded from Git;
- tested framework baseline tracked in `config/framework.lock` instead of vendoring framework source.

Still mandatory before any real staging/production cutover:

- fresh database/site backups;
- exact installed-app/framework version capture;
- cutover-specific rollback checkpoint.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site — COMPLETE

Dependency plumbing is active through `required_apps = ["erpnext"]`, v15 dependency constraints and deploy/install validation.

Proven baseline:

- Frappe `15.113.4`, commit `588e443808206a7bfe87429c5a55e16016ec7840`;
- ERPNext `15.121.3`, commit `26f06878346fb6861229ccb1fe3a53dc1bf5bad3`;
- Ledgix `0.0.1` from `erpnext-core-migration`;
- integration site `ledgix-erpnext.local`.

Fresh-site migrate/build/list-apps/site-config checks passed.

---

## Phase 2 — Native ERPNext Capability / Gap Matrix — COMPLETE

The final Phase 2 regression gate passed on `ledgix-erpnext.local` during the Phase 3 combined runtime gate on 2026-09-16.

### Native capability proven

- standard Item / Item Group / UOM / Customer / Supplier / Address / Contact;
- Price List / Item Price / Pricing Rule;
- Sales Invoice / native return Credit Note;
- Mode of Payment / Payment Entry / outstanding and unallocated payment behavior;
- Purchase Order / Purchase Receipt / Purchase Invoice / supplier payment;
- Warehouse / Stock Entry / Stock Reconciliation / Stock Ledger;
- Batch / Serial No / Serial and Batch Bundle;
- POS Profile / Opening / POS Invoice / split tender / Closing / consolidation;
- persisted unfinished/draft POS Invoice;
- native print rendering.

### Runtime business-engine evidence — PASS

Invoice/FBR-only path:

- non-stock Item;
- Sales Invoice + GL;
- zero stock effect;
- Payment Entry settlement;
- native return;
- no parallel Ledgix Sale.

Purchase/inventory path:

- PO -> Receipt -> Invoice -> supplier Payment Entry;
- stock increase, sale reduction and native return restoration;
- GL throughout;
- no parallel Ledgix Purchase/Payment/Stock Movement/Sale.

POS path:

- POS opening;
- Cash + Credit Card split payment;
- submitted POS Invoice;
- closing and consolidated Sales Invoice;
- ERPNext consolidated accounting/stock ownership;
- no parallel Ledgix POS Shift/Sale/Payment/Stock Movement.

Extended evidence:

- Pricing Rule resolves correctly;
- partial Payment Entry preserves outstanding;
- unallocated customer advance works natively;
- partial Credit Note works;
- Stock Reconciliation authoritative quantity proven through `qty_after_transaction`;
- serial/batch bundles proven;
- draft POS creates no GL/stock posting until submit;
- native tax primitives exist, with FBR-specific semantics reserved for Phase 4.

### Phase 2 decisions

- standard masters/pricing/payments/AR/AP/buying/stock/serial/batch: **USE NATIVE**;
- invoice + FBR-only clients: **USE NATIVE non-stock Item + Sales Invoice**;
- POS engine: **ERPNext authority; keep Ledgix UX wrapper for now**;
- POS hold: **Ledgix UX over native draft POS Invoice**;
- financial tax: **extend ERPNext only after Phase 4 parity**;
- FBR compliance metadata/submission/reconciliation: **KEEP LEDGIX**.

No production authority cutover occurred.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — COMPLETE

The combined Phase 2 + Phase 3 gate passed on `ledgix-erpnext.local` on 2026-09-16 at branch commit `7c6bd61b2faf`.

### ERPNext Customer FBR extension — PASS

ERPNext `Customer` now persists Ledgix-specific buyer fields for registration type, NTN/CNIC, STRN, province, FBR address and verification state/date.

### Item Tax Profile relink — PASS

`Ledgix Item Tax Profile` supports `erpnext_item -> Item` as the target authority while retaining the legacy `Ledgix Item` reference as optional migration compatibility only.

The runtime gate proved an ERPNext-Item-only profile without requiring a legacy item.

### ERPNext sales/FBR envelope — PASS

`Sales Invoice` and `POS Invoice` contain server-managed Ledgix fields for FBR status/reference/result/reconciliation state, client-sale identifier and immutable header snapshot.

`Sales Invoice Item` and `POS Invoice Item` contain immutable line snapshots for:

- FBR Item Profile;
- HS Code / FBR UOM / Sales Type / rate description;
- scenario and SRO references;
- Transaction Value vs Notified Retail Price basis;
- notified retail price;
- Sales Tax Withheld at Source;
- Extra Tax;
- Further Tax;
- FED Payable;
- versioned JSON snapshot.

### Business/client profiles — PASS

Site-level `Ledgix Business Profile` supports:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

These flags curate product UX only; server permissions remain authoritative.

### Role mapping — PASS

Additive Ledgix Cashier/Manager/Admin permissions on target ERPNext DocTypes were installed and the gate reported no mismatches. Native ERPNext permissions are retained.

### Idempotency — PASS

The schema synchronizer ran twice without duplicate Custom Fields. The final gate proved every configured Phase 3 field exactly once and all persistence contracts green.

No old Ledgix master/transaction/tax/FBR source was retired in Phase 3.

---

## Phase 4 — Tax Parity and Accounting Foundation — IMPLEMENTED, RUNTIME GATE PENDING

### Goal

Prove ERPNext as the **single monetary/tax + GL authority** while Ledgix remains the legal/FBR classification and immutable-snapshot layer.

### Foundation implemented

`ledgix_saas.setup.erpnext_tax_foundation` now provides an integration adapter that:

- never assigns a competing `grand_total`;
- resolves line tax/FBR metadata from ERPNext Item + Ledgix Item Tax Profile;
- freezes immutable line/header snapshots;
- maps ordinary Sales Tax, Extra Tax, Further Tax and FED into ERPNext Sales Taxes and Charges rows/accounts;
- keeps Sales Tax Withheld at Source separate from invoice payable/GL in Phase 4, matching the existing Ledgix/FBR semantic contract;
- maps Third Schedule/notified retail price into a legal tax basis while ERPNext remains the final total/GL authority;
- uses native `On Net Total + included_in_print_rate` for homogeneous tax-inclusive pricing because ERPNext rejects inclusive `Actual` tax rows;
- fails closed for unproven mixed-rate/Third-Schedule inclusive pricing rather than guessing.

ERPNext `Company` receives account-map fields for Sales Tax, Extra Tax, Further Tax, FED and a reserved withheld account. No duplicate Company/master model is introduced.

### Mandatory 13-case matrix implemented

The isolated runtime gate covers:

1. ordinary taxable item;
2. tax-inclusive price;
3. zero-rated item;
4. exempt item;
5. Third Schedule / Notified Retail Price;
6. Further Tax;
7. Extra Tax;
8. FED;
9. Sales Tax Withheld at Source;
10. mixed-tax invoice;
11. full return;
12. partial return;
13. non-stock financial/price-adjustment Credit Note.

Each relevant case checks submitted ERPNext documents, net/tax/grand totals, tax-account GL, balanced GL, immutable line snapshots, FBR tax preview and zero stock effect for the dedicated non-stock fixtures.

Returns use ERPNext's native return mapper. The financial/price-adjustment case uses `qty=-1`, a reduced adjustment rate and `update_stock=0`; ERPNext requires a negative item quantity on a linked return and therefore a zero-quantity linked return is intentionally not used.

### FBR safety

Phase 4 preview code does **not**:

- call FBR/PRAL network endpoints;
- submit sandbox or production invoices;
- cut over FBR Submission Log authority;
- switch the real FBR payload datasource;
- retire the legacy Ledgix tax engine.

### Final gate

Runner:

- `scripts/run_erpnext_phase4_final_gate.sh`

Sequence:

1. local CI;
2. Redis readiness;
3. migrate Phase 4 Company extension;
4. full Phase 2 regression;
5. full Phase 3 regression;
6. Phase 4 foundation/account-map checks;
7. all 13 real ERPNext tax/accounting parity cases;
8. single PASS/FAIL verdict.

Phase 4 becomes **COMPLETE only after this runtime gate passes** on `ledgix-erpnext.local`.

Design contract:

- `docs/plan/erpnext_phase4_tax_parity_matrix.md`

---

## Safety Status

- No staging/production authority has been cut over.
- Existing Ledgix masters, transactions, tax engine and FBR source remain available while replacement paths are proven.
- Migration behavioral/schema/tax helpers are hard-guarded to `ledgix-erpnext.local` where they create integration data.
- No FBR network submission is performed by migration gates.
- Phase 4 code is a parity foundation, not yet an automatic Sales Invoice event hook.
