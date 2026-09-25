# Ledgix POS — Installation and Configuration

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Supported stack:** Frappe v15 + ERPNext v15 + ledgix_saas  
**Release contract source:** deploy/release_contract.env

## 1. Purpose

This document defines the supported installation and initial configuration model for Ledgix POS.

It covers:

- local development installation;
- current dependency/version expectations;
- canonical local-site management;
- fresh production-site provisioning boundaries;
- Ledgix app installation order;
- current setup/configuration responsibilities;
- secrets handling;
- migration/build expectations;
- what installation must never do automatically.

The core rule is:

> **Ledgix is installed on top of ERPNext. A Frappe-only Ledgix business site is not a supported current architecture.**

---

## 2. Supported application stack

Current application order is:

    Frappe
      -> ERPNext
      -> ledgix_saas

hooks.py declares ERPNext as a required app.

pyproject.toml constrains the current app to Frappe/ERPNext v15.

The production release contract currently pins:

- Ledgix app: ledgix_saas;
- Ledgix expected app version: 15.0.1;
- Frappe: 15.113.4;
- ERPNext: 15.121.3;
- required Frappe major: 15;
- required ERPNext major: 15;
- ERPNext migration closure gate SHA: d813d26d16a11665522da98c7bd542a7cc09c53f.

These values must be updated deliberately through the release contract when the supported stack changes.

---

## 3. Repository layout

Typical checkout:

    <repo-root>/
    ├── install.sh
    ├── site_setup.sh
    ├── start.sh
    ├── apps/
    │   └── ledgix_saas/
    ├── deploy/
    ├── scripts/
    ├── docs/
    └── frappe-bench/      # generated/reused runtime bench

Repository application source lives in:

    apps/ledgix_saas/

The local bench copy is synchronized from the repository source through the supported local tooling.

Do not treat generated bench runtime content as the source repository.

---

## 4. Local installation entrypoint

Supported local install command:

    ./install.sh --local

The installer performs:

- preflight;
- system dependency setup;
- Node/Yarn setup;
- Bench CLI setup;
- Frappe v15 bench creation/reuse;
- ERPNext v15 dependency preparation;
- Frappe/ERPNext branch alignment checks.

It intentionally leaves site creation/repair to site_setup.sh.

---

## 5. Local dependency installation

install.sh can install or verify dependencies such as:

- Git;
- curl;
- build tools;
- Python development tooling;
- Redis;
- MariaDB;
- Node through NVM;
- Yarn;
- Bench CLI;
- relevant native libraries.

It also verifies MariaDB/Redis service availability for local development.

This is a local/dev convenience path.

Do not blindly transplant its interactive sudo behavior into unattended production automation.

---

## 6. Local Bench creation

The installer creates/reuses:

    frappe-bench/

A bench is considered valid only when expected Frappe/runtime directories and files exist.

If an existing bench is incomplete, the script uses a guarded move-aside/recreate path instead of pretending it is healthy.

ERPNext is then fetched/reused in the bench and registered as a bench app.

---

## 7. Frappe / ERPNext branch alignment

Local install expects the configured Frappe/ERPNext v15 branch policy.

If the apps are on unexpected branches, the installer fails rather than silently mixing unsupported framework lines.

Detached HEAD can be tolerated diagnostically but should be understood explicitly.

---

## 8. Canonical local site

Default local integration site:

    ledgix-erpnext.local

Supported site manager:

    ./site_setup.sh

Common actions:

    ./site_setup.sh --ensure
    ./site_setup.sh --status

The local site must end with .local or .localhost.

The local site manager refuses production-style domains.

---

## 9. Local ensure behavior

site_setup.sh --ensure can:

- validate bench runtime;
- ensure ERPNext exists in the bench;
- synchronize repository Ledgix source into bench app path;
- install ERPNext on the site if missing;
- install ledgix_saas if missing;
- enable local developer mode;
- run bench migrate;
- build Ledgix assets;
- set the canonical site as active;
- save local credentials outside Git.

It is intended as the normal repair/create path.

It is not intended to delete existing business data.

---

## 10. Local single-site policy

The local site manager intentionally prefers one active local site.

If multiple active local sites exist, --ensure fails rather than choosing one arbitrarily.

If a different local site exists instead of the configured canonical site, ensure also fails rather than silently deleting or replacing it.

This makes destructive standardization explicit.

---

## 11. Local reset

Destructive reset requires:

    ./site_setup.sh \
      --reset \
      --site ledgix-erpnext.local \
      --confirm "RESET ledgix-erpnext.local"

The exact confirmation phrase is required.

The reset path:

- removes active local .local/.localhost sites only;
- refuses non-local domains;
- archives old local site folders;
- recreates one clean canonical site.

Do not use this as a routine troubleshooting shortcut.

