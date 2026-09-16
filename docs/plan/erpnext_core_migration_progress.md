# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `main`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This ledger records exercised evidence against `erpnext_core_migration_plan.md`. Code existence alone never closes a phase; guarded runtime evidence is required where a phase has an integration gate.

---

## Phase 0 — Baseline / Safety — COMPLETE FOR MIGRATION DEVELOPMENT

Completed:

- repository architecture audit and ERPNext-core migration plan;
- rollback baseline/tag;
- local repository validation, dependency validation and secret scan;
- runtime bench/sites/databases/secrets excluded from Git;
- tested Frappe/ERPNext baseline tracked in `config/framework.lock`.

Still mandatory before a real client cutover: fresh backup, exact version capture and a cutover rollback checkpoint.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site — COMPLETE

Proven integration baseline:

- Frappe `15.113.4` (`version-15`);
- ERPNext `15.121.3` (`version-15`);
- Ledgix `0.0.1`;
- site `ledgix-erpnext.local`;
- Company `Ledgix ERPNext Integration` / PKR / Pakistan.

Ledgix declares ERPNext as a required app. Fresh-site migrate/build/list-apps/bootstrap checks passed.

---

## Phase 2 — Native ERPNext Capability / Gap Matrix — COMPLETE

Runtime evidence proves native ERPNext paths for:

- Item / Item Group / UOM / Customer / Supplier / Contact / Address;
- Price List / Item Price / Pricing Rule;
- Sales Invoice, Payment Entry and native Credit Note;
- Purchase Order / Receipt / Invoice and supplier payment;
- Stock Entry / Stock Reconciliation / Stock Ledger;
- Batch / Serial No / Serial and Batch Bundle;
- POS Profile / Opening / POS Invoice / split tender / Closing / consolidation;
- unfinished draft POS Invoice;
- native print rendering.

Decisions:

- standard masters, pricing, AR/AP, payments, buying and inventory: **ERPNext native**;
- invoice + FBR-only client: **non-stock ERPNext Item + Sales Invoice**;
- POS UI remains Ledgix UX over native engine until the dedicated POS cutover phase;
- FBR legal metadata/submission stays Ledgix-specific.

No production authority was cut over in Phase 2.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — COMPLETE

Runtime gate proves:

- ERPNext Customer carries Ledgix-only buyer/FBR identity fields;
- `Ledgix Item Tax Profile.erpnext_item` targets native `Item` while the legacy item link is optional migration compatibility;
- Sales Invoice/POS Invoice carry Ledgix FBR envelope fields;
- Sales Invoice Item/POS Invoice Item carry immutable FBR/legal line snapshots;
- Business Profiles cover Invoice + FBR Only, Small Retail, Full Retail, B2B and Mixed;
- Ledgix Cashier/Manager/Admin permissions are additive over native ERPNext DocTypes;
- repeated schema synchronization does not create duplicate Custom Fields.

No legacy master/transaction source was retired.

---

## Phase 4 — Tax Parity and Accounting Foundation — COMPLETE

Mandatory tax/accounting runtime matrix passed **13/13** on `ledgix-erpnext.local`.

Proven cases:

1. ordinary taxable;
2. tax-inclusive price;
3. zero-rated;
4. exempt;
5. Third Schedule / notified retail price;
6. Further Tax;
7. Extra Tax;
8. FED;
9. Sales Tax Withheld at Source;
10. mixed invoice;
11. full return;
12. partial return;
13. non-stock financial/price adjustment Credit Note.

Authority contract:

- ERPNext owns monetary totals, invoice tax rows and GL;
- Ledgix owns FBR/legal classification and immutable snapshots;
- Sales Tax Withheld at Source remains separate from invoice payable under the proven current semantics;
- no FBR/PRAL network request or production datasource cutover occurred.

Design: `docs/plan/erpnext_phase4_tax_parity_matrix.md`.

---

## Phase 5 — Master Data Migration — COMPLETE

The consolidated Phase 2 + 3 + 4 + 5 gate passed on `main` / `ledgix-erpnext.local` on 2026-09-16.

### Final runtime evidence

Every mandatory Phase 5 check passed:

- dry-run executed and rolled back;
- dry-run target counts stayed unchanged;
- first real scoped migration passed;
- second real run proved idempotence;
- target counts stayed stable;
- no conflicts on first or second run;
- legacy source records were not deleted;
- Category -> Item Group identity/metadata preserved;
- normal/batch/serial Items mapped correctly;
- explicit Item Prices mapped through dedicated Ledgix migration provenance while ERPNext `reference` remains native;
- Customer price list/payment terms/credit limit/contact/address/FBR data mapped;
- Supplier group/contact/address mapped;
- Supplier AP/opening amount explicitly deferred to Phase 7;
- Mode of Payment Ledgix policy metadata preserved;
- all legacy Item Tax Profiles relinked to native Item;
- normal opening quantity exact;
- lot identity preserved as ERPNext Batch;
- serial identities preserved exactly;
- Invoice + FBR Only profile creates non-stock native Items and no Stock Ledger Entry;
- stock-enabled profile creates native inventory state;
- legacy master freeze was not performed;
- transaction authority cutover was not performed.

