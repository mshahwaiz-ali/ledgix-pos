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

Final evidence:

- local CI/migrate/apps green;
- Phase 6+7 fail-closed static contracts passed **25/25**;
- mapped Supplier AP preflight reconciled with no blocker;
- **11/11** Phase 7 runtime cases passed;
- PO -> PR -> PI -> Payment Entry, direct stock Purchase Invoice and non-stock purchasing proven;
- Material Transfer, Stock Reconciliation, Batch/Serial, purchase return, cancellation/backdating and valuation proven;
- native Bin/SLE stock and valuation matched expected quantities;
- no parallel Ledgix Purchase/Stock Movement/Lot/Serial writes.

Canonical service: `ledgix_saas.services.erpnext_buying_inventory`.

Design: `docs/plan/erpnext_phase7_buying_inventory_cutover.md`.

---

## Phase 8 — POS Engine Migration — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `c89587a04a7d4fa552d4af06fe71097ff39ffee7`

Architecture decision: **retain the Ledgix POS screen, replace its business backend with ERPNext POS authority**.

The guarded final gate on `ledgix-erpnext.local` passed with `phase8_complete=true` and `phase9_ready=true`.

Final evidence:

- local CI/migrate/apps green;
- Phase 6+7+8 fail-closed static contracts passed **36/36**;
- **7/7** Phase 8 runtime cases passed:
  - native POS boot/catalog/profile/payment configuration;
  - native POS Opening Entry shift;
  - native draft holds with zero GL/SLE;
  - split-tender checkout/change/idempotency;
  - native POS return with source-rate authority;
  - native Closing Entry/consolidation/stock movement;
  - no parallel legacy POS writes;
- Retail transaction authority is `POS Invoice`;
- B2B remains native `Sales Invoice`;
- stock/pricing/customer/payment authority is ERPNext;
- final stock delta proved exactly once through native consolidation;
- Ledgix Sale/Payment/POS Shift/POS Hold/stock/FBR-log counts stayed unchanged in the cutover matrix;
- FBR source/network cutover was explicitly not performed during Phase 8.

Canonical service: `ledgix_saas.services.erpnext_pos`.

Compatibility layer: `ledgix_saas.api.pos_compat`.

Design: `docs/plan/erpnext_phase8_pos_cutover.md`.

---

## Phase 9 — FBR Source Cutover — IMPLEMENTED, FINAL RUNTIME GATE PENDING

Phase 9 changes the FBR transaction source while retaining the Ledgix FBR/compliance layer.

### Implemented authority boundary

Native source documents:

- `Sales Invoice` for B2B/invoice sales;
- `POS Invoice` for retail POS sales;
- native ERPNext return invoice / Credit Note for returns.

Ledgix remains authoritative for:

- FBR settings and Sandbox/Production controls;
- immutable legal/FBR snapshots and payload mapping;
- FBR client/response parsing;
- `Ledgix FBR Submission Log`;
- QR/reference/status/error metadata;
- reconciliation-required safeguards;
- correction tracking.

### Safety rules implemented

- submitted native invoice lines must contain immutable FBR snapshot JSON;
- payload totals are reconciled to ERPNext totals before network submission;
- consolidated POS accounting `Sales Invoice` is explicitly excluded as a second FBR source;
- legacy `Ledgix Sale` production submission endpoint is fail-closed/retired;
- native official submission is idempotent once an FBR invoice number exists;
- ambiguous Production POST outcome enters `Reconciliation Required` and blocks blind retry;
- native cancellation is blocked after official FBR submission/reconciliation state;
- native Credit Note sends the original FBR invoice number as `invoiceRefNo`;
- Tax & FBR Center FBR operations are routed to native `Sales Invoice` / `POS Invoice` references;
- correction requests support native ERPNext references while legacy records remain historical.

Canonical adapter: `ledgix_saas.api.fbr_native`.

UI adapter: `ledgix_saas.api.fbr_native_ui` + `public/js/ledgix_fbr_native_center.js`.

Schema: `ledgix_saas.setup.erpnext_phase9_extensions`.

Final runner: `scripts/run_erpnext_phase9_final_gate.sh`.

The Phase 9 runtime gate is restricted to `ledgix-erpnext.local` and monkeypatches FBR validate/post adapters so **zero real FBR/PRAL network calls** occur during the migration proof.

Required final result: `phase9_complete=true`, `phase10_ready=true`, no failed cases and `real_fbr_network_calls=0`.

Design: `docs/plan/erpnext_phase9_fbr_cutover.md`.

---

## Next after Phase 9

**Phase 10 — Final Print Redesign**.

The known legacy print targets were intentionally deferred during transaction-engine migration. Phase 10 will make native Sales/POS/Credit Note printing and Ledgix branding/thermal/A4 formats authoritative over the migrated ERPNext documents.

---

## Safety Status

- Development is direct on `main`; no PR branch is used.
- ERPNext core is never modified or vendored.
- All destructive/runtime migration gates are restricted to `ledgix-erpnext.local`.
- Legacy records remain preserved until later freeze/retirement cleanup.
- Phase 6 B2B paths create no parallel Ledgix financial ledgers.
- Phase 7 buying/inventory paths create no parallel Ledgix purchase/stock ledgers.
- Phase 8 POS paths create no parallel Ledgix sale/payment/shift/hold/stock ledgers.
- Phase 9 native FBR adapter writes FBR metadata/logs only and does not recreate business ledgers.
- Customer AR and Supplier AP mismatches fail closed.
- Production FBR ambiguous outcomes fail closed pending external reconciliation.
