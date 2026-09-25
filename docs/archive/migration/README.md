# Ledgix ERPNext-Core Migration Archive

**Status:** HISTORICAL / COMPLETE  
**Migration phases:** 0–13 CLOSED  
**There is no Phase 14.**

## Purpose

This directory preserves the plans, phase notes, progress ledgers and release-hardening evidence produced during the completed ERPNext-core migration.

The files intentionally retain phase-time wording such as `ACTIVE`, `PENDING`, intermediate paths and then-current implementation status.

Those statements describe the project at the time they were written.

They are **not** current operating instructions.

---

## Current documentation authority

For current technical work use:

- `docs/developer/README.md`;
- `docs/developer/ARCHITECTURE.md`;
- `docs/developer/MIGRATION_AND_LEGACY_RETIREMENT.md`;
- the relevant subsystem guide under `docs/developer/`.

For client/operator work use:

- `docs/client/README.md`;
- the relevant workflow guide under `docs/client/`.

Repository front door:

- `README.md`.

Archive index:

- `docs/archive/README.md`.

---

## Archived migration set

Master historical migration plan:

- `erpnext_core_migration_plan.md`

Completed migration progress/evidence:

- `erpnext_core_migration_progress.md`

Phase documents:

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

Post-migration release-hardening history:

- `client_acceptance_production_release_hardening.md`
- `release_hardening_progress.md`

---

## Final migration outcome

The migration established:

- Frappe v15 + ERPNext v15 + `ledgix_saas`;
- ERPNext as current business/master/transaction/accounting/stock authority;
- retained Ledgix product UX over ERPNext-native data;
- frozen historical duplicate Ledgix business ledgers;
- ERPNext-native Retail POS, B2B, purchasing, inventory and payment workflows;
- ERPNext-native FBR source transactions with Ledgix compliance/audit orchestration;
- Business Profiles and one-codebase multi-site SaaS boundaries;
- production release, backup/restore, client readiness and final acceptance tooling.

---

## Related historical evidence

FBR V2 redesign history is now preserved under:

- `docs/archive/historical/fbr-v2/`

Final point-in-time audit evidence is under:

- `docs/archive/audit/`

---

## Rule for future maintainers

When investigating **why** a migration decision was made, use this archive.

When operating, developing, deploying or supporting the current product, start from `README.md` and the consolidated current documentation.

If archived material conflicts with current source/current docs, current source and current docs win.
