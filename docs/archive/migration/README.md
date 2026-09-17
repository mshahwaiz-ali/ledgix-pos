# Ledgix ERPNext-Core Migration Archive

**Status:** HISTORICAL / COMPLETE  
**Migration phases:** 0–13 CLOSED  
**Do not use this directory as current operating authority.**

## Purpose

This directory preserves the plans, phase notes, progress ledgers and release-hardening evidence produced during the ERPNext-core migration.

The migration is complete. There is no Phase 14.

Some archived files intentionally retain phase-time wording such as `ACTIVE`, `PENDING`, old `docs/plan/...` paths, or intermediate implementation status. Those statements describe the project **at the time the document was written** and must not override current architecture or runbooks.

Do not rewrite historical phase documents merely to make them look current; use the current documentation listed below instead.

---

## Current documentation authority

### Architecture and operating flows

```text
docs/architecture/CURRENT_ARCHITECTURE.md
docs/architecture/LEGACY_AUDIT.md
docs/operations/ERP_WORKFLOWS.md
docs/operations/LOCAL_DEMO_DATA.md
```

### Local development

```text
docs/local/LOCAL_INSTALLATION.md
```

### FBR

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
```

### Production

```text
docs/production/README_PRODUCTION.md
docs/production/DEPLOYMENT.md
docs/production/PRODUCTION_CHECKLIST.md
docs/production/release_install_update.md
docs/production/backup_restore_rollback.md
docs/production/final_release_gate.md
```

Root index: `README.md`.

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

Earlier superseded design context may also remain in this archive. Where an archived document conflicts with current architecture/source, current source and the active docs above win.

---

## Final migration outcome

The completed migration established:

- Frappe v15 + ERPNext v15 + `ledgix_saas`;
- ERPNext as the active business/master/transaction/accounting/stock authority;
- retained Ledgix product pages over ERPNext-native data;
- frozen historical custom Ledgix business ledgers;
- ERPNext-native Retail POS, B2B, purchasing, inventory and payment workflows;
- ERPNext-native FBR invoice sources with Ledgix compliance/audit orchestration;
- Business Profiles and one-codebase/multi-site SaaS deployment boundaries;
- production release, backup/restore, client readiness and final acceptance tooling.

The current local acceptance dataset and present-day readiness state were completed after the migration phase documents and therefore belong in current docs, not retroactively in every historical phase note.

---

## Current external/deferred boundaries

The archive must not be read as proof that external/manual gates have happened.

Current documentation intentionally distinguishes:

- application implementation from real FBR Sandbox certification;
- FBR readiness from explicit Production activation;
- machine-verifiable release setup from physical printer/scanner/device UAT;
- local acceptance from real client production acceptance;
- frozen legacy retention from a future physical schema-deletion project.

Check current docs before making any go-live statement.

---

## Rule for future maintainers

When investigating why a migration decision was made, use this archive.

When operating, developing or deploying the current product, do **not** follow archived phase instructions blindly. Start from `README.md` and the active documentation tree.
