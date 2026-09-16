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

Evidence:

- customer receivables preflight reconciled;
- **17/17** transaction cases green;
- native Sales Invoice / Payment Entry / Credit Note authority;
- checkout/payment idempotency and interrupted-payment recovery;
- full/partial payments, refunds, exchanges and exact source-rate returns;
- no parallel Ledgix Sale/Payment/Sales Return financial writes;
- fail-closed static contract passed **14/14**.

Canonical service: `ledgix_saas.services.erpnext_selling`.

Design: `docs/plan/erpnext_phase6_selling_cutover.md`.

---

## Phase 7 — Buying and Inventory Cutover — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `6fbfc95063becd57d051476df37219fab43ae704`

Evidence:

- Supplier AP preflight reconciled;
- **11/11** runtime cases passed;
- PO -> PR -> PI -> Payment Entry and direct stock Purchase Invoice proven;
- Stock Entry/Reconciliation, valuation, Batch/Serial and purchase return proven;
- native Bin/SLE authority matched expected quantities;
- no parallel Ledgix Purchase/Stock Movement/Lot/Serial writes.

Canonical service: `ledgix_saas.services.erpnext_buying_inventory`.

Design: `docs/plan/erpnext_phase7_buying_inventory_cutover.md`.

---

## Phase 8 — POS Engine Migration — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `c89587a04a7d4fa552d4af06fe71097ff39ffee7`

Architecture decision: retain the Ledgix POS screen while ERPNext POS owns the engine.

Evidence:

- **36/36** Phase 6+7+8 static contracts green;
- **7/7** runtime cases green;
- native POS boot/profile/payments/opening/closing;
- native draft holds;
- split tender/change/idempotency;
- native POS return with source-rate authority;
- no parallel legacy POS writes.

Canonical service: `ledgix_saas.services.erpnext_pos`.

Compatibility layer: `ledgix_saas.api.pos_compat`.

Design: `docs/plan/erpnext_phase8_pos_cutover.md`.

---

## Phase 9 — FBR Source Cutover — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `a441823ee23d075897fdbd30ee72ac265745f2e8`

Evidence:

- **48/48** Phase 6+7+8+9 static contracts green;
- **9/9** runtime cases green;
- Sales Invoice/POS Invoice payloads from immutable native snapshots;
- native FBR validation/submission logs and official reference/QR persistence;
- native Credit Note original-FBR reference;
- ambiguous Production POST reconciliation lock;
- consolidated POS accounting Sales Invoice excluded as second FBR source;
- legacy Ledgix Sale Production submit retired;
- **zero real FBR/PRAL network calls** in the migration gate.

Canonical adapter: `ledgix_saas.api.fbr_native`.

Design: `docs/plan/erpnext_phase9_fbr_cutover.md`.

---

## Phase 10 — BI, Reports and Print Migration — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `d9b37d7f84219b8ef278ca12b9fa294d538293f4`

The guarded final gate passed with `phase10_complete=true` and `phase11_ready=true`.

Evidence:

- fail-closed static suite passed **61/61**;
- **7/7** Phase 10 runtime cases passed;
- native A4 Sales Invoice / Credit Note rendering;
- native thermal POS Invoice rendering;
- persisted FBR invoice number and local QR rendering;
- POS compatibility returns native print targets;
- Current Stock, Low Stock, Stock Movement, Sales, Returns, Purchases and Customer Statement read ERPNext authority;
- Inventory Intelligence reads Item/Bin/SLE/native sales/purchase/Batch/Serial sources;
- legacy business counts stayed unchanged;
- **zero real FBR/PRAL calls**.

Canonical reporting services: `ledgix_saas.services.erpnext_reporting` + `erpnext_reporting_compat`.

Native print context: `ledgix_saas.api.printing.get_native_invoice_print_context`.

Design: `docs/plan/erpnext_phase10_bi_reports_print.md`.

---

## Phase 11 — Workspace and Product Simplification — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `23915a81214a9717c7183cbc90a89a33cba4fd2e`