---

## 12. Local credentials

Local development deliberately uses simple local-only credential conventions.

site_setup.sh can store generated/current local credentials under:

    .secrets/sites/<site>.env

The directory is outside the committed source contract.

Local password conventions must never be copied into production.

---

## 13. Local development runtime

Use:

    ./start.sh

Typical actions include:

    ./start.sh --status
    ./start.sh --background
    ./start.sh --stop
    ./start.sh --smoke --site ledgix-erpnext.local

This is a development runtime.

Do not use start.sh / bench start as the production process-management model.

---

## 14. Local verification

From the bench:

    bench --site ledgix-erpnext.local list-apps
    bench version --format plain

Expected site stack includes:

- frappe;
- erpnext;
- ledgix_saas.

Run client dependency preflight where appropriate:

    bash scripts/run_ledgix_client_preflight.sh ledgix-erpnext.local

---

## 15. Repository validation

Basic local CI entrypoint:

    bash scripts/ci_local.sh

Current ci_local.sh runs:

- ERPNext dependency validation;
- repository secret scan.

Focused subsystem tests/gates should also be run for changed areas.

ci_local alone is not the complete final release gate.

---

## 16. Migration after installation

Current Ledgix relies on after_migrate synchronization for:

- ERPNext extension fields;
- tax foundation;
- migration-era current extension schema;
- print formats;
- permissions;
- product shell;
- frozen legacy retirement enforcement.

Therefore a supported install/upgrade runs:

    bench --site <site> migrate

after the correct app version is in place.

Migration must not be skipped casually.

---

## 17. Asset build

After app synchronization/migration, build assets using the supported path, e.g.:

    bench build --app ledgix_saas

or the production updater's build sequence.

Do not assume source changes are available to browser pages without a matching asset build/cache refresh when the change affects assets.

---

## 18. Fresh production site provisioning

Use the production tooling, not the local site manager.

Primary safe provisioner:

    deploy/provision_client_site_safe.sh

Canonical wrapper:

    deploy/production_setup.sh --action site

Required production inputs include:

- explicit site;
- immutable release SHA/tag;
- optional/required URL depending on wrapper path.

---

## 19. Production immutable release

Production provisioning does not follow a moving branch.

A release must resolve to:

- full 40-character commit SHA; or
- immutable tag.

Moving branch names such as main are not accepted as production release identity.

---

## 20. Fresh production provisioning order

The safe provisioner:

1. resolves approved immutable release;
2. validates release contract;
3. validates shared-bench compatibility if existing Ledgix tenants exist;
4. validates Frappe/ERPNext versions;
5. creates isolated database/site credentials;
6. creates Frappe site;
7. installs ERPNext;
8. installs Ledgix;
9. migrates;
10. builds Ledgix assets;
11. enables scheduler for normal Frappe/ERPNext operation;
12. clears cache;
13. optionally sets host_name;
14. runs dependency preflight;
15. runs offline smoke;
16. stores owner-only secrets outside repository;
17. records provisioning evidence.

---

## 21. Production secrets

Fresh production provisioning generates strong credentials.

Default external per-site storage:

    ~/.config/ledgix/sites/<site>.env

This file is outside the Git repository and should be owner-only.

Never commit:

- Administrator password;
- database password;
- site_config.json;
- FBR tokens;
- API/private keys;
- backup files;
- encryption material.

---

## 22. Shared-bench provisioning safety

If existing Ledgix tenants already share the bench, provisioning a new tenant is permitted only when:

- existing tenant release evidence exists;
- every existing Ledgix tenant records the same target immutable release;
- current shared app code exactly matches the requested release.

If not, first update the full shared cohort using the shared-bench updater.

Adding a new tenant must not silently switch shared code.

---

## 23. What fresh provisioning does not configure

Fresh provisioning intentionally does not create client business masters.

It does not automatically create/configure:

- client Company;
- Chart of Accounts;
- Customer/Supplier masters;
- Items;
- Warehouses;
- payment accounts;
- POS Profile;
- Price Lists;
- tax accounts;
- client FBR legal identity.

These are business onboarding/configuration concerns.

---

## 24. What fresh provisioning does not activate

Provisioning does not:

- apply a Business Profile automatically;
- activate FBR Production;
- mark Sandbox certified;
- arm Production posting;
- fabricate external evidence.

Provisioning evidence explicitly records:

    fbr_production_activated=0

---

## 25. Native ERPNext prerequisites

Before normal client operation, configure appropriate ERPNext prerequisites.

Depending on Business Profile, these can include:

- Company;
- Chart of Accounts;
- default currency/country;
- accounting defaults;
- Selling Price List;
- Buying Price List;
- Item Groups / Items;
- Warehouses;
- Modes of Payment;
- Mode of Payment Company accounts;
- Customers;
- Suppliers;
- tax accounts/templates;
- POS Profile;
- default/walk-in customer.

