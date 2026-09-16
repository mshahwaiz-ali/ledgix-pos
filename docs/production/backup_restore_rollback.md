# Ledgix Backup, Restore and Rollback Runbook

Status: R3 release hardening procedure.

This runbook covers two distinct recovery modes:

1. a **single canonical local site** for development and integration;
2. a production-safe restore procedure that never experiments on the production source site.

The local environment is intentionally simpler than production. Local development uses one site only: `ledgix-erpnext.local` by default.

---

## 1. Standard local site model

Ledgix local development uses one canonical site with one standard application order:

```text
Frappe -> ERPNext -> Ledgix
```

`site_setup.sh` is Ledgix-specific. It does not ask the operator to choose applications. ERPNext is mandatory and Ledgix is always installed after ERPNext.

Default local site:

```text
ledgix-erpnext.local
```

Create or repair the standard site:

```bash
./site_setup.sh --ensure
```

Destructively delete every active `.local` / `.localhost` site and recreate only the canonical site:

```bash
./site_setup.sh \
  --reset \
  --site ledgix-erpnext.local \
  --confirm "RESET ledgix-erpnext.local"
```

The reset is local-only. It refuses production-style domains.

---

## 2. Backup contract

`deploy/backup_safe.sh` creates a complete recovery set containing:

- database dump;
- public files archive;
- private files archive;
- `site_config` recovery input;
- SHA-256 manifest;
- site/release/version/operator/rollback metadata.

The backup command uses explicit output paths and verifies every required artifact before returning success.

The site-config backup is sensitive. It may contain database credentials and the `encryption_key`; it must remain owner-only and must never be committed.

For production, keep a protected off-host/off-server copy. `backup_safe.sh --copy-to <absolute-path>` can create and verify a secondary copy on mounted protected storage.

---

## 3. Backup verification

Read-only verification:

```bash
bash deploy/verify_backup_set.sh \
  --metadata /absolute/path/to/ledgix-backup-...env \
  --site example.local
```

The verifier checks:

- metadata permissions;
- database/public/private/config verification flags;
- artifact existence and non-empty size;
- site-config permissions;
- SHA-256 manifest integrity.

It never restores, migrates, or changes a site.

---

## 4. Why the encryption key matters

Frappe Password fields may be encrypted using the site's `encryption_key`.

A recovery therefore cannot blindly replace the target `site_config.json` with the source file. The safe rule is:

- preserve the target database identity and credentials;
- extract the source backup's `encryption_key`;
- merge only that key into the recovery target config;
- verify that DB identity is unchanged;
- restore the database and files.

This keeps database isolation while allowing restored encrypted values to remain readable.

---

## 5. In-place local recovery drill

Local development intentionally keeps one site only, so R3 does **not** require a permanent `ledgix-recovery.local` site.

The consolidated local runtime drill is destructive but safe for the disposable local integration environment:

```text
ledgix-erpnext.local
      |
      | verified backup
      v
frappe-bench/recovery-staging/...
      |
      | wipe/recreate same local site
      v
ledgix-erpnext.local
      |
      | restore staged DB/files + encryption key
      v
Phase 12 + ERPNext/Ledgix verification
```

The recovery set is copied outside the active site directory before the site is deleted. Therefore deleting/recreating the site cannot destroy the recovery point being tested.

Run:

```bash
bash scripts/run_backup_restore_runtime_gate.sh \
  ledgix-erpnext.local \
  --confirm "RESET AND RESTORE ledgix-erpnext.local"
```

Optional online smoke:

```bash
bash scripts/run_backup_restore_runtime_gate.sh \
  ledgix-erpnext.local \
  --confirm "RESET AND RESTORE ledgix-erpnext.local" \
  --url http://ledgix-erpnext.local:8000
```

The runtime gate refuses non-local domains.

---

## 6. What the single-site runtime gate proves

The in-place local recovery drill performs one coherent proof:

