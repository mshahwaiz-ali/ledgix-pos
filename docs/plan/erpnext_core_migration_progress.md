# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `main`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This ledger records exercised evidence against `erpnext_core_migration_plan.md`. Code existence alone never closes a phase; guarded runtime evidence is required where a phase has an integration gate.

---

## Phase 0 — Baseline / Safety — COMPLETE FOR MIGRATION DEVELOPMENT

Completed: repository architecture audit, rollback baseline/tag, repository/dependency/secret validation, runtime bench/site/database exclusions, and pinned framework baseline.

Still mandatory before a real client cutover: fresh backup, exact version capture and a cutover rollback checkpoint.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site — COMPLETE

Proven baseline:

- Frappe `15.113.4` / `version-15`;
- ERPNext `15.121.3` / `version-15`;
- Ledgix `0.0.1`;
- site `ledgix-erpnext.local`;
- Company `Ledgix ERPNext Integration` / PKR / Pakistan.

Ledgix declares ERPNext as required. Fresh-site migrate/build/list-apps/bootstrap checks passed.

---

## Phase 2 — Native ERPNext Capability / Gap Matrix — COMPLETE

Runtime evidence proved native ERPNext paths for masters, pricing, Sales Invoice/Payment Entry/Credit Note, purchase documents, Stock Entry/Reconciliation/Ledger, Batch/Serial, POS opening/invoice/split tender/closing, unfinished POS draft and native print.

Decision: standard masters, pricing, financials, buying and inventory use ERPNext authority; Ledgix keeps product UX and FBR/compliance concerns.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — COMPLETE

Runtime gate proved ERPNext Customer FBR extensions, Item-linked Ledgix legal/tax profiles, Sales/POS Invoice FBR envelope fields, immutable line snapshots, business profiles, additive Ledgix permissions and idempotent schema synchronization.

---

## Phase 4 — Tax Parity and Accounting Foundation — COMPLETE

Mandatory tax/accounting matrix passed **13/13** on `ledgix-erpnext.local`: ordinary, inclusive, zero-rated, exempt, Third Schedule, Further Tax, Extra Tax, FED, Sales Tax Withheld at Source, mixed invoice, full return, partial return and price-only Credit Note.

ERPNext owns monetary totals/tax rows/GL; Ledgix owns legal/FBR classification and immutable snapshots.

Design: `docs/plan/erpnext_phase4_tax_parity_matrix.md`.

---

## Phase 5 — Master Data Migration — COMPLETE

The consolidated Phase 2+3+4+5 gate passed on 2026-09-16.

Proven:

- dry-run rollback and stable target counts;
- real migration and rerun idempotence;
- Item Group/Item/Item Price/Customer/Supplier/Mode of Payment mappings;
- contacts/addresses/FBR metadata;
- opening stock;
- Batch/Serial identity preservation;
- invoice-only profile creates non-stock Items and no SLE;
- source legacy records are not deleted;
- supplier AP/current liability intentionally deferred to Phase 7.

Canonical service: `ledgix_saas.migration.erpnext_phase5_master_migration_runtime.run`.

Design: `docs/plan/erpnext_phase5_master_migration.md`.

---

## Phase 6 — Selling, Payments and Returns Cutover — COMPLETE

**Closed:** 2026-09-16  
**Final static-proof HEAD:** `3df4634dc4dc05d13231ead7427af353a799a71d`

Phase 6 moved the new B2B/invoice financial path to ERPNext while intentionally leaving retail POS backend to Phase 8 and FBR submission datasource/network cutover to Phase 9.

### Final evidence

Full guarded closure on `ledgix-erpnext.local` proved:

