# FBR Redesign — V2 Migration and Readiness Gate

**Status:** LEGACY SETTINGS DB CLEANUP COMPLETE LOCALLY — SOURCE TOMBSTONE RETIRED  
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

## 5. Current retained compatibility boundary

Controlled local cleanup has now removed the retired singleton database authority:

- old `Ledgix FBR Settings` DocType metadata is absent;
- Workspace Link count is zero;
- old DocPerm count is zero;
- old Custom DocPerm count is zero;
- old `tabSingles` rows are zero;
- V2 profile `FBR-PROFILE-00094` remains Disabled / Manual / unarmed;
- `V2_NETWORK_CUTOVER_ACTIVE` remains false.

The obsolete `ledgix_fbr_settings` controller/schema source package is now physically removed so a future migrate cannot recreate the singleton.

Still intentionally retained for one final compatibility-closure step:

- inert compatibility API shell `api/fbr_settings.py`;
- retired historical V2 migration tombstone;
- guarded cleanup helper `patches/v1_0/cleanup_retired_fbr_settings_metadata.py`, still unregistered and idempotent.

None of these retained artifacts is current FBR configuration authority.

---

## 6. Static retirement contract

The source/runtime retirement contracts now prove:

- historical migration entry points remain fail-closed;
- the old Settings package is not registered;
- the old controller/schema source directory is absent;
- current product shell, permissions and validation do not expose the old singleton;
- the compatibility API shell never reads credentials or the retired singleton;
- the post-cleanup runtime gate requires the old DocType to be absent;
- V2 remains the only live configuration authority;
- Production remains disabled/unarmed.

---

## 7. Remaining retirement sequence

After local DB cleanup and source tombstone removal:

1. run the complete static/source retirement gate;
2. synchronize canonical source into the local Bench runtime and prove byte parity;
3. run the post-cleanup runtime gate and V2 activation/health gates with network hard-blocked;
4. prove an ordinary migrate does not recreate `Ledgix FBR Settings`;
5. repeat zero-reference/import proof for `api/fbr_settings.py`;
6. retire that compatibility API shell only when no live import/caller remains;
7. keep Production disabled/unarmed until real reference-data and Sandbox-certification readiness is complete.

Do not recreate the old singleton or re-register its package to satisfy any historical test.

---

## 8. Guarded database cleanup record

Patch 5E2D added:

`apps/ledgix_saas/patches/v1_0/cleanup_retired_fbr_settings_metadata.py`

It remains intentionally **unregistered in `patches.txt`**. Ordinary migrate therefore does not run it.

The controlled local cleanup was performed only after:

- source/runtime parity proof;
- read-only inventory;
- a fresh database + public files + private files + site-config backup;
- checksum verification and independent re-verification;
- a secondary backup copy;
- exact temporary site-config authorization;
- V2 fail-closed proof.

The cleanup target was exactly:

- 1 Workspace Link;
- 3 DocPerm rows;
- 3 Custom DocPerm rows;
- 28 Singles rows;
- the retired `Ledgix FBR Settings` DocType metadata.

Post-cleanup evidence shows all of those legacy counts at zero while the V2 profile remains Disabled / Manual / unarmed.

No FBR network operation or accounting mutation is part of this helper.

---

## 9. Safety boundary

This retirement phase does not:

- enable FBR;
- arm Production;
- perform an FBR/PRAL request;
- alter ERPNext accounting;
- fabricate reference data;
- alter historical submitted invoice evidence.

The destructive local singleton metadata cleanup is already complete and rollback-protected by the verified backup set. No Production-site cleanup has been performed by this local proof.

Production remains fail closed until the separate real-world readiness and Sandbox certification gates are satisfied.
