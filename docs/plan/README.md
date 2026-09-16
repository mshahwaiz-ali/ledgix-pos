# Ledgix Planning Index

## Active architecture plan

Use **`erpnext_core_migration_plan.md`** as the master architecture and implementation authority.

Current direction:

- Frappe v15 + ERPNext v15 + `ledgix_saas`;
- ERPNext as the authoritative business engine;
- Ledgix as the product, FBR/compliance, UX, intelligence and branding layer;
- one business concept = one source of truth;
- staged migration with reconciliation before legacy retirement.

## Phase documents

- Phase 3: `erpnext_phase3_extension_schema.md`
- Phase 4: `erpnext_phase4_tax_parity_matrix.md`
- Phase 5: `erpnext_phase5_master_migration.md`
- Phase 6: `erpnext_phase6_selling_cutover.md`
- Phase 7: `erpnext_phase7_buying_inventory_cutover.md`
- Phase 8: `erpnext_phase8_pos_cutover.md`
- Phase 9: `erpnext_phase9_fbr_cutover.md`
- Phase 10: `erpnext_phase10_bi_reports_print.md`
- Phase 11: `erpnext_phase11_workspace_product_simplification.md`

Use **`erpnext_core_migration_progress.md`** for exercised gate status and current handoff state.

## Current implementation status

- Phase 0–10: complete on the guarded migration/integration workflow.
- Phase 11: implemented; final guarded runtime gate pending.
- Next after Phase 11: Phase 12 — Legacy Freeze, Reconciliation and Retirement.

## Historical plan

`new_plan.md` is retained as historical design context only.

Its earlier **"No ERPNext dependency"** direction has been superseded by `erpnext_core_migration_plan.md` and must not be used as implementation authority for new work.
