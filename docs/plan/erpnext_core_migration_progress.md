# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `main`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This ledger records exercised evidence against `erpnext_core_migration_plan.md`. Code existence alone never closes a phase; guarded runtime evidence is required where a phase has an integration gate.

---

## Phase 0 — Baseline / Safety — COMPLETE FOR MIGRATION DEVELOPMENT

Repository architecture audit, rollback baseline/tag, repository/dependency/secret validation, runtime bench/site/database exclusions and pinned framework baseline are complete.

A real client cutover still requires a fresh backup, exact version capture and a production rollback checkpoint.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site — COMPLETE

Proven baseline:

- Frappe `15.113.4` / `version-15`;
- ERPNext `15.121.3` / `version-15`;
- Ledgix `0.0.1`;
- site `ledgix-erpnext.local`;
- Company `Ledgix ERPNext Integration` / PKR / Pakistan.

---

## Phase 2 — Native ERPNext Capability / Gap Matrix — COMPLETE

Native proofs cover masters, pricing, Sales Invoice/Payment Entry/Credit Note, buying, stock ledger, Batch/Serial, POS Profile, Opening Entry, split-tender POS Invoice, Closing Entry, unfinished native POS draft and native print behavior.

Decision: standard business engines use ERPNext authority; Ledgix retains product UX, FBR/compliance, intelligence and branding.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — COMPLETE

ERPNext Customer/Item/native invoice extensions, immutable legal/FBR line snapshots, business profiles, additive roles/permissions and idempotent schema synchronization are proven.

---

## Phase 4 — Tax Parity and Accounting Foundation — COMPLETE

Mandatory matrix passed **13/13**: ordinary, tax-inclusive, zero-rated, exempt, Third Schedule, Further Tax, Extra Tax, FED, Sales Tax Withheld at Source, mixed invoice, full return, partial return and price-only Credit Note.

ERPNext owns monetary totals/tax rows/GL. Ledgix owns legal/FBR classification and immutable snapshots.

---

## Phase 5 — Master Data Migration — COMPLETE

The consolidated gate proved dry-run rollback, real migration/rerun idempotence, native item/customer/supplier/pricing/payment mappings, contacts/addresses/FBR metadata, opening stock, Batch/Serial identities and non-stock invoice-only mode without SLE. Legacy source rows remain preserved.

Canonical service: `ledgix_saas.migration.erpnext_phase5_master_migration_runtime.run`.

---

## Phase 6 — Selling, Payments and Returns Cutover — COMPLETE

**Closed:** 2026-09-16  
**Final static-proof HEAD:** `3df4634dc4dc05d13231ead7427af353a799a71d`

Final evidence includes:

- Phase 2–5 regressions green;
- customer receivables preflight reconciled;
- **17/17** transaction cases green;
- full/partial payments and native AR;
- Payment Entry allocation/idempotency/cancellation;
- full/partial Credit Notes, refund and exchange;
- B2B compatibility over native Sales Invoice/Payment Entry;
- checkout discount and authorized rate-override audit;
- interrupted payment recovery and required payment references;
- malicious return-rate input could not override source ERPNext invoice rate;
- no parallel Ledgix Sale/Payment/Sales Return financial writes;
- fail-closed static contract passed **14/14**.

Canonical service: `ledgix_saas.services.erpnext_selling`.

Design: `docs/plan/erpnext_phase6_selling_cutover.md`.

---

## Phase 7 — Buying and Inventory Cutover — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `6fbfc95063becd57d051476df37219fab43ae704`

The guarded final gate on `ledgix-erpnext.local` passed with `phase7_complete=true` and `phase8_ready=true`.

### Final evidence

- local CI/migrate/apps green;
- Phase 6+7 fail-closed static contracts passed **25/25**;
- mapped Supplier AP preflight reconciled with no blocker;
- **11/11** Phase 7 runtime cases passed:
  - full PO -> PR -> PI -> supplier Payment Entry;
  - direct Purchase Invoice with stock;
  - non-stock financial-only Purchase Invoice;
  - Material Transfer;
  - Stock Reconciliation;
  - Batch / Serial and Batch Bundle authority;
  - Serial No availability/issue;
  - Purchase Return;
  - cancellation + backdated stock behavior;
  - ERPNext valuation authority;
  - no parallel Ledgix Purchase/Stock Movement/Lot/Serial writes;
- native Bin/SLE stock and valuation matched expected quantities;
- legacy purchase/stock identity counts were unchanged.

Canonical service: `ledgix_saas.services.erpnext_buying_inventory`.

Design: `docs/plan/erpnext_phase7_buying_inventory_cutover.md`.

---

## Phase 8 — POS Engine Migration — IMPLEMENTED, FINAL RUNTIME GATE PENDING

Architecture decision: **retain the Ledgix POS screen, replace its business backend with ERPNext POS authority**.

### Implemented authority boundary

Canonical service:

- `ledgix_saas.services.erpnext_pos`

Compatibility layer:

- `ledgix_saas.api.pos_compat`

Implemented native paths:

- boot/profile/payment configuration from `POS Profile`;
- Customer/Item/Item Group/Price List/Item Price/Pricing Rule catalog authority;
- availability from ERPNext Bin/stock ledger;
- cashier opening from `POS Opening Entry`;
- retail checkout from `POS Invoice`;
- split payment/reference/change through native POS payment rows;
- retail checkout idempotency through native invoice metadata;
- held Retail carts as draft `POS Invoice`;
- held B2B carts as draft `Sales Invoice`;
- retail returns via ERPNext POS return mapper with source-rate authority;
- cashier close/consolidation via `POS Closing Entry` and native consolidated Sales Invoice;
- current Ledgix RPC names routed to the Phase 8 compatibility layer using Frappe method overrides;
- known-wrong legacy `Ledgix Sale` auto-print target is suppressed with `print_deferred=true` until native/Ledgix print formats are finalized;
- Phase 6 B2B Sales Invoice path remains native and unchanged;
- no Phase 8 FBR network/source cutover.

### Final gate

Runner:

- `scripts/run_erpnext_phase8_final_gate.sh`

The guarded runtime matrix proves native boot/catalog, opening shift, draft holds with zero GL/SLE, split-tender checkout/change/idempotency, native POS return, closing/consolidation, final stock delta, and unchanged Ledgix Sale/Payment/POS Shift/POS Hold/stock/FBR-log counts.

Phase 8 closes only when the integration gate returns `phase8_complete=true` and `phase9_ready=true`.

Design: `docs/plan/erpnext_phase8_pos_cutover.md`.

---

## Next after Phase 8

**Phase 9 — FBR Source Cutover**.

The FBR integration layer stays Ledgix-owned, but the transaction datasource will deliberately switch from legacy `Ledgix Sale` to native `Sales Invoice`, `POS Invoice` and native return/Credit Note documents only after payload preview parity and no-dual-submit safeguards pass.

---

## Safety Status

- Development is direct on `main`; no PR branch is used.
- ERPNext core is never modified or vendored.
- All destructive/runtime migration gates are restricted to `ledgix-erpnext.local`.
- Legacy records remain preserved until later freeze/retirement cleanup.
- Phase 6 B2B paths create no parallel Ledgix financial ledgers.
- Phase 7 buying/inventory paths create no parallel Ledgix purchase/stock ledgers.
- Phase 8 POS paths are designed to create no parallel Ledgix sale/payment/shift/hold/stock ledgers.
- Customer AR and Supplier AP mismatches fail closed.
- FBR submission/source cutover remains intentionally deferred to Phase 9; Phase 8 must not dual-submit.
