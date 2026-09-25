# Ledgix POS — Deployment and Upgrades

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Production release model:** immutable SHA/tag  
**Companion docs:** INSTALLATION_AND_CONFIGURATION.md, BACKUP_RESTORE_ROLLBACK.md, MULTI_SITE_SAAS.md, TESTING_AND_RELEASE_GATES.md

## 1. Purpose

This document defines the supported production deployment and upgrade model.

The governing rules are:

> **Production deploys an immutable Ledgix release, not a moving branch.**

and:

> **A shared bench is one shared application-code unit; all Ledgix tenants on that bench must move as an approved cohort.**

---

## 2. Production topology

Typical production path:

    Internet
      -> DNS / HTTPS
      -> Nginx
      -> Supervisor-managed Frappe services
      -> Frappe bench
          -> Frappe
          -> ERPNext
          -> ledgix_saas
      -> one Frappe site/database per client
      -> MariaDB / Redis / files

Use native Frappe multitenancy.

Do not run production through the local development runner.

---

## 3. Release identity

A production release must be:

- full 40-character Git commit SHA; or
- immutable Git tag resolving to one commit.

Moving branch names such as main are rejected by the current update tools.

The repository can use main as the development source branch, but Production approval records a specific immutable commit.

---

## 4. Release contract

Current stack contract is stored in:

    deploy/release_contract.env

Current pinned values include:

- ledgix_saas 15.0.1;
- Frappe 15.113.4;
- ERPNext 15.121.3;
- required major 15;
- migration closure gate SHA.

Production update fails closed when the installed framework stack does not match the target release contract.

---

## 5. Why Ledgix updates do not rewrite ERPNext

Existing-site Ledgix update scripts explicitly prohibit pulling/installing/replacing ERPNext during an ordinary Ledgix release.

ERPNext/Frappe are prerequisites.

If the framework version must change, treat that as a separate planned platform upgrade, not an incidental Ledgix update.

---

## 6. Fresh production provisioning

Use:

    deploy/production_setup.sh --action site

or:

    deploy/provision_client_site_safe.sh

with explicit:

- site;
- immutable release;
- URL where relevant.

Fresh provisioning installs ERPNext before Ledgix.

See INSTALLATION_AND_CONFIGURATION.md for configuration boundaries.

---

## 7. Single-site production update

Use:

    deploy/deploy_update_safe.sh \
      --site <site> \
      --release <approved-sha-or-tag> \
      --url https://<site>

This updater is deliberately restricted to a bench with one site.

If multiple sites exist, it fails and directs the operator to the shared-bench updater.

---

## 8. Single-site update preconditions

The updater requires:

- explicit site;
- explicit release;
- explicit URL;
- valid bench;
- passwordless sudo for service management;
- clean repository;
- target release resolvable;
- target release contract present;
- current Frappe/ERPNext matching target contract;
- Ledgix installed;
- client dependency preflight green.

Production URL can be HTTP/HTTPS for updater smoke, but final production acceptance requires HTTPS.

---

## 9. Single-site update sequence

Current safe updater performs:

1. validate target site/bench;
2. reject shared bench;
3. resolve immutable target;
4. record previous SHA;
5. create verified pre-update backup;
6. enable maintenance mode;
7. checkout approved release;
8. validate release contract;
9. verify exact framework versions;
10. run pre-mutation client preflight;
11. synchronize exact Ledgix app source;
12. build assets;
13. migrate site;
14. clear caches;
15. run post-migration client preflight;
16. run offline smoke;
17. refresh/restart production processes;
18. disable maintenance mode;
19. run online smoke;
20. write release evidence.

If online smoke fails, maintenance is re-enabled and the update fails closed.

---

## 10. Failure behavior

The update script leaves maintenance mode ON when it exits before success.

It prints the previous release and advises recovery from:

- verified pre-update backup;
- previous release identity.

This is intentional.

Do not blindly turn maintenance mode off just to make the site reachable.

---

## 11. Release evidence

Successful update writes owner-private release evidence under the site's private Ledgix release area.

Evidence includes items such as:

- release input;
- deployed SHA;
- framework versions;
- backup metadata;
- dependency preflight;
- offline smoke;
- online smoke.

