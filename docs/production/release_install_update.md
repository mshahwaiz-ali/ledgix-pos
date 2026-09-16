# Ledgix Production Release Install / Update Runbook

**Workstream:** Client Acceptance + Production Provisioning + Release Hardening  
**Architecture:** one Ledgix codebase, ERPNext business authority, no per-client forks.

---

## 1. Release identity

Production deployment never follows a moving branch name.

Every approved release is identified by either:

- a full 40-character Git commit SHA; or
- an approved Git tag resolving to one commit.

`main` remains the development source of truth, but production resolves an explicit immutable release identity before a site is mutated.

The supported stack is recorded in `deploy/release_contract.env`.

Current contract:

- Frappe `15.113.4`;
- ERPNext `15.121.3`;
- app `ledgix_saas`;
- ERPNext Core Migration closure gate `d813d26d16a11665522da98c7bd542a7cc09c53f`.

Updating Ledgix never silently pulls or rewrites ERPNext core.

---

## 2. Required production inputs

For mutating production operations, set targets explicitly:

```bash
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<40-char-approved-sha-or-tag>'
export PRODUCTION_URL='https://client.example.com'
```

`PRODUCTION_SITE` and `DEPLOY_RELEASE` are required for fresh site/full provisioning.

`PRODUCTION_SITE`, `DEPLOY_RELEASE` and `PRODUCTION_URL` are required for a production update.

Do not use a moving branch such as `main` as `DEPLOY_RELEASE`.

---

## 3. Administrator credentials

Production has no implicit `admin`, `admin@123`, or other weak convenience defaults.

Fresh provisioning generates strong Administrator/database credentials automatically and stores them outside the repository with owner-only permissions. The default per-site location is:

```text
~/.config/ledgix/sites/<site>.env
```

Legacy helper output under `deploy/production.secrets.md`, if found from an older interrupted workflow, is relocated by the supported wrapper to the configured external secrets location.

Local development credentials are a separate policy and never flow into these production helpers.

---

## 4. Fresh production provisioning

Use the supported wrapper:

```bash
cd /path/to/pos
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<40-char-approved-sha-or-tag>'
export PRODUCTION_URL='https://client.example.com'
bash deploy/production_setup.sh --action site
```

For full host/bench/services setup, also provide domain/HTTPS inputs as required and use `--action full`.

The canonical site provisioner is `deploy/provision_client_site_safe.sh`. It creates an isolated database, installs ERPNext before Ledgix, migrates/builds, runs dependency preflight and offline smoke checks, and records provisioning evidence.

It does not create client business masters, apply a Business Profile, or activate FBR Production. After provisioning, configure native ERPNext prerequisites and then use `/app/ledgix-setup`.

See `docs/production/fresh_client_provisioning.md`.

---

## 5. Verified backup and restore readiness

Run an explicit verified backup before every production update, FBR Production switch or destructive maintenance operation:

```bash
bash deploy/backup_safe.sh --site client.example.com
```

The R3 contract covers database, public files, private files, secure site-config inputs, checksum verification, release identity and rollback metadata.

R3 recovery was exercised on the local canonical site with an actual destructive wipe/recreate/restore cycle and Phase 12 digest verification. Production still requires the correct client-specific recovery point and operational approval before destructive recovery.

See `docs/production/backup_restore_rollback.md`.

---

## 6. Safe update: single-site bench

Use this path only when the bench contains one site:

```bash
bash deploy/deploy_update_safe.sh \
  --site client.example.com \
  --release '<40-char-approved-sha-or-tag>' \
  --url 'https://client.example.com'
```

Equivalent wrapper form:

```bash
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<40-char-approved-sha-or-tag>'
export PRODUCTION_URL='https://client.example.com'
bash deploy/production_setup.sh --action deploy-update
```

The updater verifies a backup before code movement, enables maintenance, checks out the immutable release, verifies the pinned stack, syncs Ledgix exactly, builds/migrates, runs preflight/offline smoke, refreshes services, runs online smoke and only then writes successful release evidence.

If the bench contains multiple sites, this updater fails closed. There is no environment-variable bypass.

---

## 7. Safe update: shared multi-site bench

Application code and built assets are bench-level resources. Every Ledgix tenant on one shared bench must therefore move as one explicitly approved release cohort.

Use:

```bash
bash deploy/deploy_update_shared_safe.sh \
  --release '<40-char-approved-sha-or-tag>' \
  --site client-a.example.com=https://client-a.example.com \
  --site client-b.example.com=https://client-b.example.com
```

The supplied cohort must exactly match every site on that bench that has `ledgix_saas` installed.

The shared updater:

1. validates every tenant and the pinned stack;
2. creates and verifies a per-site backup for every tenant;
3. puts the full cohort into maintenance before shared code movement;
4. switches/syncs/builds the approved Ledgix release once;
5. migrates, preflights and offline-smokes every tenant;
6. restarts shared processes once;
7. reopens the cohort only after all offline gates pass;
8. online-smokes every tenant;
9. returns the full cohort to maintenance if any online smoke fails;
10. writes per-site release evidence with one common cohort digest.

If clients require different Ledgix revisions, place them on separate benches instead of creating per-client forks.

See `docs/production/multi_site_saas.md`.

---

## 8. Release evidence

Successful updates retain:

```text
frappe-bench/sites/<site>/private/ledgix-release/last-successful.env
```

Evidence includes site/URL, previous and deployed release identities, backup metadata and smoke/preflight results. Shared-bench releases also record the common cohort digest.

Fresh provisioning retains separate initial provisioning evidence under the site's private directory.

---

## 9. Static gates

Release baseline / single-site deployment contract:

```bash
bash scripts/run_release_hardening_static_gate.sh
```

Backup/restore contract:

```bash
bash scripts/run_backup_restore_static_gate.sh
```

Fresh provisioning + multi-site contract:

```bash
bash scripts/run_r1_r4_static_gate.sh
```

These static gates do not deploy production sites.

---

## 10. Rollback boundary

Rollback restores application revision, database and files as one consistent recovery point.

Do not:

- delete the previous known-good release identity before the rollback window closes;
- delete the verified backup set;
- unfreeze Phase 12 historical Ledgix data as a normal rollback shortcut;
- run legacy Ledgix and ERPNext financial/stock authorities in parallel.

---

## 11. Product boundary

There are no per-client forks. Client differences remain standard ERPNext configuration, permissions and Ledgix Business Profile/product settings.
