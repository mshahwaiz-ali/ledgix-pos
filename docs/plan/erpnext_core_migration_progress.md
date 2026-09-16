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

Evidence:

- fail-closed static suite passed **61/61**;
- **7/7** runtime cases passed;
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

Evidence:

- static suite passed **70/70**;
- **5/5** runtime cases passed;
- Ledgix Workspace uses ERPNext native Forms/Lists for operational work;
- differentiated product pages were limited to Ledgix-specific UX;
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

## Phase 12 — Legacy Freeze, Reconciliation and Retirement — COMPLETE

**Closed:** 2026-09-16  
**Final gate HEAD:** `87a20272b92a8e311959c35d3dd9aa79e081821b`

The guarded final gate passed with `phase12_complete=true` and `phase13_ready=true`.

Evidence:

- Phase 6–12 fail-closed static suite passed **81/81**;
- **7/7** Phase 12 runtime cases passed;
- migrated Item, Category, Customer, Supplier, Price List, enabled Item Price and Payment Method provenance fully reconciled;
- unresolved legacy Sale/Purchase/Return/Payment/Stock drafts were zero;
- open legacy POS Shifts/Holds were zero;
- deterministic historical count/latest-modified/SHA-256 snapshot was persisted and verified stable;
- freeze identity persisted the exact gate commit;
- System Manager/Ledgix Admin/Ledgix Manager legacy permissions are read/report/export/print only;
- Ledgix Cashier legacy business access is removed;
- normal legacy write path is blocked while an explicit controlled bypass exists for rollback tooling;
- old POS compatibility reads ERPNext `POS Invoice` authority;
- second freeze is idempotent;
- legacy row counts remained unchanged;
- no legacy schema or business rows were deleted.

Current ERPNext balances/stock are intentionally not forced to equal stale post-cutover legacy tables. Phases 6–11 proved authority at their cutover boundaries; Phase 12 proves provenance, no unresolved operations and historical immutability from the freeze point forward.

Canonical retirement service: `ledgix_saas.api.legacy_retirement`.

Design: `docs/plan/erpnext_phase12_legacy_freeze_retirement.md`.

---

## Phase 13 — Client Profiles and SaaS Productization — IMPLEMENTED, FINAL GATE PENDING

Phase 13 turns the completed ERPNext-backed Ledgix system into one configurable codebase for different client complexity levels.

### Implemented provisioning boundary

- five supported presets remain canonical: Invoice + FBR Only, Small Retail, Full Retail, B2B and Mixed;
- new Admin/System Manager Desk page: `/app/ledgix-setup`;
- server-side provisioning/readiness service: `ledgix_saas.api.client_setup`;
- readiness checks existing ERPNext Company, Selling Price List, Warehouse and POS Profile requirements according to the selected preset;
- POS-enabled profiles require an enabled POS Profile with Customer, Warehouse, Selling Price List and at least one payment mode;
- FBR Settings installation is required while live token/seller activation remains a separate explicit compliance step;
- wizard applies product preset and optional safe site defaults only;
- wizard creates no Item/Customer/Supplier/accounting/stock/sales/purchase business masters or ledgers;
- Business Profile records setup version/completion/company/user/time/snapshot audit metadata only;
- Setup Wizard is surfaced under Administration for Ledgix Admin/System Manager only;
- generic client-site preflight enforces installed Frappe + ERPNext + Ledgix and Frappe/ERPNext major version 15;
- production/client lifecycle documentation covers site creation, backup, upgrade, profile onboarding and acceptance.

### Final gate

Runner:

- `scripts/run_erpnext_phase13_final_gate.sh`

The runtime gate is designed to prove:

- site dependency surface is correct;
- all five presets evaluate on one codebase;
- Invoice-only does not acquire POS requirements;
- POS-enabled profiles fail closed without a valid POS Profile;
- one real preset application persists setup audit metadata;
- Product Shell reflects the applied preset;
- no ERPNext business-master counts change;
- Phase 12 frozen snapshot remains unchanged;
- the integration-site Business Profile is restored after testing.

Required result:

- `phase13_complete=true`;
- `migration_complete=true`;
- no failed cases;
- stable Phase 12 digest;
- unchanged ERPNext business-master counts.

Design: `docs/plan/erpnext_phase13_client_profiles_saas.md`.

Operations: `docs/production/client_lifecycle.md`.

---

## After Phase 13

The ERPNext Core Migration has no additional architecture phase after Phase 13.

Once the final Phase 13 gate is green, remaining work is:

- client acceptance;
- production provisioning;
- release hardening/monitoring;
- real FBR Sandbox/Production rollout under client credentials;
- later separately-approved physical removal of historical legacy schema only after observation, backup and rollback planning.

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
- Phase 12 legacy business data is frozen historical audit with an immutable digest and controlled rollback release.
- Phase 13 client differences are configuration/presets only and do not create another business engine.
- Physical legacy deletion remains deferred until a separately-approved destructive migration after observation, backup and rollback planning.
