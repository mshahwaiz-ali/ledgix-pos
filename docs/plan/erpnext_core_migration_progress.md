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
- **7/7** Phase 8 runtime cases passed;
- native POS boot/catalog/profile/payment configuration;
- native POS Opening Entry, draft holds, split-tender checkout/change/idempotency, native return and Closing Entry/consolidation;
- final stock delta proved exactly once through native consolidation;
- no parallel Ledgix Sale/Payment/POS Shift/POS Hold/stock writes;
- FBR source/network cutover remained deferred to Phase 9.

Canonical service: `ledgix_saas.services.erpnext_pos`.

Compatibility layer: `ledgix_saas.api.pos_compat`.

Design: `docs/plan/erpnext_phase8_pos_cutover.md`.

---

## Phase 9 — FBR Source Cutover — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `a441823ee23d075897fdbd30ee72ac265745f2e8`

The guarded final gate on `ledgix-erpnext.local` passed with `phase9_complete=true` and `phase10_ready=true`.

Final evidence:

- local CI/migrate/assets/apps green;
- Phase 6+7+8+9 fail-closed static contracts passed **48/48**;
- **9/9** Phase 9 runtime cases passed;
- Sales Invoice and POS Invoice payloads were built from immutable native FBR snapshots;
- validation audit persisted against the native ERPNext reference;
- Production submit idempotency persisted the official FBR invoice/QR metadata on the native document;
- native Credit Note referenced the original official FBR invoice number;
- ambiguous Production POST entered `Reconciliation Required`, blocked blind retry and required explicit reconciliation release;
- consolidated POS accounting Sales Invoice was rejected as a second FBR source;
- correction tracking accepted native ERPNext references;
- no legacy business ledger or legacy FBR-source log was created;
- legacy `Ledgix Sale` Production submission endpoint remained fail-closed/retired;
- the migration gate used mocked FBR adapters only and recorded **zero real FBR/PRAL network calls**.

Canonical adapter: `ledgix_saas.api.fbr_native`.

UI adapter: `ledgix_saas.api.fbr_native_ui` + `public/js/ledgix_fbr_native_center.js`.

Design: `docs/plan/erpnext_phase9_fbr_cutover.md`.

---

## Phase 10 — BI, Reports and Print Migration — IMPLEMENTED, FINAL RUNTIME GATE PENDING

Phase 10 removes active BI/report/print dependencies on duplicate Ledgix business ledgers while retaining the Ledgix analytics and branded document UX.

### Implemented native reporting boundary

Canonical reporting service:

- `ledgix_saas.services.erpnext_reporting`

Active authority:

- Item / Bin / Item Reorder / Item Price for stock status;
- Stock Ledger Entry for movements and inventory timeline;
- Sales Invoice + POS Invoice for sales and native returns;
- Purchase Invoice for buying reports;
- GL Entry for customer statement;
- ERPNext Batch / Serial identity through native stock data.

The current Inventory Intelligence RPC is overridden to `ledgix_saas.api.inventory_intelligence_native.get_inventory_intelligence_data`, preserving the page contract while using ERPNext-native data.

The active Ledgix report names remain available for user continuity, but their Python data sources, filters and `ref_doctype` metadata now point to ERPNext authority.

### Implemented print boundary

Native formats:

- `Ledgix ERPNext Tax Invoice` -> `Sales Invoice` / native Credit Note rendering;
- `Ledgix ERPNext POS Receipt` -> `POS Invoice` / native POS return rendering.

Native print context:

- `ledgix_saas.api.printing.get_native_invoice_print_context`

It reads ERPNext document totals/payment/return state plus the immutable native FBR snapshots and Phase 9 persisted FBR metadata. The QR is generated locally from the persisted official FBR invoice number; no external QR service is used.

Phase 8 POS compatibility now returns the native ERPNext document, DocType and Ledgix format as the print target. New POS printing never restores a `Ledgix Sale` identity just to print. Legacy print formats remain preserved for historical legacy records.

### Final gate

Runner:

- `scripts/run_erpnext_phase10_final_gate.sh`

The guarded runtime matrix is designed to prove:

- native Sales Invoice A4 render;
- native POS Invoice thermal render;
- native Credit Note label/original FBR reference;
- persisted FBR number + self-contained QR render;
- native POS print target handoff;
- active stock/sales/return/purchase/customer reports over ERPNext;
- native Inventory Intelligence;
- unchanged legacy business ledger counts;
- **zero real FBR/PRAL network adapter calls**.

Phase 10 closes only when the integration gate returns `phase10_complete=true`, `phase11_ready=true`, no failed cases and `real_fbr_network_calls=0`.

Design: `docs/plan/erpnext_phase10_bi_reports_print.md`.

---

## Next after Phase 10

**Phase 11 — Workspace and Product Simplification**.

Phase 11 will remove obsolete legacy workspace shortcuts and expose the native ERPNext business engine through the simplified Ledgix product surface, while retaining differentiated Ledgix POS, FBR, BI and branding UX.

---

## Safety Status

- Development is direct on `main`; no PR branch is used.
- ERPNext core is never modified or vendored.
- All destructive/runtime migration gates are restricted to `ledgix-erpnext.local`.
- Legacy records remain preserved until Phase 12 freeze/retirement cleanup.
- Phase 6 B2B paths create no parallel Ledgix financial ledgers.
- Phase 7 buying/inventory paths create no parallel Ledgix purchase/stock ledgers.
- Phase 8 POS paths create no parallel Ledgix sale/payment/shift/hold/stock ledgers.
- Phase 9 FBR writes only compliance metadata/logs over native ERPNext transaction authority.
- Phase 10 BI/report/print paths are read-only over native ERPNext data and do not recreate duplicate business ledgers.
- Customer AR and Supplier AP mismatches fail closed.
- Production FBR ambiguous outcomes fail closed pending external reconciliation.