This evidence is later consumed by strict release acceptance.

---

## 12. Shared-bench update

Use:

    deploy/deploy_update_shared_safe.sh

with:

- immutable release;
- every Ledgix tenant explicitly supplied as SITE=URL.

Example structure:

    deploy/deploy_update_shared_safe.sh \
      --release <sha-or-tag> \
      --site client-a.example.com=https://client-a.example.com \
      --site client-b.example.com=https://client-b.example.com

---

## 13. Shared cohort rule

The updater discovers every site on the bench using ledgix_saas.

The supplied approved cohort must exactly match that discovered set.

Partial shared-bench releases fail closed.

This prevents one tenant from running old schema against new shared code.

---

## 14. Shared release sequence

Current shared updater:

1. resolves immutable release;
2. loads target release contract;
3. discovers Ledgix tenant cohort;
4. requires exact cohort match;
5. validates each site's Frappe/ERPNext stack;
6. runs each site's preflight;
7. creates/verifies backup for every tenant;
8. places entire cohort in maintenance;
9. switches shared application code once;
10. builds shared Ledgix assets once;
11. migrates every tenant;
12. runs preflight/offline smoke for every tenant;
13. restarts shared processes once;
14. removes maintenance for full cohort;
15. runs online smoke for every tenant;
16. returns full cohort to maintenance if any online smoke fails;
17. records per-site release evidence with cohort digest.

---

## 15. Cohort digest

Shared updater records a SHA-256 digest of the approved cohort.

This creates evidence that each site moved as part of the same explicit release group.

The digest is not a substitute for per-site backup/release evidence.

---

## 16. Adding a tenant to an existing shared bench

Fresh provisioning checks whether existing Ledgix tenants are present.

If they are:

- each existing tenant must have immutable release evidence;
- each must match the requested release;
- current bench Ledgix app must exactly match that release.

If not, update the existing cohort first.

Do not let "add a tenant" silently become "upgrade every tenant."

---

## 17. Different client versions

Two clients requiring different Ledgix revisions must not share the same bench.

Use:

- separate bench;
- separate host if appropriate.

Do not create per-client Git forks.

The product is designed for configuration differences, not code forks.

---

## 18. Maintenance mode

Production upgrade tools deliberately use maintenance mode.

Maintenance protects against:

- writes during schema migration;
- mixed old/new code interaction;
- user operations during release switch.

If a release aborts, leaving maintenance on is safer than reopening an inconsistent site.

---

## 19. Asset build

Single-site update performs build after application sync.

Shared update builds once for the shared bench.

Do not repeatedly build per tenant when code is shared unless a specific architecture change requires it.

---

## 20. Cache refresh

After migrate, current update tooling clears:

- Frappe cache;
- website cache.

This prevents stale metadata/assets from masking a successful migration.

---

## 21. Process restart

Production tooling refreshes shared services after build/migrate.

Current service model uses Supervisor.

Typical managed groups include web and workers.

Do not replace production process management with bench start.

---

## 22. Offline smoke

Offline smoke validates the site/application without depending on public routing.

It is used before reopening service.

A passing offline smoke does not prove DNS/HTTPS/reverse-proxy health.

---

## 23. Online smoke

Online smoke validates the public URL after maintenance is lifted.

If it fails:

- single-site updater re-enables maintenance;
- shared updater returns entire cohort to maintenance.

This preserves fail-closed release behavior.

---

## 24. Preflight before and after migrate

Current updater runs client dependency preflight before mutation and again after migrate.

This verifies the release did not leave the site in a broken dependency/application state.

---

## 25. Backup before every update

Every production update creates a verified backup before code movement.

Do not bypass this just because the release appears "small" or "docs only" if the deployment tooling will mutate site state.

See BACKUP_RESTORE_ROLLBACK.md.

---

## 26. Rollback identity

Before updating, record:

- previous release SHA;
- target release SHA;
- backup metadata.

This gives the operator a coherent rollback pair:

    previous app release + pre-update site recovery set

Rollback should not guess which database snapshot matches which code.

---

## 27. Framework upgrades

A Frappe/ERPNext version upgrade is a separate change class.