- Phase 2–5 regression gates green;
- customer receivables preflight reconciled;
- **17/17** Phase 6 transaction cases passed;
- full/partial payments and native AR;
- multi-invoice Payment Entry allocation;
- Payment Entry idempotency/cancellation/outstanding restoration;
- full/partial Credit Note, refund and exchange;
- B2B compatibility APIs use ERPNext authority;
- non-stock Phase 6 fixtures create no SLE;
- immutable FBR snapshots remain attached;
- no parallel `Ledgix Sale` / `Ledgix Payment` / `Ledgix Sales Return` financial writes;
- pricing/payment policy proof green: checkout discount, authorized rate-override audit, interrupted payment recovery and required payment references;
- malicious client-supplied return rate `1.23` could not override the original ERPNext invoice rate `1000.00`;
- final fail-closed static contract ran **14/14 tests** and passed.

Canonical service: `ledgix_saas.services.erpnext_selling`.

Design: `docs/plan/erpnext_phase6_selling_cutover.md`.

---

## Phase 7 — Buying and Inventory Cutover — IMPLEMENTED, FINAL RUNTIME GATE PENDING

### Implemented authority boundary

Canonical service:

- `ledgix_saas.services.erpnext_buying_inventory`

Implemented native paths:

- Purchase Order -> Purchase Receipt -> Purchase Invoice -> supplier Payment Entry;
- direct Purchase Invoice with stock effect for small-shop buying;
- financial-only Purchase Invoice for non-stock items;
- Purchase Return through ERPNext return mapping;
- Material Receipt / Issue / Transfer through Stock Entry;
- quantity correction through Stock Reconciliation;
- stock availability/valuation from Bin + Stock Ledger Entry;
- Batch and Serial No / Serial and Batch Bundle authority;
- POS serial availability compatibility now reads ERPNext Serial No;
- manual stock compatibility now writes native Stock Entry instead of Ledgix Stock Movement/Lot/Serial.

### Supplier AP guard

`erpnext_phase7_supplier_ap_preflight.run` compares mapped legacy Supplier `current_balance` with ERPNext Supplier GL payable state. Legacy `opening_balance` is reported as provenance only and is never silently reposted. Any current-payable mismatch blocks cutover.

### Workspace routing

Ledgix Buying & Suppliers and Inventory & Stock cards now point normal operations to standard ERPNext Purchase Order/Receipt/Invoice, Supplier, Item/Item Group, Warehouse, Stock Entry/Reconciliation, Batch and Serial No.

Historical legacy DocTypes/reports remain available for migration/reconciliation; they are not deleted in Phase 7.

### Final gate

Runner:

- `scripts/run_erpnext_phase7_final_gate.sh`

It performs local CI, migrate, fail-closed Phase 6+7 static contracts, supplier AP preflight and the Phase 7 runtime matrix.

Runtime matrix covers:

- full purchase chain + supplier payment;
- purchase idempotency;
- direct stock purchase;
- non-stock financial-only purchase;
- material transfer;
- Stock Reconciliation;
- Batch bundle behavior;
- Serial No availability/issue;
- Purchase Return;
- stock cancellation;
- backdated SLE behavior;
- ERPNext valuation authority;
- no parallel Ledgix Purchase/Stock Movement/Lot/Serial writes.

Phase 7 closes only when the integration gate returns both `phase7_complete=true` and `phase8_ready=true`.

Design: `docs/plan/erpnext_phase7_buying_inventory_cutover.md`.

---

## Next after Phase 7

Phase 8 — POS Engine Migration. The retained Ledgix POS UX will be moved onto the already-proven ERPNext Customer/Item/Pricing/Sales/Payment/Stock authority and legacy retail financial/stock backends will be removed from the live path.

---

## Safety Status

- Development remains direct on `main`; no PR branch is used.
- ERPNext core is never modified/vendor-forked.
- No production/client authority is changed by these integration-site gates.
- Legacy records remain available until explicit later freeze/retirement phases.
- Phase 6 B2B financial paths create no parallel Ledgix financial documents.
- Phase 7 adapters are designed to create no parallel Ledgix purchase/stock/lot/serial documents.
- Customer AR and Supplier AP mismatches fail closed rather than being silently lost.
- Retail POS backend remains intentionally deferred to Phase 8.
- FBR network submission/source cutover remains intentionally deferred to Phase 9.
