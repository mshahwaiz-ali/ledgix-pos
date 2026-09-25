# Ledgix POS — Backup, Restore and Rollback

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Primary tooling:** deploy/backup_safe.sh, deploy/verify_backup_set.sh, deploy/restore_drill.sh

## 1. Purpose

This document defines the supported recovery contract for Ledgix.

The core rule is:

> **A release is not safely deployable unless its current state can be recovered using a verified site backup tied to a known application release.**

Recovery must protect:

- database;
- public files;
- private files;
- encrypted Frappe values;
- site identity;
- release identity;
- historical Ledgix retirement evidence.

---

## 2. Recovery set

deploy/backup_safe.sh creates a recovery set containing:

- database dump;
- public files archive;
- private files archive;
- site_config recovery input;
- SHA-256 manifest;
- backup metadata.

This is the canonical Ledgix site-level backup contract.

---

## 3. Backup metadata

Backup metadata records evidence such as:

- site;
- site URL;
- creation time;
- operator;
- rollback owner;
- repository SHA;
- from release;
- to release;
- Frappe version;
- ERPNext version;
- Ledgix version;
- backup artifact paths;
- checksum manifest;
- optional off-host copy directory;
- verification flags.

The metadata file is sensitive and owner-only.

---

## 4. Backup command

Typical production form:

    bash deploy/backup_safe.sh \
      --site client.example.com

Useful optional parameters include:

- --from-release;
- --to-release;
- --url;
- --operator;
- --rollback-owner;
- --copy-to <absolute path>.

---

## 5. Backup creation

backup_safe.sh invokes Frappe backup with files and explicit output paths.

It requires all of:

- database artifact;
- public files artifact;
- private files artifact;
- site-config artifact.

If any required artifact is missing or empty, backup fails.

---

## 6. Checksums

The backup tool creates a SHA-256 manifest covering:

- database;
- public files;
- private files;
- site config.

It then immediately verifies the manifest.

A backup command returning success means the required local artifacts passed checksum verification at creation time.

---

## 7. Site-config sensitivity

The site-config backup can contain:

- DB identity/credentials;
- encryption key;
- other site secrets.

It is chmod owner-only by the backup tool.

Never commit it.

Never share it as ordinary debugging evidence.

---

## 8. Off-host copy

Production policy should retain a protected secondary copy.

backup_safe.sh can copy the complete verified set to an absolute mounted location and verify the checksum manifest again there.

A host snapshot alone is not a substitute for the site-level recovery contract.

---

## 9. Read-only backup verification

Use:

    bash deploy/verify_backup_set.sh \
      --metadata /absolute/path/to/ledgix-backup-....env \
      --site client.example.com

The verifier checks:

- metadata exists;
- metadata owner/mode;
- required fields;
- verification flags;
- artifact existence/size;
- artifact paths remain under recorded backup directory;
- site-config privacy;
- checksum manifest.

It does not restore or mutate a site.

---

## 10. Why release identity matters

A recovery point is tied to the application revision that created it.

The backup records:

- repository SHA;
- Frappe version;
- ERPNext version;
- Ledgix version.

A restore should use the matching release family.

Do not restore an old database into unrelated new code and call that a proven rollback.

---

## 11. Encryption key

Frappe Password fields can depend on the site's encryption_key.

Restoring DB/files without the matching source encryption key can make encrypted values unreadable.

But copying source site_config wholesale onto another recovery site can overwrite the target DB identity.

Therefore the safe restore rule is:

> **preserve target DB identity, merge the source encryption key, then restore the source database/files.**

---

## 12. Non-production restore drill

Production-like restore testing uses:

    deploy/restore_drill.sh

The tool requires:

- source site;
- separate target site;
- verified backup metadata;
- exact destructive confirmation phrase;
- explicitly marked non-production recovery target.

It refuses source == target.

---

## 13. Recovery-target marker

A recovery target must contain:

    sites/<target>/private/.ledgix-non-production-recovery-target

with exact content:

    NON_PRODUCTION_RECOVERY_TARGET=<target>

This is a deliberate guard against accidental destructive restore onto an ordinary site.

---

## 14. Restore confirmation

Required form:

    RESTORE <source-site> TO <target-site>

Exact confirmation is required.

This prevents a generic "yes" from authorizing a destructive recovery drill.

---

## 15. Restore-drill release match

The drill reads the source backup release identity and requires current repository code to match.

If the recovery bench is on a different release, the drill fails.

This prevents testing restore under unrelated code.

---

## 16. Recovery-target safety backup

Before overwriting the recovery target, restore_drill.sh creates a fresh verified backup of the target itself.

Even a disposable recovery target receives a pre-restore safety point.

---

## 17. Maintenance mode

The recovery target is placed in maintenance before restore.

If the drill fails before success, maintenance remains ON.

Do not reopen a partially restored site casually.

---

## 18. Encryption-key merge

The tool merges only the source encryption key into the target config.

It calculates a digest of target DB identity fields before and after merge.

If DB identity changes, restore stops.

---

## 19. Restore operation

The tool restores:

- database;
- public files;
- private files

into the recovery target.

After restore it verifies target database identity again.

Source DB credentials are not copied onto the target.

---

## 20. Post-restore migrate

restore_drill.sh does not migrate by default.

A matching-release restore should avoid unnecessary schema mutation.

--migrate must be explicitly requested when the recovery scenario requires it.

This distinction matters for rollback proof.

---

## 21. Local destructive recovery gate

