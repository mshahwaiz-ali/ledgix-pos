# Ledgix Local Installation and Development

**Status:** CURRENT  
**Canonical local site:** `ledgix-erpnext.local`  
**Required stack:** Frappe v15 -> ERPNext v15 -> `ledgix_saas`

## Purpose

This is the supported local setup path for the current ERPNext-core Ledgix repository.

Older instructions that create arbitrary Ledgix-only sites or install `ledgix_saas` without ERPNext are obsolete.

---

## 1. Repository layout

Typical local checkout:

```text
~/data_drive/pos/
├── install.sh
├── site_setup.sh
├── start.sh
├── apps/ledgix_saas/
├── deploy/
├── docs/
└── frappe-bench/        # generated/reused locally; not committed
```

Repository app source remains under `apps/ledgix_saas/`. Local site tooling synchronizes it into the bench application path as required.

---

## 2. First-time setup

From the repository root:

```bash
cd ~/data_drive/pos
chmod +x install.sh site_setup.sh start.sh deploy/*.sh
./install.sh --local
```

The installer:

- performs a local preflight;
- installs/reuses required Ubuntu packages;
- prepares Node/Yarn and Bench tooling;
- creates or reuses a valid Frappe v15 bench;
- ensures ERPNext v15 is present in the bench;
- validates Frappe/ERPNext branch alignment;
- leaves site creation to `site_setup.sh`.

`install.sh` does **not** start the development server as part of installation.

### Sudo behavior

The installer prefers non-interactive/passwordless sudo. On a trusted local machine only, interactive sudo can be explicitly allowed:

```bash
ALLOW_INTERACTIVE_SUDO=1 ./install.sh --local
```

Do not copy that convention into unattended production automation.

---

## 3. Canonical local site

Create or repair the supported integration site:

```bash
./site_setup.sh --ensure
```

Default site:

```text
ledgix-erpnext.local
```

The site stack is always:

```text
Frappe -> ERPNext -> ledgix_saas
```

There is no local app-selection menu. ERPNext is a required dependency of Ledgix.

Check state with:

```bash
./site_setup.sh --status
```

---

## 4. What `--ensure` may do

`site_setup.sh --ensure` is the normal safe repair/create path. It can:

- create the canonical local site when none exists;
- ensure ERPNext exists in the bench and is installed on the site;
- synchronize the repository Ledgix app into the bench;
- install `ledgix_saas` if missing;
- enable local developer mode;
- run `bench migrate`;
- build Ledgix assets;
- set the canonical site as the active bench site;
- save local credentials under `.secrets/sites/` outside Git.

It is not intended to delete existing business data.

If a different active local site or multiple active local sites exist, the script fails rather than silently deleting them.

---

## 5. Destructive local reset

A reset is explicitly destructive to active local sites and their databases.

Use it only when a clean local environment is intentionally required:

```bash
./site_setup.sh --reset \
  --site ledgix-erpnext.local \
  --confirm "RESET ledgix-erpnext.local"
```

The reset path requires the exact confirmation phrase.

**Do not use reset as a routine fix for the completed acceptance dataset.** The current `LEDGIX-RETAIL-OPERATING-V1` dataset is verified operating/acceptance data and should not be casually rebuilt. See `docs/operations/LOCAL_DEMO_DATA.md` first.

---

## 6. Start and stop development runtime

Start the local development runtime:

```bash
./start.sh
```

Useful runner actions include:

```bash
./start.sh --status
./start.sh --background
./start.sh --stop
./start.sh --smoke --site ledgix-erpnext.local
```

`start.sh` is for development/local process management only. It is not the production Supervisor/Nginx service workflow.

Expected URL:

```text
http://ledgix-erpnext.local:8000
```

If local hostname resolution is missing, `start.sh` can report/add the required `/etc/hosts` mapping interactively. Under WSL, Windows-side host resolution may also need configuration.

---

## 7. Verify the installed stack

From the bench:

```bash
cd ~/data_drive/pos/frappe-bench
bench --site ledgix-erpnext.local list-apps
bench version --format plain
```

The site must include:

```text
frappe
erpnext
ledgix_saas
```

ERPNext must not be omitted.

Run the client dependency preflight when appropriate:

```bash
cd ~/data_drive/pos
bash scripts/run_ledgix_client_preflight.sh ledgix-erpnext.local
```

---

## 8. Common development commands

```bash
cd ~/data_drive/pos/frappe-bench

bench --site ledgix-erpnext.local migrate
bench --site ledgix-erpnext.local clear-cache
bench --site ledgix-erpnext.local clear-website-cache
bench --site ledgix-erpnext.local console
bench build --app ledgix_saas
```

Run repository validation from the repository root:

```bash
bash scripts/ci_local.sh
```

Use focused tests in addition to the repository gate when changing a specific service or API.

---

## 9. Local operating/acceptance data

The current canonical local dataset is:

```text
LEDGIX-RETAIL-OPERATING-V1
```

It is already completed and verified on `ledgix-erpnext.local`.

Normal development should **verify and preserve** it, not automatically reseed it.

See:

```text
docs/operations/LOCAL_DEMO_DATA.md
```

for the current verifier, exact dataset contract, safe inspection commands and deliberate rebuild rules.

---

## 10. FBR safety locally

Local operating data deliberately keeps FBR transport disabled.

Do not add real Production credentials to the local acceptance dataset and do not fabricate Sandbox success evidence.

Current FBR documentation:

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
```

---

## 11. Local secrets

Local site credentials are stored under:

```text
.secrets/sites/<site>.env
```

The secrets directory is outside the committed source contract and must remain ignored by Git.

Before every push:

```bash
git status
```

Do not commit:

- `.secrets/`;
- site/database passwords;
- FBR tokens;
- database dumps/backups;
- generated `frappe-bench/` runtime contents;
- local logs unless intentionally curated as safe test evidence.

---

## 12. Common failure boundaries

### Bench missing or invalid

Run:

```bash
./install.sh --local
```

The installer reuses a valid bench and moves an incomplete bench aside only through its guarded path.

### ERPNext missing

Do not manually install Ledgix alone. Re-run the supported installer/site ensure path:

```bash
./install.sh --local
./site_setup.sh --ensure
```

### Site needs repair

Use:

```bash
./site_setup.sh --ensure
```

before considering any destructive reset.

### Assets stale

```bash
cd frappe-bench
bench build --app ledgix_saas
bench --site ledgix-erpnext.local clear-cache
```

### Need a clean site

Use the exact guarded reset command from section 5 only after deciding that local data may be destroyed.

---

## 13. Production boundary

Local setup scripts are not the production deployment contract.

For production use the active runbooks under:

```text
docs/production/
```

Start with `docs/production/DEPLOYMENT.md` and `docs/production/final_release_gate.md`.
