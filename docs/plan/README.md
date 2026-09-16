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
- Phase 12: `erpnext_phase12_legacy_freeze_retirement.md`
- Phase 13: `erpnext_phase13_client_profiles_saas.md`

Use **`erpnext_core_migration_progress.md`** for exercised gate status and current handoff state.

Production/client lifecycle runbook:

- `docs/production/client_lifecycle.md`

Post-migration release workstream:

- `client_acceptance_production_release_hardening.md`

## Current implementation status

- **ERPNext Core Migration Phases 0–13: COMPLETE** on the guarded integration workflow.
- Phase 13 final guarded gate passed at migration implementation HEAD `d813d26d16a11665522da98c7bd542a7cc09c53f` with `phase13_complete=true` and `migration_complete=true`.
- Phase 12 frozen historical digest remained stable and the integration-site profile/setup state was restored after the gate.
- The project is now in **Client Acceptance + Production Provisioning + Release Hardening**.
- Do not create another ERPNext Core Migration phase. Remaining work is release/operations hardening over the completed architecture.

## Historical plan

`new_plan.md` is retained as historical design context only.

Its earlier **"No ERPNext dependency"** direction has been superseded by `erpnext_core_migration_plan.md` and must not be used as implementation authority for new work.