### Naming / schema discipline

- active migration modules use descriptive names rather than `_v2/_v3` suffixes;
- repository validation rejects future migration `_vN` names/references;
- Frappe DocType folder/JSON naming is validated;
- target business masters use standard ERPNext DocType names rather than parallel Ledgix replacements.

Canonical service: `ledgix_saas.migration.erpnext_phase5_master_migration_runtime.run`.

Design: `docs/plan/erpnext_phase5_master_migration.md`.

---

## Phase 6 — Selling, Payments and Returns Cutover — IMPLEMENTED, FINAL RUNTIME GATE PENDING

### Scope decision

Phase 6 moves the **new B2B/invoice path** to ERPNext financial authority.

Retail POS backend is intentionally not switched here; that remains Phase 8. FBR network submission/source cutover remains Phase 9.

### Native selling service implemented

Canonical service:

- `ledgix_saas.services.erpnext_selling`

Implemented capabilities:

- resolve migrated ERPNext Customer / Item / Price List / Mode of Payment identities;
- use native ERPNext selling prices/pricing rules;
- create Sales Invoice with Ledgix sale channel/client-id context;
- apply the proven Phase 4 FBR/tax snapshot adapter;
- checkout client-sale idempotency under a Company transaction lock;
- post one Payment Entry against one or multiple Sales Invoices;
- payment client-id idempotency;
- native Payment Entry cancellation with preserved Ledgix reason;
- native Credit Note/return using ERPNext's return mapper and `Sales Invoice Item.sales_invoice_item` source-row link;
- customer refund through native Payment Entry type `Pay` with negative Credit Note allocation;
- exchange as Credit Note + replacement Sales Invoice;
- customer receivable/credit view from submitted ERPNext Sales Invoice + Payment Entry state.

No custom monetary total, payment balance or second receivables ledger was introduced.

### Phase 6 extension schema

Only routing/idempotency metadata was added to standard native documents.

Sales Invoice:

- sale channel;
- client return ID;
- exchange reference;
- checkout source.

Payment Entry:

- client payment ID;
- payment source;
- cancellation/reversal reason.

Existing Phase 3 `custom_ledgix_client_sale_id` remains the sale idempotency field.

### Compatibility routing

Current Ledgix RPC/UI paths stay stable through Frappe method overrides:

- B2B preview/checkout -> ERPNext selling adapter;
- B2B customer credit/open invoices -> ERPNext receivables;
- native invoice returns -> ERPNext Credit Notes;
- Retail requests -> existing retail backend until Phase 8.

`api/v2_b2b.py` is now a compatibility wrapper; it no longer owns Ledgix Sale/Payment writes.

### Phase 6 final gate implemented

Runner:

- `scripts/run_erpnext_phase6_final_gate.sh`

It performs:

1. local CI/schema/naming/dependency/secret checks;
2. migrate Phase 6 fields;
3. Phase 6 static contract test;
4. Phase 2 regression;
5. Phase 3 regression;
6. Phase 4 13-case tax/accounting regression;
7. Phase 5 master migration/reconciliation regression;
8. Phase 6 native selling/payment/return matrix.

Phase 6 matrix covers:

- client-sale idempotency;
- fully paid;
- partially paid;
- unpaid credit sale/native AR;
- one payment across multiple invoices;
- payment idempotency;
- payment cancellation/outstanding restoration;
- full Credit Note;
- partial Credit Note;
- refund;
- exchange;
- B2B compatibility API;
- native receivables;
- no stock effect for non-stock fixtures;
- immutable FBR snapshot;
- no parallel Ledgix financial documents;
- explicit retail-POS deferral.

Phase 6 is **not complete** until this runner is green on `ledgix-erpnext.local`.

Design: `docs/plan/erpnext_phase6_selling_cutover.md`.

---

## Next after Phase 6

Phase 7 — Buying and Inventory Cutover.

Phase 7 will move Purchase Order/Receipt/Invoice, supplier Payment Entry, Stock Entry/Reconciliation and supplier opening/AP state to the final native cutover path.

---

## Safety Status

- Active development is now directly on `main`; no migration PR flow is required.
- No production/client authority has been cut over by these integration gates.
- Legacy masters remain available until later freeze/retirement phases.
- New Phase 6 B2B financial code does not create Ledgix Sale/Payment documents.
- Retail POS financial backend is still intentionally deferred to Phase 8.
- FBR network submission/source cutover is still intentionally deferred to Phase 9.
- Supplier AP/opening state remains deferred to Phase 7.