Local development has a separate single-site destructive recovery proof:

    bash scripts/run_backup_restore_runtime_gate.sh \
      ledgix-erpnext.local \
      --confirm "RESET AND RESTORE ledgix-erpnext.local"

This is local-only.

It refuses non-local production-style domains.

---

## 22. Local recovery staging

The local runtime gate stages recovery artifacts outside the active site directory before deleting/recreating the site.

This prevents site deletion from destroying the recovery point under test.

---

## 23. What local recovery proof validates

The local gate validates:

- source app stack;
- exact repository Ledgix source;
- representative reads;
- Phase 12 frozen snapshot;
- fresh verified backup;
- destructive reset/recreate;
- encryption-key preservation;
- DB identity preservation;
- restored database/files;
- dependency preflight;
- offline smoke;
- representative ERPNext/Ledgix reads;
- frozen historical snapshot still matching;
- exactly one local active site.

---

## 24. Phase 12 recovery evidence

Migrated sites preserve frozen historical legacy data.

Recovery verification should prove:

- retirement status remains Frozen;
- frozen snapshot matches;
- required app stack exists;
- representative native records are readable.

A restore that corrupts/changes the historical digest is not valid.

---

## 25. Production rollback preparation

Before a release, know:

- production site/domain;
- current known-good SHA/tag;
- target SHA/tag;
- fresh verified backup metadata;
- checksum-valid artifacts;
- off-host copy location where required;
- framework/app versions;
- rollback owner;
- recovery proof.

If the prior known-good code or recovery point is unknown, the release is not ready.

---

## 26. Rollback strategy

Preferred rollback pair:

    previous known-good application release
      +
    pre-update verified site backup

This avoids attempting unsupported schema downgrade against a database already migrated forward.

---

## 27. Production rollback sequence

Typical incident sequence:

1. stop new writes;
2. enable maintenance;
3. retain failed-state evidence if safe;
4. identify previous known-good release;
5. verify matching recovery set;
6. restore DB/public/private files;
7. restore required encryption key safely;
8. restore exact matching Ledgix release;
9. migrate only if explicitly required by rollback plan;
10. run dependency preflight;
11. run offline smoke;
12. verify representative data;
13. verify frozen legacy state on migrated sites;
14. restart/reload services;
15. run online smoke;
16. reopen only after checks pass;
17. retain incident/rollback evidence.

---

## 28. Do not assume schema downgrade

Rolling application code backward over a database migrated forward can be unsafe.

A tested rollback normally restores:

- the database/files from before the failed upgrade;
- the application release that matches that backup.

Do not rely on reverse migrations unless they were deliberately designed/tested.

---

## 29. Backup frequency

The application tooling does not define one universal business retention schedule.

Production backup frequency/retention should be set according to:

- client policy;
- transaction volume;
- RPO/RTO;
- accounting retention;
- FBR/legal retention;
- infrastructure risk.

But every release/update/destructive operation must have a fresh verified recovery point.

---

## 30. Backup confidentiality

Recovery artifacts contain sensitive business data.

Protect:

- DB dump;
- private files;
- site config;
- metadata;
- off-host storage credentials.

Never put recovery archives in Git/public object storage.

---

## 31. Tenant separation

Each client requires a separate per-site recovery set.

Even on a shared bench:

- backup each site independently;
- record each site's release evidence;
- retain each site's encryption/site configuration separately.

A server snapshot can supplement but does not replace per-site recovery evidence.

---

## 32. FBR recovery considerations

Restore can bring back:

- FBR tokens;
- Submission Logs;
- FBR status on invoices;
- Reconciliation Required states;
- Offline Pending states;
- Sandbox evidence.

After restore, do not assume old network state is safe to retransmit.

Especially:

- preserve Reconciliation Required;
- do not blindly retry;
- verify Production mode/arm intentionally;
- do not create duplicate submissions.

---

## 33. Recovery and secrets

Because restore merges the source encryption key, restored Password fields can become readable.

This increases the sensitivity of the recovery target.

Treat a recovery drill site as confidential.

Do not expose it publicly without explicit need and controls.

---

## 34. Backup verification failure

If verify_backup_set fails:

- do not deploy;
- do not delete the old recovery point;
- investigate missing/corrupt artifact;
- create a fresh verified backup.

Do not override checksum failure.

---

## 35. Recovery drill failure

If restore drill fails:

- leave target in maintenance;
- inspect failure;
- preserve logs/evidence;
- restore the target from its pre-drill safety backup if needed.

Never respond by restoring onto the production source site.

---

## 36. Completion markers

Current local release-hardening evidence uses:

    backup_restore_static_complete=true
    backup_restore_runtime_complete=true

These are software/recovery proofs.

Production still requires its own fresh client recovery point.

---

## 37. Developer checklist

- [ ] backup artifacts complete;
- [ ] checksum manifest passes;
- [ ] metadata owner-only;
- [ ] site-config backup owner-only;
- [ ] release SHA recorded;
- [ ] framework versions recorded;
- [ ] off-host copy protected;
- [ ] restore drill target separate/non-production;
- [ ] exact confirmation used;
- [ ] target DB identity preserved;
- [ ] source encryption key handled;
- [ ] matching application release used;
- [ ] migrate not run unless intended;
- [ ] preflight/smoke after restore;
- [ ] Phase 12 frozen snapshot verified on migrated sites;
- [ ] FBR ambiguous/offline states preserved.

---

## 38. Summary

> **Ledgix recovery is a checksum-verified, release-aware site recovery contract: database, files and encryption context move together, production restore is proven on a separate non-production target, and rollback uses a known-good application/database pair rather than assuming reverse schema migration is safe.**