Because release_contract pins exact supported versions, a Ledgix release that changes those versions should include:

- explicit updated release contract;
- compatibility testing;
- backup/restore validation;
- migration tests;
- deployment-runbook review.

Do not allow Ledgix updater to opportunistically run bench update against ERPNext.

---

## 28. Schema upgrades

Ledgix schema changes arrive through:

- current DocType JSON;
- after_migrate synchronizers;
- registered patches.

Run migrate after the approved release is installed.

Do not run arbitrary historical migration scripts directly unless the current documented procedure explicitly requires them.

---

## 29. Patch execution

Frappe runs registered patches from patches.txt under normal migration semantics.

Do not assume unregistered patch files execute.

Do not invoke a patch as a normal production API.

---

## 30. Legacy retirement during migrate

After-migrate ordering ends with legacy-retirement synchronization.

If a migrated site is already Frozen:

- read-only legacy permissions are reapplied;
- frozen historical Ledgix business data must remain immutable.

An upgrade must not reopen old ledgers.

---

## 31. FBR during deployment

Normal deployment does not authorize FBR Production.

Deploy/update must not:

- arm Production;
- change Sandbox certification to complete;
- fabricate token presence;
- send live FBR POST;
- resolve reconciliation automatically.

FBR activation is a separate go-live workflow.

---

## 32. Final production release gate

After deployment, run the audit-only final gate:

    bash scripts/run_ledgix_production_release_gate.sh \
      --site <site> \
      --url https://<site> \
      --release <approved-release>

Add --require-fbr-production only when FBR Production is genuinely part of go-live.

This gate does not deploy or make FBR network calls.

---

## 33. Final gate HTTPS requirement

Unlike the updater, the final production release gate requires:

    https://

This makes HTTPS part of final production acceptance.

---

## 34. Repository cleanliness

Production release tooling expects a clean repository.

Uncommitted local changes destroy immutable release confidence.

Do not deploy from an unknown dirty state.

---

## 35. Production secrets

Do not place deployment secrets in:

- Git;
- release evidence intended for broad sharing;
- scripts;
- commit messages.

Per-site credentials remain external and owner-only.

---

## 36. Upgrade checklist

- [ ] target immutable SHA/tag approved;
- [ ] repository clean;
- [ ] target release contract inspected;
- [ ] current framework versions match contract;
- [ ] tenant scope identified;
- [ ] single-site vs shared-bench updater chosen correctly;
- [ ] preflight green;
- [ ] verified backup created;
- [ ] rollback release known;
- [ ] maintenance enabled before code/schema mutation;
- [ ] approved release synced exactly;
- [ ] build successful;
- [ ] migrate successful;
- [ ] preflight re-run;
- [ ] offline smoke green;
- [ ] services restarted correctly;
- [ ] online smoke green;
- [ ] release evidence written;
- [ ] final release gate run separately;
- [ ] FBR Production state unchanged unless separately approved.

---

## 37. Anti-patterns

Do not:

- git pull main directly in production and call it a release;
- update only one tenant's schema on shared code;
- skip backup;
- deploy from dirty worktree;
- use bench update to alter ERPNext implicitly;
- run local installer as production update mechanism;
- exit maintenance after failed smoke without diagnosis;
- use a host snapshot as the only site rollback evidence;
- activate FBR Production as a deployment side effect.

---

## 38. Source map

| Concern | Current source |
|---|---|
| Production wrapper | deploy/production_setup.sh |
| Single-site update | deploy/deploy_update_safe.sh |
| Shared-bench update | deploy/deploy_update_shared_safe.sh |
| Fresh site provision | deploy/provision_client_site_safe.sh |
| Release contract | deploy/release_contract.env |
| Smoke | deploy/smoke_test.sh |
| Status | deploy/status.sh |
| Client preflight | scripts/run_ledgix_client_preflight.sh |
| Final release gate | scripts/run_ledgix_production_release_gate.sh |

---

## 39. Summary

> **Ledgix production releases are immutable, backup-first and fail-closed; single-site benches update independently, shared benches move as complete approved tenant cohorts, and deployment never silently upgrades ERPNext or activates FBR Production.**
