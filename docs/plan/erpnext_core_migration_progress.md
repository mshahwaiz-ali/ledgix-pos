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

## Phase 5 — Master Data Migration — IMPLEMENTED, ITEM-PRICE FIX READY FOR RE-GATE

### Latest runtime evidence

The consolidated Phase 2 + 3 + 4 + 5 gate was exercised on `ledgix-erpnext.local` at commit `2cd059a2fe78` on 2026-09-16.

Regression status remained green:

- Phase 2: **PASS**;
- Phase 3: **PASS**;
- Phase 4: **PASS, 13/13**.

Phase 5 proved every mandatory master/stock/profile check except explicit Item Price reconciliation. The failed checks were limited to:

- `dry_run_passed`;
- `first_migration_passed`;
- `second_migration_passed`;
- `explicit_item_prices_mapped`.

The underlying migration had no conflicts/errors and all non-price checks were green: categories, Items, tracking, customers, contacts/addresses, FBR fields, suppliers, payment methods, Item Tax Profile relink, normal/batch/serial opening state, legacy record preservation and Invoice + FBR Only non-stock behavior.

### Item Price root cause identified and corrected

The first implementation attempted to store Ledgix migration provenance in ERPNext `Item Price.reference`.

Pinned ERPNext v15 owns that standard field: `ItemPrice.before_save()` derives `reference` from the native Customer/Supplier price semantics. For a generic selling price the migration marker is therefore cleared during save. The ERPNext Item Price records themselves were created, but the reconciliation lookup by `reference` could not find their provenance.

Corrected design:

- ERPNext `Item Price.reference` is left fully native;
- `Item Price.custom_ledgix_legacy_item_price` stores only one-time Ledgix migration provenance;
- existing matching ERPNext Item Price rows from the failed rehearsal are adopted by semantic key only when their rate matches and no other Ledgix provenance owner exists;
- a different rate or provenance owner fails closed as a conflict;
- reconciliation now checks the dedicated provenance field.

This allows the next re-gate to repair the already-created rehearsal rows without generating another explicit price row.

### Standard target ownership

Target business authority uses standard ERPNext/Frappe DocTypes:

- `Item Group`, `UOM`, `Price List`, `Item`, `Item Price`;
- `Customer`, `Contact`, `Address`, `Supplier`;
- `Mode of Payment`;
- ERPNext Stock Ledger / `Batch` / `Serial No`.

Legacy `Ledgix Item`, `Ledgix Customer`, `Ledgix Supplier`, etc. remain only as migration sources until later freeze/retirement phases. They are intentionally not renamed or deleted during Phase 5.

Ledgix-only configuration/compliance models such as `Ledgix Item Tax Profile` and `Ledgix Business Profile` remain custom because ERPNext does not replace their product/FBR purpose.

### Naming cleanup

Active migration/test helper names are descriptive rather than versioned. Examples:

- `erpnext_phase5_master_migration_runtime`;
- `erpnext_phase5_master_migration_gate_profiles`;
- `erpnext_phase5_master_migration_gate_runtime`;
- `erpnext_phase4_tax_credit_case`;
- `erpnext_phase4_tax_parity_runtime`;
- `erpnext_pos_behavioral_spike_runtime`;
- `erpnext_stock_purchase_behavioral_spike_runtime`.

Version-suffixed migration modules are removed. Repository validation now rejects future `*_vN.py` migration modules or references.

### Extension schema implemented

`ledgix_saas.setup.erpnext_phase5_extensions` adds only Ledgix-only metadata/provenance that pinned ERPNext v15 does not model natively:

- Item legacy source, SKU, legacy tracking audit and minimum-stock compatibility value;
- Item Group legacy source, active/icon/color and category FBR-default metadata;
- Price List legacy source/default-retail/priority/notes;
- Item Price migration provenance only;
- Customer/Supplier provenance;
- Address/Contact provenance;
- Mode of Payment legacy POS policy (`requires_reference`, `allow_change`, sort order, legacy method type).

Schema installation is idempotent through `after_migrate`. **Business data migration is not an after-migrate hook.**

### Explicit migration engine implemented

Canonical entry point:

- `ledgix_saas.migration.erpnext_phase5_master_migration_runtime.run`

Production-safe defaults:

- `dry_run=1`;
- `migrate_opening_stock=0`.

Implemented migration order:

1. UOMs;
2. categories -> ERPNext Item Groups;
3. Price Lists;
4. Items + barcode/tracking/provenance;
5. active Item Prices with native validity/rate/UOM and dedicated Ledgix provenance;
6. Customers + native group/type/default price list/payment terms/company credit limit + Contact/Address + FBR fields;
7. Suppliers + native group + Contact/Address;
8. Modes of Payment + Ledgix POS policy metadata;
9. legacy Item Tax Profile relink to ERPNext Item;
10. opt-in opening stock / Batch / Serial state.

### Accounting-state ownership

- Customer receivable/unallocated-credit state is deferred to **Phase 6 — Selling, Payments and Returns Cutover**.
- Supplier AP/opening balances are deferred to **Phase 7 — Buying and Inventory Cutover**.

Neither is converted into a fake master balance in Phase 5.

### Opening stock implementation

Opening stock requires an explicit enabled leaf ERPNext Warehouse and an inventory-enabled business profile.

- Normal: native Material Receipt;
- Lot Based: exact surviving legacy lot name -> ERPNext Batch + receipt;
- Serial Based: exact in-stock legacy serial numbers -> ERPNext Serial No / Serial & Batch Bundle;
- target stock activity unrelated to Phase 5 markers blocks migration;
- reruns reuse marker documents and must reconcile final Bin quantity;
- Invoice + FBR Only profile creates non-stock ERPNext Items and performs no stock-ledger posting.

### Final integration gate

Runner:

- `scripts/run_erpnext_phase5_final_gate.sh`

The next runtime gate must reconfirm:

- Phase 2/3/4 regressions;
- dry-run rollback;
- first and second idempotent migration runs;
- explicit Item Price provenance/rate mapping;
- all previously green master/profile/stock checks.

Phase 5 remains **not complete** until that corrected runtime gate passes on `ledgix-erpnext.local`.

Design contract:

- `docs/plan/erpnext_phase5_master_migration.md`

---

## Next after Phase 5

Phase 6 — Selling, Payments and Returns Cutover.

Phase 6 will move new sales/payment/return authority and customer receivable/credit state to ERPNext. Supplier AP/opening state aligns with Phase 7 buying cutover. FBR submission cutover remains Phase 9.

---

## Safety Status

- No staging/production authority has been cut over.
- Existing Ledgix masters, transactions, tax engine and FBR source remain available while replacement paths are proven.
- Integration gates are hard-guarded to `ledgix-erpnext.local` where they create controlled fixtures.
- No FBR network submission is performed by migration gates.
- Phase 5 migration defaults to dry-run and does not migrate opening stock unless explicitly requested.
- No legacy master is deleted or frozen by Phase 5 code.