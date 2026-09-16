# Phase 5 — Native ERPNext Master Data Migration

**Branch:** `erpnext-core-migration`  
**Integration site gate:** `ledgix-erpnext.local`  
**Baseline:** Frappe 15.113.4 / ERPNext 15.121.3

## Goal

Move Ledgix master authority to native ERPNext records once, with an auditable and idempotent migration. This is not a permanent synchronization layer.

Phase 5 does **not** freeze/delete legacy masters and does **not** cut transaction authority. Those decisions require later cutover phases.

## Target ownership

| Legacy Ledgix source | Target authority | Notes |
| --- | --- | --- |
| Ledgix Category | ERPNext `Item Group` | Ledgix-only visual/FBR defaults remain small custom fields on Item Group |
| Ledgix Item unit | ERPNext `UOM` / Item `stock_uom` | `Piece -> Nos`, `Liter -> Litre`; remaining source values preserve name where possible |
| Ledgix Price List | ERPNext `Price List` | Selling list; retail/default/priority/notes are Ledgix extension metadata |
| Ledgix Item | ERPNext `Item` | Native barcode, tracking flags, valuation/standard rates; provenance/SKU/minimum-stock compatibility are Ledgix fields |
| Ledgix Item Price | ERPNext `Item Price` | Native validity/rate/UOM fields; one Ledgix provenance Custom Field tracks the migration source |
| Ledgix Customer | ERPNext `Customer` | native group/type/default price list/payment terms/credit limit + Phase 3 FBR fields |
| Customer contact/address | Frappe `Contact` / `Address` | authoritative email/phone child tables + Dynamic Links |
| Ledgix Supplier | ERPNext `Supplier` | native Supplier Group/contact/address |
| Ledgix Payment Method | ERPNext `Mode of Payment` | native payment type; Ledgix POS reference/change policy retained as extension metadata |
| Ledgix Item Tax Profile | existing Ledgix FBR profile linked to ERPNext `Item` | no duplicate product master |
| Ledgix current stock | ERPNext Stock Ledger | explicit one-time opening receipts only |
| Ledgix Stock Lot | ERPNext `Batch` + stock receipt | exact surviving lot identity, remaining quantity and cost |
| Ledgix Stock Serial | ERPNext `Serial No` + Serial/Batch Bundle | exact in-stock serial identity |

## Data that intentionally does not move in Phase 5

Accounting balances are transactional state, not master attributes:

- Customer receivables, unallocated credit and customer credit balances move with **Phase 6 — Selling, Payments and Returns Cutover**.
- Supplier AP/opening balances move with **Phase 7 — Buying and Inventory Cutover**.

Phase 5 reports these rows as deferred rather than inventing fake master balances or journals.

## Extension policy

`ledgix_saas.setup.erpnext_phase5_extensions` adds only information that pinned ERPNext v15 does not own natively:

- legacy source/provenance identifiers;
- legacy SKU, tracking-type audit value and minimum-stock compatibility value;
- category active/icon/color and Ledgix FBR category-default switches;
- retail Price List priority/default/notes;
- one `Item Price.custom_ledgix_legacy_item_price` migration-provenance field;
- Ledgix POS payment method policy (`requires_reference`, `allow_change`, sort order and legacy method type).

ERPNext's standard `Item Price.reference` field is **not** used for migration provenance. In pinned ERPNext v15 the Item Price controller owns that field and derives it from Customer/Supplier semantics. Ledgix therefore leaves the native field untouched.

No duplicate Item/Customer/Supplier/Price List/Item Price business model is introduced for target authority.

Schema extensions are idempotently installed by `after_migrate`. **Business data migration is never automatically executed by migrate.**

## Migration entry point

Canonical migration service:

```text
ledgix_saas.migration.erpnext_phase5_master_migration_runtime.run
```

Safety defaults:

```text
dry_run = 1
migrate_opening_stock = 0
```

The caller must explicitly supply/select the Company. Opening stock also requires an explicit enabled leaf Warehouse.

A `source_prefix` can scope a migration rehearsal or tenant-specific batch. Ledgix Item Prices are scoped through their linked legacy Item because their document names are generated `IP-#####` values rather than item identifiers.

