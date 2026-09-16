# Ledgix Planning Index

## Active architecture plan

Use **`erpnext_core_migration_plan.md`** as the current master architecture and implementation plan.

It defines the active direction:

- Frappe v15 + ERPNext v15 + `ledgix_saas`;
- ERPNext as the authoritative business engine;
- Ledgix as the product, FBR/compliance, UX, intelligence and branding layer;
- one business concept = one source of truth;
- staged migration with reconciliation before legacy retirement.

## Phase implementation documents

- `erpnext_phase3_extension_schema.md` — standard-master extension model;
- `erpnext_phase4_tax_parity_matrix.md` — tax/accounting parity;
- `erpnext_phase5_master_migration.md` — master migration/reconciliation;
- `erpnext_phase6_selling_cutover.md` — B2B selling/payments/returns, **COMPLETE**;
- `erpnext_phase7_buying_inventory_cutover.md` — buying/inventory authority cutover, **active**;
- `erpnext_core_migration_progress.md` — exercised implementation evidence/status ledger.

## Historical plan

`new_plan.md` is retained as historical design context only.

Its earlier **"No ERPNext dependency"** direction has been superseded by `erpnext_core_migration_plan.md` and must not be used as the implementation authority for new work.
