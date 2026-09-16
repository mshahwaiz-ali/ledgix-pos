# Ledgix Backup, Restore and Rollback Runbook

Status: R3 release hardening procedure.

This runbook proves that a Ledgix production recovery point is not just created, but can be restored onto an isolated non-production site using the matching application release.

## 1. Recovery principles

- Never test a restore on the source/production site.
- A recovery target must be a disposable non-production Frappe site.
- Source and recovery target must use the same supported Frappe/ERPNext/Ledgix release contract.
- The backup set must contain database, public files, private files and `site_config` recovery input.
- Required artifacts are protected by a SHA-256 checksum manifest.
- Production backup metadata remains site-explicit and records release identity, versions, operator and rollback owner.
- Phase 12 frozen legacy history must still verify after restoring a migrated client site.
- Do not create a client-specific code fork to recover a site.

## 2. What `backup_safe.sh` retains

`deploy/backup_safe.sh` calls the Frappe backup command with explicit output paths for:

- database dump;
- public files archive;
- private files archive;
- `site_config` backup.

It then verifies that every artifact is non-empty, creates a SHA-256 manifest, validates the manifest immediately, records installed Frappe/ERPNext/Ledgix versions and writes owner-only rollback metadata under:

`frappe-bench/sites/<site>/private/backups/`

The `site_config` backup is sensitive because it can contain database credentials and the `encryption_key`. It must remain owner-only and must be handled as a secret.

For production, use protected off-host/off-server storage. `backup_safe.sh --copy-to <absolute-mounted-path>` can create and checksum-verify a secondary copy when the protected storage is mounted locally.

## 3. Why the encryption key matters

A restored Frappe database can contain encrypted Password fields. Those values require the source site's `encryption_key`.

The recovery drill therefore does **not** copy the complete source `site_config.json` onto the recovery target. Instead it:

1. takes a safety backup of the recovery target;
2. preserves the recovery target database identity and credentials;
3. reads the source backup's `encryption_key`;
4. merges only that key into the recovery target config;
5. verifies that the recovery target DB identity did not change;
6. restores the source database and files.

This preserves tenant/database isolation while allowing encrypted restored data to remain readable.

## 4. Backup verification

Read-only verification:

```bash
bash deploy/verify_backup_set.sh --metadata /absolute/path/to/ledgix-backup-...env --site example.local
```

The verifier checks:

- metadata is owner-only;
- required verification flags are green;
- every referenced artifact exists and is non-empty;
- artifacts remain inside the recorded private backup directory;
- the site-config backup is owner-only;
- the checksum manifest validates.

It does not migrate, restore or alter a site.

## 5. Non-production recovery target

Create a disposable site on the same dedicated/local recovery bench with Frappe, ERPNext and Ledgix installed. Do not use a production client site as the target.

The consolidated runtime gate writes an explicit marker only after the operator supplies the destructive confirmation phrase. The marker is:

`sites/<target>/private/.ledgix-non-production-recovery-target`

and contains:

```text
NON_PRODUCTION_RECOVERY_TARGET=<target-site>
```

`restore_drill.sh` refuses to continue without this marker and also refuses when source and target are the same site.

## 6. Matching release rule

A restore drill must run with the same Ledgix repository release recorded in the backup metadata.

If the backup records release SHA `abc...`, the recovery bench repository must be at that exact SHA before the restore. The restore helper fails closed when the repository HEAD differs.

This avoids accidentally proving a restore with application code that does not match the database snapshot.

## 7. Consolidated R3 runtime gate

Example for the local migration integration site and a disposable recovery site:

```bash
bash scripts/run_backup_restore_runtime_gate.sh \
  ledgix-erpnext.local \
  ledgix-recovery.local \
  --confirm "RESTORE ledgix-erpnext.local TO ledgix-recovery.local"
```

Optional online smoke after the restored recovery site is reachable:

```bash
bash scripts/run_backup_restore_runtime_gate.sh \
  ledgix-erpnext.local \
  ledgix-recovery.local \
  --confirm "RESTORE ledgix-erpnext.local TO ledgix-recovery.local" \
  --url http://ledgix-recovery.local:8000
```

The runtime gate performs one coherent proof:

1. R3 static contract and local CI;
2. explicit non-production target marker;
3. fresh checksum-verified source recovery point;
4. recovery-target safety backup before overwrite;
5. source encryption-key merge without source DB credentials;
6. database/public/private restore;
7. dependency preflight;
8. offline Ledgix/ERPNext smoke;
9. representative ERPNext/Ledgix reads;
10. Phase 12 frozen snapshot verification;
11. optional online smoke;
12. owner-only recovery evidence record.

Post-restore `bench migrate` is deliberately **not** run by default for a matching-release recovery. Use the explicit `--migrate` option on `restore_drill.sh` only when the selected recovery strategy requires it.

## 8. Phase 12 verification

The recovery verifier is read-only. It does not call the Phase 12 freeze routine again.

For migrated sites it verifies:

- legacy state is still Frozen;
- persisted frozen snapshot still matches current restored legacy history;
- Frappe, ERPNext and Ledgix are installed;
- representative `Company`, `Item`, `Customer`, `Sales Invoice` and `Business Profile` reads succeed.

A mismatch is a failed recovery drill.

## 9. Rollback preparation before production release

Before every production release identify all of the following:

- production site and URL;
- currently deployed/known-good SHA or immutable tag;
- approved target SHA or tag;
- verified backup metadata for the current known-good state;
- checksum-valid database/public/private/config artifacts;
- protected off-host copy where required;
- exact Frappe/ERPNext/Ledgix versions;
- operator;
- rollback owner;
- recovery evidence from a non-production restore drill for the release family.

If the previous known-good release or its restorable backup cannot be identified, the production release is not approved.

## 10. Production rollback sequence

A real rollback is an incident procedure, not a normal update. Keep the affected site in maintenance mode and use the previously verified recovery point.

The sequence is:

1. stop new business writes and enable maintenance mode;
2. retain evidence of the failed/current state before destructive action when safe;
3. select the previous known-good immutable release;
4. revalidate its backup metadata/checksums;
5. restore database/public/private files;
6. restore required secure site-config inputs, especially the matching `encryption_key`, without replacing the site's DB identity incorrectly;
7. restore/sync the matching Ledgix application release;
8. run migration only if the rollback strategy explicitly requires and supports it;
9. run client preflight and offline smoke;
10. verify representative reads and Phase 12 frozen state for migrated clients;
11. restart/reload services as required;
12. run online smoke;
13. exit maintenance mode only after the rollback checks pass;
14. retain incident/rollback evidence.

Frappe application/database downgrades may not be supported generically. A rollback must therefore restore a known-good database snapshot together with the matching application release rather than assuming schema downgrade is safe.

## 11. Secrets and off-host policy

Never commit any of the following:

- site-config backups;
- database dumps;
- private file archives;
- production tokens/passwords;
- off-host storage credentials.

Backup artifacts remain under site-private storage or protected backup storage. The Git repository contains only scripts, contracts and documentation.

## 12. R3 completion evidence

R3 is complete only when both are green:

```text
backup_restore_static_complete=true
backup_restore_runtime_complete=true
```

The runtime evidence file is stored under:

`frappe-bench/sites/<recovery-target>/private/ledgix-recovery/`

That evidence proves restoration without changing the source site or unfreezing Phase 12 history.
