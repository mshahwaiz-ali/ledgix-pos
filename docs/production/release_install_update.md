# Ledgix Production Release Install / Update Runbook

**Workstream:** Client Acceptance + Production Provisioning + Release Hardening  
**Scope:** R0 + R2 deployment hardening  
**Architecture:** one Ledgix codebase, ERPNext business authority, no per-client forks.

---

## 1. Release identity

Production deployment never follows a moving branch name.

Every approved release is identified by either:

- a full 40-character Git commit SHA; or
- an approved Git tag resolving to one commit.

`main` remains the development source of truth, but a production update resolves an explicit immutable release identity before the site is mutated.

The supported stack for the release is recorded in `deploy/release_contract.env`.

Current contract:

- Frappe `15.113.4`;
- ERPNext `15.121.3`;
- app `ledgix_saas`;
- ERPNext Core Migration closure gate `d813d26d16a11665522da98c7bd542a7cc09c53f`.

Updating Ledgix never silently pulls or rewrites ERPNext core. The pinned Frappe/ERPNext stack is a prerequisite and an incompatible production site fails closed.

---

## 2. Required production inputs

For mutating production operations, set the target explicitly:

```bash
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<40-char-approved-sha-or-tag>'
export PRODUCTION_URL='https://client.example.com'
```

`PRODUCTION_SITE` is required for site/full/backup/update actions.

`DEPLOY_RELEASE` and `PRODUCTION_URL` are additionally required for updates.

Do not use a moving branch such as `main` as `DEPLOY_RELEASE`.

---

## 3. Administrator credentials

The production wrapper no longer supplies `admin` as an implicit Administrator password.

For site creation:

- interactive setup may accept an explicitly entered password;
- unattended setup lets the underlying production helper generate a strong random password when `FRAPPE_ADMIN_PASSWORD` is omitted;
- if `FRAPPE_ADMIN_PASSWORD` is supplied intentionally, keep it outside source control and shell history where practical.

Legacy helper output written to `deploy/production.secrets.md` is immediately relocated by the supported `production_setup.sh` wrapper to:

```text
~/.config/ledgix/production-sites.md
```

or the path specified by `LEDGIX_PRODUCTION_SECRETS_FILE`.

Do not commit production credentials into the Ledgix repository.

---

## 4. Fresh production setup

Use the supported wrapper rather than calling internal EC2 helper actions directly.

Example:

```bash
cd /path/to/pos
export PRODUCTION_SITE='client.example.com'
export PRODUCTION_DOMAIN='client.example.com'
export LETSENCRYPT_EMAIL='ops@example.com'
bash deploy/production_setup.sh --yes --action full
```

The full flow prepares the supported Frappe/ERPNext bench, synchronizes Ledgix, creates the explicit site, configures production services and optionally configures HTTPS.

After provisioning, complete standard ERPNext prerequisites and use `/app/ledgix-setup` to select the client Business Profile.

---

## 5. Verified backup

Run an explicit verified backup before every production update, FBR Production switch or destructive maintenance operation:

```bash
bash deploy/backup_safe.sh --site client.example.com
```

For release updates the updater runs this automatically before maintenance mode.

The helper requires a newly-created:

- database archive;
- public files archive;
- private files archive.

It writes rollback metadata beside the site backups, including current and target release identities when supplied.

A backup is still only one part of rollback readiness. Off-host retention and an actual restore drill are handled in the R3 backup/restore workstream.

---

## 6. Safe production update

Preferred direct command:

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

The update flow:

1. requires a clean repository;
2. rejects an unapproved shared-bench update unless `LEDGIX_ALLOW_SHARED_BENCH_UPDATE=1` is deliberately set under the multi-site procedure;
3. resolves the explicit SHA/tag and rejects moving branch names;
4. records the previous SHA;
5. creates and verifies a pre-update database/files backup;
6. enables maintenance mode;
7. checks out the approved release detached at the resolved SHA;
8. verifies the tracked release contract and proves the exact pinned Frappe/ERPNext stack is already installed;
9. runs the client dependency preflight before application mutation;
10. mirrors only `ledgix_saas` into the bench exactly — ERPNext core is not pulled or rewritten by the update;
11. builds assets and migrates the target site;
12. reruns dependency preflight and ERPNext-native offline smoke checks;
13. refreshes production processes and validates Nginx/Supervisor;
14. leaves maintenance mode only after the offline gate is green;
15. runs online smoke checks against the explicit public URL;
16. re-enables maintenance mode if online smoke fails;
17. writes `private/ledgix-release/last-successful.env` only after success.

If deployment exits after maintenance mode was enabled but before success, the helper intentionally leaves maintenance mode enabled. Do not expose a partially migrated site merely because cleanup ran.

---

## 7. Shared-bench safety

Application code and built assets are bench-level resources. Therefore an update on a bench containing multiple sites can affect more than the named site even though migration commands are site-specific.

Until the R4 multi-site release procedure explicitly approves the affected sites, the updater blocks a bench containing more than one Frappe site.

The override:

```bash
export LEDGIX_ALLOW_SHARED_BENCH_UPDATE=1
```

must only be used when every affected site has been included in the shared-bench maintenance/release plan. It is not a convenience bypass.

---

## 8. Release record

After a successful update, retain:

```text
frappe-bench/sites/<site>/private/ledgix-release/last-successful.env
```

It records:

- site and URL;
- release input;
- previous SHA;
- deployed SHA;
- Frappe version;
- ERPNext version;
- Ledgix app;
- latest backup metadata path;
- dependency preflight result;
- offline smoke result;
- online smoke result.

This is operational evidence only. ERPNext remains the business-data authority.

---

## 9. Static release-hardening gate

Before using the hardened production helpers, run:

```bash
bash scripts/run_release_hardening_static_gate.sh
```

This is non-destructive. It validates repository CI, shell syntax, the immutable release contract, explicit-site rules, verified-backup contract, fail-closed maintenance behavior and ERPNext-native smoke surfaces.

It does not deploy or mutate a production site.

---

## 10. Rollback boundary

This R0 + R2 batch records the previous release and verifies a pre-update backup, but it does not yet claim a restore drill is proven.

R3 will add the restoration exercise and formal rollback evidence.

Until then:

- do not delete the previous known-good release identity;
- do not delete the verified backup set;
- do not unfreeze Phase 12 historical Ledgix business records as a normal rollback shortcut;
- never run legacy Ledgix and ERPNext financial/stock authorities in parallel.

---

## 11. Product boundary

There are no per-client forks. Client differences remain standard ERPNext configuration, permissions and Ledgix Business Profile/product settings.
