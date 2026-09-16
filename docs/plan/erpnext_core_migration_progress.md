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

The final Phase 2 regression gate passed on `ledgix-erpnext.local` and remains part of each later consolidated gate.

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
- native tax primitives exist, with FBR-specific semantics reserved for the Ledgix compliance layer.

### Phase 2 decisions

- standard masters/pricing/payments/AR/AP/buying/stock/serial/batch: **USE NATIVE**;
- invoice + FBR-only clients: **USE NATIVE non-stock Item + Sales Invoice**;
- POS engine: **ERPNext authority; keep Ledgix UX wrapper for now**;
- POS hold: **Ledgix UX over native draft POS Invoice**;
- financial tax: **ERPNext authority after Phase 4 parity**;
- FBR compliance metadata/submission/reconciliation: **KEEP LEDGIX**.

No production authority cutover occurred.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — COMPLETE

The combined Phase 2 + Phase 3 gate passed on `ledgix-erpnext.local` on 2026-09-16.

### ERPNext Customer FBR extension — PASS

ERPNext `Customer` persists Ledgix-specific buyer fields for registration type, NTN/CNIC, STRN, province, FBR address and verification state/date.

### Item Tax Profile relink — PASS

`Ledgix Item Tax Profile` supports `erpnext_item -> Item` as the target authority while retaining the legacy `Ledgix Item` reference as optional migration compatibility only.

The runtime gate proved an ERPNext-Item-only profile without requiring a legacy item.

### ERPNext sales/FBR envelope — PASS

`Sales Invoice` and `POS Invoice` contain server-managed Ledgix fields for FBR status/reference/result/reconciliation state, client-sale identifier and immutable header snapshot.

`Sales Invoice Item` and `POS Invoice Item` contain immutable line snapshots for FBR Item Profile, HS Code, FBR UOM, Sales Type, rate description, scenario/SRO references, tax basis, notified retail price, Sales Tax Withheld, Extra Tax, Further Tax, FED and versioned JSON.

### Business/client profiles — PASS

Site-level `Ledgix Business Profile` supports Invoice + FBR Only, Small Retail, Full Retail, B2B and Mixed modes. Feature flags curate UX only; server permissions remain authoritative.

### Role mapping / idempotency — PASS

Additive Ledgix Cashier/Manager/Admin permissions were installed on target ERPNext DocTypes without replacing native roles. Schema synchronization ran repeatedly without duplicate Custom Fields.

No old Ledgix master/transaction/tax/FBR source was retired in Phase 3.

---

## Phase 4 — Tax Parity and Accounting Foundation — COMPLETE

The mandatory runtime matrix passed **13/13** on `ledgix-erpnext.local` on 2026-09-16. `failed_cases` was empty and the gate returned `phase4_complete=true`, `phase5_ready=true`.

### Authority proven

ERPNext is proven as the single monetary/tax + GL authority for the tested Sales Invoice/Credit Note paths. Ledgix remains the legal/FBR classification and immutable-snapshot layer.

`ledgix_saas.setup.erpnext_tax_foundation`:

- never assigns a competing `grand_total`;
- resolves line FBR/tax metadata from ERPNext Item + Ledgix Item Tax Profile;
- freezes immutable snapshots;
- maps ordinary Sales Tax, Extra Tax, Further Tax and FED into ERPNext tax rows/accounts;
- keeps Sales Tax Withheld at Source separate from invoice payable/GL, matching Ledgix/FBR semantics;
- maps Third Schedule/notified retail price as legal tax basis while ERPNext owns final totals/GL;
- uses native inclusive-tax behavior where proven and fails closed for unsupported combinations.

### Mandatory matrix — PASS

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

Relevant cases proved submitted ERPNext documents, net/tax/grand totals, dedicated tax-account GL, balanced GL, immutable line snapshots, FBR tax preview and zero stock effect for non-stock fixtures.

### FBR safety

Phase 4 performed preview only:

- no FBR/PRAL network submission;
- no sandbox/production invoice submission;
- no FBR Submission Log authority cutover;
- no real FBR datasource switch;
- no legacy Ledgix tax-engine retirement.

Design contract:

- `docs/plan/erpnext_phase4_tax_parity_matrix.md`

