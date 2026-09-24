# FBR Redesign — V2 Migration and Readiness Gate

**Status:** LEGACY MIGRATION EXECUTION RETIRED — HISTORICAL DESIGN / COMPATIBILITY TOMBSTONE ONLY  
**Date:** 2026-09-25  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`

---

## 1. Current authority

The V2 architecture is now the active FBR configuration/compliance authority.

Current authority is:

- `Ledgix FBR Integration Profile` for company-scoped integration configuration;
- `Ledgix FBR Item Mapping` for FBR product classification;
- ERPNext Company/Customer/Address for business identity;
- ERPNext native tax configuration and invoice accounting for monetary authority.

The old global Settings singleton and old mixed Item Tax Profile must not be used as a migration source by current runtime code.

---

## 2. Historical migration design

Earlier redesign work provided:

- a local-only read-only preview;
- a guarded local apply path;
- safe copying of selected non-monetary metadata;
- fail-closed destination profile state;
- explicit exclusion of old monetary tax fields;
- explicit exclusion of Item-level Sandbox scenario assignment;
- no automatic migration of duplicated seller identity.

That design is retained in Git history and this document only as historical evidence.

It is no longer an executable migration authority.

---

## 3. Retirement decision

Patch 5E2B1 retires:

- executable reads from the old global Settings singleton;
- legacy Password/token decryption and copying;
- legacy Item Tax Profile enumeration;
- V2 profile/item mapping writes from the historical helper;
- the confirmation/apply path;
- the live migration-preview runner.

The compatibility module remains temporarily importable so stale commands fail with an explicit retirement error instead of silently reviving old behavior.

Module:

`apps/ledgix_saas/migration/fbr_redesign_v2_migration.py`

Historical entry points retained only to fail closed:

- `preview_v2_migration(...)`
- `apply_v2_migration(...)`

Neither entry point may read or write legacy data.

---

## 4. Preview runner state

Historical runner:

`scripts/run_fbr_redesign_v2_migration_preview.sh`

The runner is now a retirement tombstone.

It:

- performs no Bench execute call;
- performs no database command;
- performs no credential read;
- performs no FBR network call;
- exits non-zero with an explicit retirement message.

It must not be converted back into a migration tool.

---

## 5. What remains intentionally present

This phase does **not** physically delete every old artifact.

Still intentionally deferred:

- old `ledgix_fbr_settings` source/controller/schema tombstone;
- compatibility API shell `api/fbr_settings.py`;
- local database Workspace Link / DocPerm / Custom DocPerm metadata;
- singleton rows in `tabSingles`;
- old DocType metadata/database table cleanup.

The old Settings package registration has now been removed from `apps/ledgix_saas/pyproject.toml`.
The remaining source/controller/schema tombstone exists only until controlled database metadata cleanup proves physical deletion safe.

These remaining artifacts are not current FBR configuration authority.

---

## 6. Static retirement contract

Test:

`apps/ledgix_saas/setup/test_fbr_redesign_v2_migration_contract.py`

It now proves:

- historical entry points remain import-compatible;
- both entry points fail closed;
- old Settings and Item Tax Profile literals are absent from the helper;
- no Password decryption exists;
- no legacy database reads/writes exist;
- no profile/item-mapping mutation exists;
- no transport/network path exists.

The source de-registration contract additionally proves that the old package is temporarily preserved while the migration authority itself is retired.

---

## 7. Remaining retirement sequence

After 5E2B1:

1. evolve remaining proof/runtime gates that still import or require the old Settings compatibility API;
2. replace presence-oriented contracts with absence/retirement contracts;
3. retire the old Settings test suite once equivalent absence proof exists;
4. package registration removal is complete; retain the source tombstone only until DB cleanup;
5. prepare a controlled Frappe patch for database metadata cleanup;
6. run that cleanup only in the controlled local runtime phase after backup/evidence capture;
7. prove zero dependency, zero network, source/runtime parity, and safe V2 profile state.

---

## 8. Prepared database cleanup patch

Patch 5E2D adds:

`apps/ledgix_saas/patches/v1_0/cleanup_retired_fbr_settings_metadata.py`

It is intentionally **not registered in `patches.txt` yet**. Pulling the source or running an ordinary migrate therefore cannot trigger this cleanup.

The module provides a read-only `preview_cleanup()` and a guarded `execute()`. Execution requires the exact temporary site-config authorization:

`ledgix_legacy_fbr_settings_cleanup_authorization = VERIFIED_BACKUP_AND_APPROVED_FBR_SETTINGS_CLEANUP`

and refuses cleanup if any V2 Integration Profile is enabled, non-Disabled, or Production-armed.

The eventual controlled cleanup targets only:

- Workspace Link rows pointing to `Ledgix FBR Settings`;
- old Custom DocPerm rows;
- old DocPerm rows;
- old `tabSingles` / Singles values;
- the retired DocType definition through Frappe's `delete_doc` semantics.

No FBR network operation or accounting mutation is part of this patch.

A separate local-runtime phase must first capture a fresh verified backup and before/after evidence. Only after that proof should patch registration/execution and physical source tombstone deletion be considered.

---

## 9. Safety boundary

This retirement phase does not:

- enable FBR;
- arm Production;
- perform an FBR/PRAL request;
- alter ERPNext accounting;
- fabricate reference data;
- delete production data;
- execute database cleanup.

Production remains fail closed until the separate real-world readiness and Sandbox certification gates are satisfied.
