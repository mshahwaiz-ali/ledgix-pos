# ERPNext Phase 8 — POS Engine Migration

## Status

**IMPLEMENTED — FINAL RUNTIME GATE PENDING**

Phase 7 has proven ERPNext buying/inventory authority. Phase 8 keeps the Ledgix POS screen but replaces the live retail backend underneath it with standard ERPNext POS documents.

## Architecture decision

The **Ledgix POS UI is retained** because it already provides the desired fast retail workflow, scanner-oriented catalog, split-tender interaction, held carts, B2B toggle and Ledgix visual design.

The UI is no longer allowed to create parallel Ledgix financial or stock ledgers.

### ERPNext authority

- cashier configuration -> `POS Profile`
- cashier opening -> `POS Opening Entry`
- retail sale -> `POS Invoice`
- retail payments/change -> `POS Invoice Payment` rows and native POS validation
- cashier closing/consolidation -> `POS Closing Entry` + native consolidated `Sales Invoice`
- retail return -> native `POS Invoice` return mapping
- held retail cart -> draft `POS Invoice`
- held B2B cart -> draft `Sales Invoice`
- customer -> `Customer`
- item/catalog -> `Item` / `Item Group`
- price -> `Price List` / `Item Price` / `Pricing Rule`
- stock availability -> `Bin` / Stock Ledger
- serial/batch -> ERPNext `Serial No` / `Batch` / Serial and Batch Bundle
- accepted tenders -> `Mode of Payment` + `POS Profile` payment modes

### Ledgix ownership retained

- the POS page and interaction design;
- authorization policy around Ledgix Cashier/Manager/Admin;
- compatibility RPC names used by the current page;
- immutable price-override audit context;
- FBR legal metadata and later submission/reconciliation layer;
- branding and later Ledgix-native print formats.

## Compatibility strategy

Legacy modules remain in the repository for history/rollback during migration. Frappe `override_whitelisted_methods` routes the existing POS RPC names to `ledgix_saas.api.pos_compat` instead of rewriting or deleting legacy modules in-place.

Covered contracts include:

- `v2_pos` boot/search/preview/complete/customer-context;
- `v2_returns` context/create;
- `v2_holds` create/list/resume/cancel;
- shift APIs through both `api.shifts` and the public `api.api` wrapper used by the current page.

B2B checkout continues to use the already-proven Phase 6 Sales Invoice/Payment Entry engine.

## Hold policy

A hold is an unfinished native invoice, not a second POS ledger.

- Retail -> draft `POS Invoice`.
- B2B -> draft `Sales Invoice`.
- Drafts must create no GL Entry and no Stock Ledger Entry.
- Ledgix-only hold IDs/status/request JSON are restoration metadata only; native draft totals remain authoritative.

## Payment policy

Retail payment is represented only by standard POS Invoice payment rows.

- payment modes must exist on the active POS Profile;
- accounts come from ERPNext Mode of Payment company mappings;
- configured reference requirements remain enforced;
- cash over-tender/change uses native POS change behavior;
- no `Ledgix Payment` is written for the retail cutover path.

## Return policy

Retail returns use ERPNext's POS return mapper. Client input can select item/quantity only. Original native invoice rates remain authoritative; request-supplied return rates are never copied into the return.

B2B returns continue through the Phase 6 native Sales Invoice Credit Note path.

## Print boundary

The current POS page still knows only the legacy `Ledgix Sale` print URL. Phase 8 therefore suppresses that known-wrong legacy print call after native checkout and returns `print_deferred=true` plus the native document identity. Native/Ledgix branded POS and A4 print formats are finalized in the dedicated print phase rather than pretending the legacy print target is valid.

## FBR boundary

Phase 8 **does not perform the FBR source cutover**.

There must be no dual submission. Real FBR payload datasource/network submission remains on the existing controlled path until Phase 9 compares native payload previews and deliberately switches the source from legacy Ledgix Sale to native Sales/POS Invoice/Credit Note documents.

## Guarded final gate

Runner:

```bash
bash scripts/run_erpnext_phase8_final_gate.sh ledgix-erpnext.local
```

The gate is restricted to `ledgix-erpnext.local` and `main`.

It proves:

1. repository validation and migration are green;
2. Phase 6/7/8 static contracts pass fail-closed;
3. native POS boot/catalog/pricing/stock use ERPNext authority;
4. native POS Opening Entry works;
5. held retail carts persist as draft POS Invoice with zero GL/SLE;
6. hold resume/cancel works without Ledgix POS Hold writes;
7. retail checkout creates a submitted POS Invoice;
8. split tender, reference and native change work;
9. checkout client-sale idempotency reuses the same POS Invoice;
10. retail return uses a native POS Invoice return and keeps source rate authority;
11. POS Closing Entry consolidates the shift and posts stock/accounting exactly once through ERPNext;
12. expected final stock delta is proven from ERPNext Bin/SLE;
13. Ledgix Sale/Payment/POS Shift/POS Hold/stock/FBR-log counts do not change;
14. `fbr_source_cutover_performed=false`;
15. final result returns `phase8_complete=true` and `phase9_ready=true`.

## Exit criteria

Phase 8 closes only when the guarded runtime gate is green. At that point the new POS live path has no dependence on legacy Ledgix sale/payment/shift/hold/stock ledgers, and the project advances to **Phase 9 — FBR Source Cutover**.