The guarded final gate passed with `phase11_complete=true` and `phase12_ready=true`.

Evidence:

- static suite passed **70/70**;
- **5/5** Phase 11 runtime cases passed;
- Ledgix Workspace uses ERPNext native Forms/Lists for operational work;
- only Ledgix POS, Tax & FBR Center and Inventory Intelligence remain differentiated product pages;
- Cashier/Manager/Admin navigation is role-aware and Business Profile-aware;
- all five Business Profiles were exercised;
- Cashier lands on POS only when POS is enabled;
- System Manager retains the full ERPNext/Frappe tree;
- legacy operational DocTypes are absent from active workspace navigation;
- product flags remain navigation-only and do not grant permissions;
- legacy business counts, Custom DocPerm count and Business Profile values remained unchanged by the shell gate.

Canonical product-shell policy: `ledgix_saas.api.product_shell`.

Design: `docs/plan/erpnext_phase11_workspace_product_simplification.md`.

---

## Phase 12 — Legacy Freeze, Reconciliation and Retirement — IMPLEMENTED, FINAL GATE PENDING

Phase 12 intentionally freezes rather than deletes historical duplicate business records.

### Implemented retirement boundary

- Single retirement state: `Ledgix Legacy Retirement State`;
- deterministic per-DocType count/latest-modified/SHA-256 snapshot;
- provenance reconciliation for migrated Items, Categories, Customers, Suppliers, Price Lists, enabled Item Prices and Payment Methods;
- fail-closed blockers for unresolved legacy drafts/open POS Shifts/Holds;
- explicit freeze confirmation before write protection activates;
- document-event guard blocks legacy insert/save/submit/cancel/delete after freeze;
- System Manager/Admin/Manager legacy permissions become read/report/export/print only;
- Cashier legacy business access is removed;
- future migrate reapplies read-only policy if the retirement state is already Frozen;
- controlled rollback release requires an exact confirmation phrase;
- no legacy schema or business rows are deleted by Phase 12;
- old POS compatibility method names now operate over ERPNext-native Item/POS/Serial/print services;
- old Business Intelligence RPC is forced to the Phase 10 ERPNext-native adapter.

### Reconciliation policy

Current ERPNext balances/stock are **not** forced to equal stale legacy post-cutover tables. Phases 6–11 already proved authority at their cutover boundaries, and ERPNext continued moving afterward while legacy ledgers stopped.

Phase 12 therefore gates on:

- complete one-time master provenance;
- zero unresolved legacy operations;
- immutable historical snapshot from the freeze point forward.

Final runner:

- `scripts/run_erpnext_phase12_final_gate.sh`

Required result:

- `phase12_complete=true`;
- `phase13_ready=true`;
- no failed cases;
- `legacy_snapshot_matches=true`;
- unchanged legacy row counts.

Design: `docs/plan/erpnext_phase12_legacy_freeze_retirement.md`.

---

## Next after Phase 12

**Phase 13 — Client Profiles and SaaS Productization**.

Phase 13 will turn the already-existing Business Profile model into the final provisioning/onboarding/deployment product workflow without creating separate code forks or another business engine.

---

## Safety Status

- Development is direct on `main`; no PR branch is used.
- ERPNext core is never modified or vendored.
- Runtime migration gates are restricted to `ledgix-erpnext.local`.
- Phase 6 B2B paths create no parallel Ledgix financial ledgers.
- Phase 7 buying/inventory paths create no parallel Ledgix purchase/stock ledgers.
- Phase 8 POS paths create no parallel Ledgix sale/payment/shift/hold/stock ledgers.
- Phase 9 FBR writes only compliance metadata/logs over native ERPNext transaction authority.
- Phase 10 BI/report/print paths read ERPNext authority only.
- Phase 11 product flags curate navigation only; permissions remain authoritative.
- Phase 12 preserves legacy rows and schema, freezes them only after reconciliation, and keeps an explicit controlled rollback path.
- Physical legacy deletion remains deferred until a later destructive migration after observation, backup and rollback planning.