The exact requirements depend on the client's selected profile.

---

## 26. Business Profile configuration

Ledgix supports one codebase across five profile presets:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

The setup API validates profile-specific prerequisites.

It does not create duplicate business masters.

Business Profile changes product exposure/configuration, not core transaction authority.

---

## 27. Setup Wizard

Current setup surface is available through the Ledgix setup Page.

It should be used after native ERPNext prerequisites exist.

Its responsibilities include:

- selecting/applying Ledgix Business Profile;
- validating client readiness;
- storing Ledgix setup metadata/configuration;
- exposing blockers.

It must not silently invent missing ERPNext business data.

---

## 28. FBR configuration

FBR configuration is separate from application installation.

If FBR is enabled for the selected Business Profile, configure:

- Company-scoped Integration Profile;
- seller legal identity;
- provider/integrator metadata;
- Business Nature/Sector;
- Item mappings;
- Tax Component mappings;
- official reference data;
- Sandbox token;
- certification scenarios/evidence.

Do not configure Production mode/arm simply because Ledgix installed successfully.

---

## 29. Local FBR safety

The canonical local acceptance dataset intentionally keeps FBR transport disabled by default.

Real FBR Sandbox network exercise uses an explicit special workflow.

Never store Production credentials in the local demo/acceptance contract.

Never fabricate certification evidence.

---

## 30. Installation and permissions

After migrate, current permission synchronizers apply Ledgix Page/Report/DocType policy.

Legacy frozen business DocTypes receive a separate read-only retirement policy once the site is frozen.

Developers must consider both:

- centralized permission policy;
- retirement-specific post-migrate enforcement.

See SECURITY_AND_PERMISSIONS.md.

---

## 31. Installation and legacy sites

A migrated historical site may contain:

- frozen Ledgix legacy business DocTypes;
- Legacy Retirement State;
- migration provenance fields;
- old historical rows.

Fresh sites can still receive the relevant schema but may have no historical rows.

Installation logic must be safe for both.

---

## 32. Installation and patches

Registered Frappe patches are defined by:

    apps/ledgix_saas/patches.txt

Do not assume every file under patches/ runs automatically.

Do not manually call historical patch modules from normal runtime endpoints.

---

## 33. Installation anti-patterns

Do not:

- install ledgix_saas as the only business app on a Frappe-only production site;
- deploy a moving branch to production;
- copy local weak credentials to production;
- manually copy site_config between clients;
- share FBR tokens across sites;
- skip migrate after schema-changing release;
- run production with bench start;
- create client business masters automatically during site provisioning;
- activate Production FBR during installation;
- revive frozen legacy ledgers.

---

## 34. Local install verification checklist

- [ ] repository clean enough for intended work;
- [ ] Frappe bench valid;
- [ ] ERPNext present;
- [ ] Frappe/ERPNext aligned to supported major/version policy;
- [ ] ledgix_saas installed;
- [ ] canonical local site exists;
- [ ] migrate passes;
- [ ] asset build passes;
- [ ] dependency preflight passes;
- [ ] smoke passes;
- [ ] secrets remain ignored/outside Git.

---

## 35. Production provision verification checklist

- [ ] site/domain explicitly approved;
- [ ] immutable release resolved;
- [ ] release contract matches bench versions;
- [ ] site/database isolated;
- [ ] strong secrets generated;
- [ ] ERPNext installed before Ledgix;
- [ ] migrate/build completed;
- [ ] dependency preflight green;
- [ ] offline smoke green;
- [ ] online smoke green when URL supplied;
- [ ] provisioning evidence written;
- [ ] credentials stored outside repository;
- [ ] FBR Production remains inactive;
- [ ] client business onboarding still pending/explicit.

---

## 36. Source map

| Concern | Current source |
|---|---|
| Local installer | install.sh |
| Local site manager | site_setup.sh |
| Local runtime | start.sh |
| Production wrapper | deploy/production_setup.sh |
| Production provisioner | deploy/provision_client_site_safe.sh |
| Release contract | deploy/release_contract.env |
| ERPNext dependency preflight | scripts/validate_erpnext_dependency.sh / run_ledgix_client_preflight.sh |
| App runtime hooks | apps/ledgix_saas/hooks.py |
| Client setup | apps/ledgix_saas/api/client_setup.py |
| Client readiness | apps/ledgix_saas/api/client_readiness.py |

---

## 37. Summary

> **Install Frappe, then ERPNext, then Ledgix; use one canonical local site for development, immutable release-pinned tooling for production, and keep business onboarding/FBR activation as explicit post-install configuration rather than automatic side effects of provisioning.**