---

## Phase 5 — Master Data Migration — IMPLEMENTED, FINAL RUNTIME GATE PENDING

### Goal

Move legacy master authority to ERPNext once, with explicit dry-run, conflict reporting, idempotent execution and reconciliation. This is not a permanent synchronization layer.

### Extension schema implemented

`ledgix_saas.setup.erpnext_phase5_extensions` adds only Ledgix-only metadata/provenance that pinned ERPNext v15 does not model natively:

- Item legacy source, SKU and minimum-stock compatibility value;
- Item Group legacy source, active/icon/color and category FBR-default metadata;
- Price List legacy source/default-retail/priority/notes;
- Customer/Supplier provenance;
- Address/Contact provenance;
- Mode of Payment legacy POS policy (`requires_reference`, `allow_change`, sort order, legacy method type).

Schema installation is idempotent through `after_migrate`. **Business data migration is not an after-migrate hook.**

### Explicit migration engine implemented

Canonical entry point:

- `ledgix_saas.migration.erpnext_phase5_master_migration_v2.run`

Production-safe defaults:

- `dry_run=1`;
- `migrate_opening_stock=0`.

Implemented migration order:

1. UOMs;
2. categories -> ERPNext Item Groups;
3. Price Lists;
4. Items + barcode/tracking/provenance;
5. active Item Prices with validity and deterministic legacy reference;
6. Customers + native group/type/default price list/payment terms/company credit limit + Contact/Address + FBR fields;
7. Suppliers + native group + Contact/Address;
8. Modes of Payment + Ledgix POS policy metadata;
9. legacy Item Tax Profile relink to ERPNext Item;
10. opt-in opening stock / Batch / Serial state.

### Conflict / accounting policy

Migration reports and refuses ambiguous collisions rather than silently overwriting incompatible native masters.

Customer receivable/credit state and Supplier AP/opening balances are explicitly deferred to Phase 6 because they are transactional accounting state, not master fields.

### Opening stock implementation

Opening stock requires an explicit enabled leaf ERPNext Warehouse.

- Normal: native Material Receipt;
- Lot Based: exact surviving legacy lot name -> ERPNext Batch + receipt;
- Serial Based: exact in-stock legacy serial numbers -> ERPNext Serial No / Serial & Batch Bundle;
- target stock activity unrelated to Phase 5 markers blocks migration;
- reruns reuse marker documents and must reconcile final Bin quantity.

### Final integration gate ready

Runner:

- `scripts/run_erpnext_phase5_final_gate.sh`

The gate uses isolated `P5-*` legacy fixtures and proves:

- Phase 2 regression remains green;
- Phase 3 regression remains green;
- Phase 4 13-case tax/accounting regression remains green;
- dry-run executes then rolls back target business data;
- first actual scoped migration;
- second actual scoped migration without duplicate target counts;
- legacy source counts remain unchanged;
- identifiers/UOM/category/SKU/barcode/tracking metadata;
- explicit Item Prices;
- Customer pricing/terms/credit/contact/address/FBR fields;
- Supplier group/contact/address with AP opening balance deferred;
- Mode of Payment policy;
- FBR Item Profile relink;
- exact normal/batch/serial quantities and identities;
- no legacy master freeze and no transaction-authority cutover.

Phase 5 is **not** marked complete until this runtime gate passes on `ledgix-erpnext.local`.

Design contract:

- `docs/plan/erpnext_phase5_master_migration.md`

---

## Next after Phase 5

Phase 6 — Selling, Payments and Returns Cutover.

Phase 6 will move transactional sales/payment/return authority and will absorb the customer/supplier accounting state intentionally deferred by Phase 5. FBR submission cutover remains Phase 9.

---

## Safety Status

- No staging/production authority has been cut over.
- Existing Ledgix masters, transactions, tax engine and FBR source remain available while replacement paths are proven.
- Integration gates are hard-guarded to `ledgix-erpnext.local` where they create controlled fixtures.
- No FBR network submission is performed by migration gates.
- Phase 5 migration defaults to dry-run and does not migrate opening stock unless explicitly requested.
- No legacy master is deleted or frozen by Phase 5 code.