## Conflict policy

Migration is fail/report-first, not overwrite-first.

Examples that become reconciliation conflicts:

- an existing ERPNext Item with the same item code but incompatible group/UOM/batch/serial structure;
- a Customer/Supplier name collision without Ledgix provenance;
- a Price List currency mismatch;
- an Item Price semantic key with a different amount or a different Ledgix provenance owner;
- an Item Tax Profile already linked to a different ERPNext Item;
- target stock ledger activity that did not come from the Phase 5 opening marker;
- lot remaining quantity not matching legacy Item current stock;
- in-stock legacy serial count not matching legacy Item current stock;
- Batch/Serial identity already owned by another ERPNext Item.

The operator resolves conflicts explicitly and reruns. The migration does not silently merge ambiguous masters.

## Opening stock contract

Opening inventory uses native ERPNext stock documents and is opt-in.

### Normal item

One Material Receipt with marker:

```text
LEDGIX-P5-OPENING:<legacy-item>
```

### Lot Based item

Every non-cancelled legacy lot with positive `remaining_qty` becomes one ERPNext Batch using the exact legacy lot name. The sum of remaining lot quantities must equal the legacy Item `current_stock` before anything is posted.

### Serial Based item

Every in-stock legacy serial identity (`Available` / `Returned`) is preserved exactly. Count must equal legacy Item `current_stock`. ERPNext creates the native Serial/Batch Bundle through the proven v15 Stock Entry path.

### Invoice + FBR Only profile

When the business profile has inventory disabled, migrated ERPNext Items remain **non-stock** even if the legacy Item carried a tracking type. The legacy tracking type is preserved only as audit metadata and no opening stock/Batch/Serial posting is performed.

### Duplicate-stock guard

If the target Item/Warehouse already contains unrelated Stock Ledger Entry activity, opening stock migration refuses to post. On rerun, only Phase 5 marker documents are reused and their final Bin quantity must still match legacy current stock.

## Dry-run semantics

Dry-run uses a database savepoint and executes the same migration logic, including stock/accounting validation, then rolls back all target business-data changes. Schema Custom Fields are installed separately and are intentionally not rolled back.

The Phase 5 integration gate proves that target record counts do not change after the dry-run.

## Integration final gate

Runner:

```bash
bash scripts/run_erpnext_phase5_final_gate.sh
```

It performs:

1. repository CI and secret/dependency checks;
2. Redis readiness;
3. `bench migrate` for extension schema;
4. Phase 2 behavioral regression;
5. Phase 3 schema regression;
6. Phase 4 13-case tax/accounting regression;
7. creation/reuse of isolated `P5-*` legacy fixtures;
8. Phase 5 dry-run with rollback proof;
9. first real scoped migration;
10. second real scoped migration to prove idempotence;
11. counts/identifiers/prices/FBR/contact/credit/payment-policy reconciliation;
12. exact normal/batch/serial opening quantity and identity reconciliation;
13. Invoice + FBR Only non-stock migration proof;
14. proof that legacy masters remain and transaction cutover/freeze has not occurred.

Phase 5 is complete only when every final-gate check is green on `ledgix-erpnext.local`.

## Naming policy

Migration helper modules use descriptive names such as `*_runtime`, `*_profiles` and `*_credit_case`. Version-suffixed source files such as `*_v2.py` or `*_v3.py` are not permitted. Repository validation enforces this rule.

Legacy Ledgix DocTypes are not renamed during Phase 5 because they are the migration source. Target business authority uses standard ERPNext/Frappe DocTypes wherever an equivalent exists.

## Production cutover usage later

Before a real client migration:

1. take a database/site backup;
2. record app/framework versions;
3. run the migration in dry-run mode without opening stock and review every conflict/deferred row;
4. select the exact target Company and leaf Warehouse where inventory is enabled;
5. reconcile legacy stock/lot/serial state;
6. rerun dry-run with opening stock enabled when applicable;
7. execute the actual migration only after the dry-run is clean;
8. rerun reconciliation and record the output;
9. only then move to Phase 6 transactional cutover planning.

Legacy masters are not deleted by this service.