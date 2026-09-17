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

Use **`erpnext_core_migration_progress.md`** for the completed migration evidence.

Production/client lifecycle runbook:

- `docs/production/client_lifecycle.md`

Post-migration release workstream:

- `client_acceptance_production_release_hardening.md`
- `release_hardening_progress.md` — active execution ledger/status

Production hardening runbooks:

- `docs/production/release_install_update.md`
- `docs/production/backup_restore_rollback.md`
- `docs/production/fresh_client_provisioning.md`
- `docs/production/multi_site_saas.md`
- `docs/production/client_onboarding_readiness.md`
- `docs/production/fbr_sandbox_production_activation.md`
- `docs/production/printing_devices_uat.md`
- `docs/production/final_release_gate.md`

## Current implementation status

- **ERPNext Core Migration Phases 0–13: COMPLETE**. Do not create a Phase 14.
- R0 + R2 production release hardening: COMPLETE.
- R3 backup/restore proof: COMPLETE.
- R1 fresh-client provisioning + R4 multi-site SaaS hardening: COMPLETE.
- R5 client onboarding/readiness: COMPLETE on the canonical local integration site.
- FBR application/setup tooling: COMPLETE at code/static-contract level. Real seller identity/tokens and real FBR Sandbox/Production certification remain external client inputs and must never be fabricated.
- Printing/device/profile UAT tooling: IMPLEMENTED; static/local acceptance gate pending exercise.
- Final immutable production release gate: IMPLEMENTED; real production acceptance remains dependent on manual UAT, strict backup/release evidence, online smoke, and FBR certification only when FBR Production is intended.
- Recovery/final acceptance now use a true read-only Phase 12 snapshot verifier; the administrative Phase 12 verifier remains separate because it intentionally records verification metadata.

## Current gates

Local machine-verifiable setup/acceptance:

```bash
bash scripts/run_release_acceptance_readiness_gate.sh ledgix-erpnext.local
```

Final production acceptance after deployment and real UAT:

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site <client-site> \
  --url https://<client-domain> \
  --release <immutable-sha-or-tag>
```

Add `--require-fbr-production` only when the client is actually going live with FBR Production.

## Historical plan

`new_plan.md` is retained as historical design context only. Its earlier **"No ERPNext dependency"** direction has been superseded by `erpnext_core_migration_plan.md` and must not be used as implementation authority for new work.