1. rerun R3 static contracts;
2. verify source site has Frappe, ERPNext and Ledgix;
3. sync the exact repository Ledgix code into the bench;
4. verify representative reads and Phase 12 frozen snapshot before reset;
5. create a fresh checksum-verified source backup;
6. stage the recovery set outside the site directory;
7. wipe all active local sites;
8. recreate one clean canonical site with Frappe -> ERPNext -> Ledgix;
9. preserve the new site's DB identity;
10. merge only the old source encryption key;
11. restore database, public files and private files;
12. verify the fresh DB identity remains unchanged;
13. run dependency preflight and offline smoke;
14. verify representative ERPNext/Ledgix reads;
15. verify Phase 12 remains frozen and its snapshot still matches;
16. ensure exactly one active local site remains;
17. retain owner-only recovery evidence.

A passing runtime gate ends with:

```text
backup_restore_runtime_complete=true
```

---

## 7. Phase 12 verification

The recovery verifier is read-only. It never calls the Phase 12 freeze routine again.

For migrated integration/client data it verifies:

- legacy state remains Frozen;
- the persisted frozen snapshot matches restored legacy history;
- Frappe, ERPNext and Ledgix are installed;
- representative `Company`, `Item`, `Customer`, `Sales Invoice` and `Business Profile` reads succeed.

Any mismatch fails the recovery drill.

---

## 8. Production recovery remains isolated

The single-site destructive drill is **local-only**. It is not the production restore procedure.

For production or production-like recovery, use `deploy/restore_drill.sh` with a separate explicitly marked non-production recovery target. The helper refuses to restore onto the source site and requires the exact destructive confirmation phrase.

Production restore evidence must prove restoration away from the live source before a real rollback is approved.

---

## 9. Matching release rule

A recovery point is tied to the application revision that created it.

The backup metadata records the repository SHA and installed Frappe/ERPNext/Ledgix versions. Recovery must use the matching release family. A restore is not considered proven if different application code is silently substituted.

---

## 10. Production rollback gate

Before any production release, identify:

- production site/domain;
- current known-good immutable SHA/tag;
- approved target SHA/tag;
- verified current-state recovery metadata;
- checksum-valid database/public/private/config artifacts;
- protected off-host copy where required;
- exact Frappe/ERPNext/Ledgix versions;
- operator;
- rollback owner;
- recovery evidence appropriate to the release family.

If the previous known-good release or its restorable recovery point is unknown, the release is not approved.

---

## 11. Production rollback sequence

A real rollback is an incident procedure:

1. stop new business writes and enable maintenance mode;
2. retain evidence of the failed/current state where safe;
3. select the previous known-good immutable release;
4. verify its backup metadata and checksums;
5. restore database/public/private files;
6. restore required secure config inputs, especially the matching `encryption_key`, without replacing DB identity incorrectly;
7. restore/sync the matching Ledgix application revision;
8. migrate only if the rollback strategy explicitly requires and supports it;
9. run client dependency preflight and offline smoke;
10. verify representative reads and Phase 12 frozen state;
11. restart/reload services;
12. run online smoke;
13. exit maintenance only after required checks pass;
14. retain incident and rollback evidence.

Do not assume schema downgrade is safe. Prefer a known-good database snapshot together with its matching application revision.

---

## 12. Secrets and recovery storage

Never commit:

- site-config backups;
- database dumps;
- private file archives;
- Administrator passwords;
- database passwords;
- FBR tokens or credentials;
- off-host storage credentials.

Local generated credentials stay under `.secrets/` and recovery staging stays outside the active site directory. Production recovery artifacts belong in protected site-private/off-host storage.

---

## 13. R3 completion evidence

R3 is complete only when both markers are green:

```text
backup_restore_static_complete=true
backup_restore_runtime_complete=true
```

For the single-site local drill, runtime evidence is stored under:

```text
frappe-bench/sites/ledgix-erpnext.local/private/ledgix-recovery/
```

The staged recovery set remains under `frappe-bench/recovery-staging/` until intentionally cleaned up.
