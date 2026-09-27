# Ledgix Local Installation and Development

**Status:** CURRENT  
**Canonical local site:** `ledgix-erpnext.local`  
**Required stack:** Frappe v15 -> ERPNext v15 -> `ledgix_saas` -> `fbr_v1`

## Purpose

This is the supported local setup path for the current ERPNext-core Ledgix repository.

Older instructions that create arbitrary Ledgix-only sites or install `ledgix_saas` without ERPNext are obsolete.

---


Ledgix is not treated as a standalone business application separate from
ERPNext. The supported product/runtime is one combined stack:

Frappe -> ERPNext -> ledgix_saas -> fbr_v1

Frappe and ERPNext keep their upstream Git histories, while Ledgix-owned
application source is tracked by this repository directly under
`frappe-bench/apps/`. There is no duplicate outer `apps/` source tree.

## 1. Repository layout

Typical local checkout:

```text
~/data_drive/ledgix-pos/
├── scripts/core/install.sh
├── scripts/core/site_setup.sh
├── start.sh
├── frappe-bench/apps/ledgix_saas/
├── frappe-bench/apps/fbr_v1/
├── frappe-bench/apps/fbr_v12/              # frozen source reference; not an active local integration
├── deploy/
├── docs/
└── frappe-bench/        # generated/reused locally; not committed
```

The Ledgix runtime is the combined Frappe -> ERPNext -> ledgix_saas -> fbr_v1 stack. Ledgix-owned source is edited directly under `frappe-bench/apps/`; no duplicate outer source tree or app-sync step exists.

---

## 2. First-time setup

From the repository root:

```bash
cd ~/data_drive/ledgix-pos
chmod +x scripts/core/*.sh deploy/*.sh
./scripts/core/install.sh --local
```

The installer:

- performs a local preflight;
- installs/reuses required Ubuntu packages;
- prepares Node/Yarn and Bench tooling;
- creates or reuses a valid Frappe v15 bench;
- ensures ERPNext v15 is present in the bench;
- validates Frappe/ERPNext branch alignment;
- leaves site creation to `scripts/core/site_setup.sh`.

`scripts/core/install.sh` does **not** start the development server as part of installation.

### Sudo behavior

The installer prefers non-interactive/passwordless sudo. On a trusted local machine only, interactive sudo can be explicitly allowed:

```bash
ALLOW_INTERACTIVE_SUDO=1 ./scripts/core/install.sh --local
```

Do not copy that convention into unattended production automation.

---

## 3. Canonical local site

Create or repair the supported integration site:

```bash
./scripts/core/site_setup.sh --ensure
```

Default site:

```text
ledgix-erpnext.local
```

The site stack is always:

```text
Frappe -> ERPNext -> ledgix_saas -> fbr_v1
```

There is no local app-selection menu. ERPNext is a required dependency of Ledgix.

Check state with:

```bash
./scripts/core/site_setup.sh --status
```

---

## 4. What `--ensure` may do

`site_setup.sh --ensure` is the normal safe repair/create path. It can:

- create the canonical local site when none exists;
- ensure ERPNext exists in the bench and is installed on the site;
- validate the canonical Ledgix app directly under `frappe-bench/apps/` and ensure its editable installation;
- install `ledgix_saas` if missing;
- install `fbr_v1` if missing, after ERPNext;
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
./scripts/core/site_setup.sh --reset \
  --site ledgix-erpnext.local \
  --confirm "RESET ledgix-erpnext.local"
```

The reset path requires the exact confirmation phrase.

**Do not use reset as a routine fix for the completed acceptance dataset.** The current `LEDGIX-RETAIL-OPERATING-V1` dataset is verified operating/acceptance data and should not be casually rebuilt. See `docs/operations/LOCAL_DEMO_DATA.md` first.

---

## 6. Start and stop development runtime

Start the local development runtime:

```bash
./scripts/core/start.sh
```

Useful runner actions include:

```bash
./scripts/core/start.sh --status
./scripts/core/start.sh --background
./scripts/core/start.sh --stop
./scripts/core/start.sh --smoke --site ledgix-erpnext.local
```

`scripts/core/start.sh` is for development/local process management only. It is not the production Supervisor/Nginx service workflow.

Expected URL:

```text
http://ledgix-erpnext.local:8000
```

If local hostname resolution is missing, `scripts/core/start.sh` can report/add the required `/etc/hosts` mapping interactively. Under WSL, Windows-side host resolution may also need configuration.

---

## 7. Verify the installed stack

From the bench:

```bash
cd ~/data_drive/ledgix-pos/frappe-bench
bench --site ledgix-erpnext.local list-apps
bench version --format plain
```

The site must include:

```text
frappe
erpnext
ledgix_saas
fbr_v1
```

ERPNext must not be omitted.

Run the client dependency preflight when appropriate:

```bash
cd ~/data_drive/ledgix-pos
bash scripts/local/run_ledgix_client_preflight.sh ledgix-erpnext.local
```

---

## 8. Common development commands

```bash
cd ~/data_drive/ledgix-pos/frappe-bench

bench --site ledgix-erpnext.local migrate
bench --site ledgix-erpnext.local clear-cache
bench --site ledgix-erpnext.local clear-website-cache
bench --site ledgix-erpnext.local console
bench build --app ledgix_saas
```

Run repository validation from the repository root:

```bash
bash scripts/validation/ci_local.sh
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

Local operating data deliberately keeps both Federal V1 network gates disabled. Do not install `fbr_v12` alongside `fbr_v1` as an active integration.

Do not add real Production credentials to the local acceptance dataset and do not fabricate Sandbox success evidence.

Current FBR documentation:

```text
docs/fbr/fbr_v1/FBR_V1_RUNTIME_ARCHITECTURE.md
docs/fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md
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
./scripts/core/install.sh --local
```

The installer reuses a valid bench and moves an incomplete bench aside only through its guarded path.

### ERPNext missing

Do not manually install Ledgix alone. Re-run the supported installer/site ensure path:

```bash
./scripts/core/install.sh --local
./scripts/core/site_setup.sh --ensure
```

### Site needs repair

Use:

```bash
./scripts/core/site_setup.sh --ensure
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
