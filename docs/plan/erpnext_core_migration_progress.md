# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Migration closed:** 2026-09-16  
**Implementation branch:** `main`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`  
**Final guarded migration gate HEAD:** `d813d26d16a11665522da98c7bd542a7cc09c53f`

## Overall status

**ERPNext Core Migration Phases 0–13 are COMPLETE.**

The final Phase 13 gate returned:

- `phase13_complete=true`;
- `migration_complete=true`;
- `failed_cases=[]`;
- `passed=true`.

The project is no longer in an ERPNext migration phase. The active post-migration workstream is:

**Client Acceptance + Production Provisioning + Release Hardening**

Plan: `docs/plan/client_acceptance_production_release_hardening.md`.

This ledger records exercised evidence against `erpnext_core_migration_plan.md`. Code existence alone never closed a phase; guarded runtime evidence was required where a phase had an integration gate.

---

## Phase 0 — Baseline / Safety — COMPLETE

Repository architecture audit, rollback baseline/tag, repository/dependency/secret validation, runtime bench/site/database exclusions and pinned framework baseline are complete.

A real client release still requires its own fresh backup, exact release/version capture and production rollback checkpoint.

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

---

## Phase 7 — Buying and Inventory Cutover — COMPLETE

**Final gate HEAD:** `6fbfc95063becd57d051476df37219fab43ae704`

Evidence:

- Supplier AP preflight reconciled;
- **11/11** runtime cases passed;
- PO -> PR -> PI -> Payment Entry and direct stock Purchase Invoice proven;
- Stock Entry/Reconciliation, valuation, Batch/Serial and purchase return proven;
- native Bin/SLE authority matched expected quantities;
- no parallel Ledgix Purchase/Stock Movement/Lot/Serial writes.

Canonical service: `ledgix_saas.services.erpnext_buying_inventory`.

---

## Phase 8 — POS Engine Migration — COMPLETE

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

---

## Phase 9 — FBR Source Cutover — COMPLETE

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

---

## Phase 10 — BI, Reports and Print Migration — COMPLETE

**Final gate HEAD:** `d9b37d7f84219b8ef278ca12b9fa294d538293f4`

Evidence:

- fail-closed static suite passed **61/61**;
- **7/7** runtime cases passed;
- native A4 Sales Invoice / Credit Note rendering;
- native thermal POS Invoice rendering;
- persisted FBR invoice number and local QR rendering;
- POS compatibility returns native print targets;
- active BI/reports read ERPNext authority;
- legacy business counts stayed unchanged;
- **zero real FBR/PRAL calls**.

Canonical reporting services: `ledgix_saas.services.erpnext_reporting` + `erpnext_reporting_compat`.

---

## Phase 11 — Workspace and Product Simplification — COMPLETE

**Final gate HEAD:** `23915a81214a9717c7183cbc90a89a33cba4fd2e`

Evidence:

- static suite passed **70/70**;
- **5/5** runtime cases passed;
- Ledgix Workspace uses ERPNext native Forms/Lists for operational work;
- Cashier/Manager/Admin navigation is role-aware and Business Profile-aware;
- all five Business Profiles exercised;
- System Manager retains the full ERPNext/Frappe tree;
- legacy operational DocTypes are absent from active workspace navigation;
- product flags curate navigation only and do not grant permissions.

Canonical product-shell policy: `ledgix_saas.api.product_shell`.

---

## Phase 12 — Legacy Freeze, Reconciliation and Retirement — COMPLETE

**Final gate HEAD:** `87a20272b92a8e311959c35d3dd9aa79e081821b`

Final gate returned `phase12_complete=true` and `phase13_ready=true`.

Evidence:

- Phase 6–12 fail-closed static suite passed **81/81**;
- **7/7** Phase 12 runtime cases passed;
- required migrated master provenance fully reconciled;
- unresolved legacy drafts/open operations were zero;
- deterministic historical count/latest-modified/SHA-256 snapshot persisted and verified;
- System Manager/Ledgix Admin/Ledgix Manager legacy permissions reduced to audit-only read/report/export/print;
- Ledgix Cashier legacy business access removed;
- normal legacy writes blocked;
- old POS compatibility reads ERPNext `POS Invoice` authority;
- second freeze idempotent;
- no legacy rows/schema deleted.

Current ERPNext balances/stock are intentionally not forced to equal stale post-cutover legacy tables. Legacy business records are frozen historical audit only.

Canonical retirement service: `ledgix_saas.api.legacy_retirement`.

---

## Phase 13 — Client Profiles and SaaS Productization — COMPLETE

**Closed:** 2026-09-16  
**Final guarded migration gate HEAD:** `d813d26d16a11665522da98c7bd542a7cc09c53f`

Phase 13 proved one configurable Ledgix codebase for:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

### Final static evidence

- repository/local CI green;
- shell/Python/JSON/TOML validation green;
- ERPNext v15 dependency contract green;
- secret scan green;
- fail-closed Phase 6–13 static suite passed **90/90**.

### Final runtime evidence

All **6/6** cases passed:

1. `site_dependency_and_setup_surface`;
2. `five_client_profile_presets`;
3. `profile_specific_readiness_requirements`;
4. `apply_configuration_without_fork`;
5. `configuration_creates_no_business_masters`;
6. `integration_site_state_restored`.

The runtime gate proved:

- all five presets evaluate from the same codebase;
- profile-specific native ERPNext requirements are enforced;
- Invoice + FBR Only does not require POS configuration;
- POS-enabled profiles require valid ERPNext POS configuration;
- explicit invalid Selling Price List/Warehouse/POS Profile selections fail closed;
- one real Mixed configuration apply persisted setup audit metadata;
- Product Shell behavior matched the applied preset and role;
- setup created **zero** ERPNext business masters;
- ERPNext master counts remained unchanged before/after apply and restore;
- Phase 12 frozen historical snapshot still matched;
- Phase 12 remained frozen;
- original integration-site Business Profile/setup state was restored without error.

Final machine verdict:

- `phase13_complete=true`;
- `migration_complete=true`;
- `failed_cases=[]`;
- `passed=true`.

Canonical setup service: `ledgix_saas.api.client_setup`.

Design: `docs/plan/erpnext_phase13_client_profiles_saas.md`.

---

## Migration closure

There is **no Phase 14**.

The ERPNext Core Migration architecture and guarded integration workflow are complete. Remaining work is operational/release work over the completed architecture:

- clean fresh-client provisioning;
- production installation/update hardening;
- backup + restoration-tested rollback;
- multi-site SaaS deployment operations;
- client onboarding/readiness records;
- Business Profile selection;
- FBR Sandbox -> Production activation;
- roles/users;
- printing and POS devices/scanners;
- accounting/warehouse prerequisites;
- profile-specific smoke/UAT;
- consolidated production release gate.

Active plan: `docs/plan/client_acceptance_production_release_hardening.md`.

Production lifecycle: `docs/production/client_lifecycle.md`.

---

## Safety status at migration closure

- development remains direct on `main`; no PR migration branch is used;
- ERPNext core is never modified or vendored;
- Phase 6 B2B paths create no parallel Ledgix financial ledgers;
- Phase 7 buying/inventory paths create no parallel Ledgix purchase/stock ledgers;
- Phase 8 POS paths create no parallel Ledgix sale/payment/shift/hold/stock ledgers;
- Phase 9 FBR writes compliance metadata/logs over native ERPNext transaction authority;
- Phase 10 BI/report/print paths read ERPNext authority;
- Phase 11 product flags curate navigation only; permissions remain authoritative;
- Phase 12 legacy business data remains frozen historical audit with an immutable digest and controlled rollback release;
- Phase 13 client differences are configuration/presets only and create no duplicate business engine;
- physical legacy deletion remains deferred until a separately approved destructive migration after observation, backup and rollback planning.
