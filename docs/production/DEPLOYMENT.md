# Ledgix Production Deployment

**Status:** CURRENT  
**Architecture:** Frappe v15 + ERPNext v15 + `ledgix_saas`  
**Production release policy:** immutable SHA/tag only

## Purpose

This is the entrypoint for production deployment after the ERPNext-core migration.

Production is not a copy of the local development flow. Do not use `bench start`, local default credentials, a moving `main` branch, or a Ledgix-only site for a live client.

---

## 1. Production architecture

```text
Internet
  -> DNS / HTTPS
  -> Nginx
  -> Frappe production processes managed by Supervisor
  -> Frappe bench
      -> ERPNext
      -> ledgix_saas
  -> per-client Frappe site/database
  -> MariaDB / Redis / files
```

Ledgix SaaS uses native Frappe multitenancy:

- one site per client;
- one database per site;
- one shared Ledgix codebase per bench;
- separate client configuration, users, business data, FBR credentials and backups;
- no per-client code forks.

If clients need different Ledgix releases, place them on separate benches rather than forking application code.

---

## 2. Supported stack and release contract

The current production contract is recorded in:

```text
deploy/release_contract.env
```

Current pinned versions:

- Frappe `15.113.4`
- ERPNext `15.121.3`
- Ledgix app `ledgix_saas`

Production deployment must resolve Ledgix to:

- a full approved 40-character Git commit SHA; or
- an approved immutable tag resolving to one commit.

Do not deploy a moving branch name as the production release identity.

---

## 3. Before deployment

Confirm:

- DNS ownership and intended domain;
- SSH access through a restricted trusted path;
- firewall/security-group policy;
- MariaDB/Redis are not exposed publicly;
- server sizing is appropriate for the expected client load;
- the repository is clean and the approved release is known;
- backup destination/ownership is known;
- FBR Production is **not** assumed to be ready merely because application deployment is ready.

Run repository/static validation before approving a release:

```bash
bash scripts/ci_local.sh
bash scripts/run_release_hardening_static_gate.sh
```

Use the additional static gates documented in `docs/production/release_install_update.md` when validating backup/provisioning/multisite contracts.

---

## 4. Clone repository and select approved release

Example initial checkout:

```bash
git clone https://github.com/mshahwaiz-ali/pos.git
cd pos
chmod +x install.sh site_setup.sh start.sh deploy/*.sh scripts/*.sh
```

The production wrapper resolves/checks the explicit release identity. Do not manually run an unpinned `git pull` immediately before go-live and assume that is an approved release.

---

## 5. Fresh client provisioning

Preferred site-level provisioning on an already prepared production bench:

```bash
cd /path/to/pos

export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<approved-40-char-sha-or-immutable-tag>'

bash deploy/production_setup.sh --action site
```

For a full host/bench/services rollout:

```bash
export PRODUCTION_SITE='client.example.com'
export DEPLOY_RELEASE='<approved-40-char-sha-or-immutable-tag>'
export PRODUCTION_URL='https://client.example.com'

bash deploy/production_setup.sh --yes --action full
```

The safe provisioner:

- creates an isolated client site/database;
- installs ERPNext before Ledgix;
- uses strong generated credentials;
- stores production credentials outside the repository;
- migrates/builds;
- enables the scheduler where required for normal Frappe/ERPNext operation;
- runs dependency preflight and offline smoke checks;
- records provisioning evidence;
- does not create client business masters;
- does not apply the Business Profile automatically;
- does not activate FBR Production.

Detailed runbook: `docs/production/fresh_client_provisioning.md`.

---

## 6. Do not manually create a Ledgix-only production site

The following legacy-style pattern is **not** the supported Ledgix production workflow:

```text
bench new-site ...
bench --site ... install-app ledgix_saas
```

without first ensuring/installing ERPNext and satisfying the release contract.

ERPNext is a required application and the business authority.

Use the supported production provisioner instead of assembling the stack ad hoc.

---

## 7. Client business onboarding

Provisioning installs infrastructure/application code only.

Before client handover configure the required native ERPNext prerequisites, including as applicable:

- Company and Chart of Accounts;
- accounting defaults;
- Selling/Buying Price Lists;
- Warehouses;
- Modes of Payment and account mappings;
- Customers/Suppliers;
- POS Profile and walk-in/default customer;
- tax accounts and client tax/FBR mapping inputs.

Then use:

```text
/app/ledgix-setup
```

and complete the client readiness workflow documented in:

```text
docs/production/client_lifecycle.md
docs/production/client_onboarding_readiness.md
```

---

## 8. HTTPS, Nginx and Supervisor

Live production must use the production service model, not the development runner.

Required principles:

- Nginx terminates/forwards HTTP(S);
- Supervisor manages Frappe production processes;
- HTTPS is enabled before sensitive production integrations are activated;
- production status checks run against the intended host/domain;
- `bench start` is never the live production process manager.

Use the `deploy/production_setup.sh` workflow rather than maintaining a second undocumented manual service sequence.

---

## 9. Backups before changes

Before every production update, destructive maintenance operation or FBR Production activation:

```bash
bash deploy/backup_safe.sh --site client.example.com
```

Verify the backup set and retain the required protected/off-host copy according to client policy.

Detailed runbook:

```text
docs/production/backup_restore_rollback.md
```

A host snapshot alone is not a substitute for a verified Ledgix site recovery set.

---

## 10. Updating an existing production deployment

### Single-site bench

```bash
bash deploy/deploy_update_safe.sh \
  --site client.example.com \
  --release '<approved-40-char-sha-or-tag>' \
  --url 'https://client.example.com'
```

### Shared multi-site bench

Use `deploy/deploy_update_shared_safe.sh` with the complete explicitly approved Ledgix tenant cohort.

Never use the single-site updater to switch shared application code for only one tenant on a multi-site bench.

Detailed runbooks:

```text
docs/production/release_install_update.md
docs/production/multi_site_saas.md
```

---

## 11. Final release acceptance

Deployment success alone is not client acceptance.

For final production approval run:

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site client.example.com \
  --url https://client.example.com \
  --release <full-40-character-SHA-or-immutable-tag>
```

Add `--require-fbr-production` only when FBR Production is genuinely part of that go-live and its separate external evidence is complete.

See `docs/production/final_release_gate.md`.

---

## 12. FBR production boundary

The FBR application layer is implemented, but the current repository documentation must **not** claim live Production readiness without real client credentials, real Sandbox network proof and the required go-live evidence.

Use:

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
docs/production/fbr_sandbox_production_activation.md
```

Production FBR posting remains fail-closed and uses no blind retry scheduler for ambiguous outcomes.

---

## 13. Production secrets

Production credentials belong outside the repository. Fresh provisioning uses an owner-only per-site external location, defaulting to:

```text
~/.config/ledgix/sites/<site>.env
```

Never commit:

- site/database passwords;
- Administrator credentials;
- FBR tokens;
- API keys/private keys;
- `site_config.json` or recovery copies;
- database/file backups;
- generated production evidence containing secrets.

Run the repository secret scan before commits/releases.

---

## 14. Current runbook map

| Task | Runbook |
|---|---|
| Fresh production client | `fresh_client_provisioning.md` |
| Client lifecycle | `client_lifecycle.md` |
| Client readiness | `client_onboarding_readiness.md` |
| Release/update | `release_install_update.md` |
| Backup/restore/rollback | `backup_restore_rollback.md` |
| Multi-site SaaS | `multi_site_saas.md` |
| FBR activation | `fbr_sandbox_production_activation.md` |
| Printing/device UAT | `printing_devices_uat.md` |
| Final production gate | `final_release_gate.md` |
| Security | `SECURITY.md` |
| Troubleshooting | `TROUBLESHOOTING.md` |

Use `docs/production/PRODUCTION_CHECKLIST.md` as the concise go-live checklist over these detailed procedures.
