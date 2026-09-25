# Ledgix POS — Multi-Site SaaS

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Tenancy model:** native Frappe site isolation

## 1. Purpose

This document defines the Ledgix multi-client SaaS model.

The central rule is:

> **One client = one Frappe site/database; one shared bench = one shared Ledgix application revision.**

Client differences belong in configuration and data, not code forks.

---

## 2. Tenant architecture

Typical shared-bench topology:

    shared host / bench
      ├── client-a.example.com
      │     -> own DB
      │     -> own site config
      │     -> own files
      │     -> own users/roles
      │     -> own Business Profile
      │     -> own FBR profile/tokens/evidence
      │
      ├── client-b.example.com
      │     -> own DB
      │     -> own site config
      │     -> own files
      │     -> own users/roles
      │     -> own Business Profile
      │     -> own FBR profile/tokens/evidence
      │
      └── shared apps/
            -> frappe
            -> erpnext
            -> ledgix_saas

---

## 3. Per-site isolation

Each client site has independent:

- database;
- site_config;
- encryption key;
- files/private files;
- Users/Roles/User Permissions;
- Company;
- accounting configuration;
- Warehouses;
- Customers/Suppliers/Items;
- POS Profiles;
- Business Profile;
- FBR Integration Profile;
- FBR tokens;
- FBR Submission Logs;
- Sandbox certification;
- backups;
- release evidence.

Do not share these between clients.

---

## 4. Shared code

All Ledgix sites on one bench use the same:

    apps/ledgix_saas

Changing this code changes runtime for every Ledgix tenant on the bench.

That is why a shared bench cannot safely deploy a new Ledgix release to only one tenant.

---

## 5. No client forks

Ledgix supports different client use cases through Business Profiles/configuration.

Supported profile presets include:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

Do not create:

- client-a branch;
- client-b branch;
- bespoke Ledgix app copy per client.

If genuine release divergence is required, separate the benches.

---

## 6. Different releases require different benches

If client A must remain on release X while client B moves to release Y:

- they cannot safely share the same bench application directory.

Move one client to:

- separate bench; or
- dedicated host.

This preserves one-revision-per-bench consistency.

---

## 7. Tenant provisioning

Add a new client using:

    deploy/provision_client_site_safe.sh

or:

    deploy/production_setup.sh --action site

The new tenant receives:

- own database;
- own site config/secrets;
- ERPNext installed before Ledgix;
- same approved Ledgix release as existing bench cohort when joining shared bench.

---

## 8. Shared-code reuse check

When provisioning onto a bench with existing Ledgix tenants, the provisioner verifies:

- existing tenants have immutable release evidence;
- recorded release equals requested target;
- actual shared application code matches target exactly.

If not, provisioning fails.

This prevents a tenant add from changing code under existing tenants.

---

## 9. Shared-bench release

Use:

    deploy/deploy_update_shared_safe.sh

Every Ledgix site on the bench must be listed explicitly in the approved cohort.

Partial cohorts fail.

---

## 10. Cohort discovery

The updater discovers sites using ledgix_saas.

The approved list must exactly match this discovered set.

This prevents:

- forgotten tenant;
- accidental partial migration;
- mixed schema/code state.

---

## 11. Shared release maintenance sequence

Before shared code changes:

- preflight every tenant;
- backup every tenant;
- place every tenant in maintenance.

Only then change shared code/build.

This ensures no tenant keeps serving against incompatible shared code during another tenant's migration.

---

## 12. Build once, migrate each site

Shared application assets are built once.

Database/schema migration is per-site.

Therefore sequence is:

    switch shared code
      -> build once
      -> migrate client A
      -> migrate client B
      -> ...
      -> verify all
      -> restart shared services once

---

## 13. Failure behavior

If any tenant fails online smoke after shared release:

- the updater returns the full cohort to maintenance.

This is safer than leaving some tenants live on a release whose cohort verification failed.

---

## 14. Per-site backup

Before shared release, every tenant receives its own verified recovery set.

A single host snapshot is not sufficient.

Each site needs:

- DB;
- public files;
- private files;
- site config recovery input;
- checksums;
- release metadata.

---

## 15. Per-site release evidence

Shared update writes per-site evidence.

It includes:

- deployed release;
- shared-bench marker;
- common cohort digest;
- site-specific backup metadata;
- preflight/smoke results.

The cohort digest proves common release scope.

Site evidence proves individual recovery/validation.

---

## 16. FBR isolation

FBR is per site/company.

Never share across tenants:

- Sandbox token;
- Production token;
- seller identity;
- provider configuration;
- Submission Logs;
- Sandbox Certification;
- official accepted invoice state.

A shared application release does not mean shared FBR configuration.

---

## 17. Business data isolation

Do not attempt to use one Company's master records as another client's SaaS database.

Each client site contains its own ERPNext business universe.

This simplifies:

- permissions;
- backups;
- legal separation;
- FBR identity;
- client export/removal;
- performance scaling.

---

## 18. User isolation

Users are site records.

A login on one client site does not automatically authorize another site.

Cross-site identity federation is not part of the current Ledgix architecture.

If added later, it must not collapse business-data isolation.

---

## 19. Tenant onboarding

After provisioning:

1. configure native ERPNext Company/accounting;
2. configure warehouses/pricing/payments;
3. configure client masters;
4. select Business Profile;
5. validate client readiness;
6. configure FBR only if applicable;
7. perform profile-specific UAT;
8. capture release acceptance evidence.

Infrastructure creation alone is not client onboarding completion.

---

## 20. Tenant removal

Tenant deletion is intentionally not automated by the shared updater.

Before removal:

1. stop new business activity;
2. take fresh per-site backup;
3. verify checksums;
4. retain exact app release identity;
5. retain protected off-host copy;
6. confirm accounting/FBR/legal retention;
7. then use the normal deliberate Frappe site-removal process.

Removing a site must not modify another tenant's DB/files.

---

## 21. Tenant restore

Restore a tenant using the per-site recovery contract.

Where practical, prove the backup first on a non-production recovery target.

After restore:

- run dependency preflight;
- run offline smoke;
- verify native ERPNext/Ledgix reads;
- verify Phase 12 frozen snapshot for migrated sites;
- verify FBR state;
- run online smoke before reopening.

---

## 22. Moving a tenant to dedicated infrastructure

A larger client can move to a separate bench/host without changing application architecture.

Migration uses:

- verified backup;
- matching release;
- restore;
- site/domain configuration;
- smoke/readiness.

No code fork is needed.

---

## 23. Domain routing

Each site should have its own hostname.

Nginx/Frappe host routing maps request Host to the appropriate site.

Wrong hostname/site mapping can produce:

- 404;
- wrong site;
- failed public smoke.

Keep DNS, Nginx config and Frappe site directory aligned.

---

## 24. HTTPS

Production tenants should use HTTPS.

Final production acceptance explicitly requires an HTTPS URL.

Do not activate sensitive live integrations over an unapproved insecure public path.

---

## 25. Redis / MariaDB

Shared infrastructure can use common service instances where appropriate, but:

- each Frappe site has its own database;
- DB credentials remain site-specific;
- service endpoints should not be publicly exposed.

Infrastructure sharing does not collapse application/data tenancy.

---

## 26. Shared scheduler

Each site can have scheduler enabled for normal Frappe/ERPNext operation.

Ledgix FBR retransmission safety does not rely on a generic retry scheduler.

Do not confuse normal site scheduler enablement with FBR auto-retry.

---

## 27. Backup storage organization

Organize backups per tenant/site.

Avoid one unstructured directory where client backup sets can be confused.

Metadata --site verification should be used before restore.

---

## 28. Release staggering

Within one bench, Ledgix application release cannot be safely staggered tenant-by-tenant.

The whole Ledgix cohort moves together.

If the business requires staggered releases, separate benches are required.

---

## 29. Observability

At minimum, operations should be able to determine per site:

- current release;
- installed app versions;
- maintenance state;
- public URL health;
- last verified backup;
- client readiness;
- FBR mode/status where enabled.

Do not rely only on host-level "server up" health.

---

## 30. Security

Tenant isolation requires:

- separate site secrets;
- separate DB;
- separate backup;
- separate FBR credentials;
- proper filesystem permissions;
- no accidental cross-company/site lookups in custom code.

See SECURITY_AND_PERMISSIONS.md.

---

## 31. Local development boundary

The developer workstation intentionally uses one canonical local site.

Local development does not need to simulate many tenants for ordinary work.

Multi-site behavior is enforced through:

- production tooling;
- shared-bench static contracts;
- release tests.

Use dedicated multi-site test environments only when changing tenancy logic.

---

## 32. New SaaS feature checklist

Before adding a tenant-sensitive feature:

- [ ] data naturally belongs to one site;
- [ ] Company scoping exists where needed inside site;
- [ ] no global filesystem secret shared between tenants;
- [ ] backup/restore captures feature state;
- [ ] feature works on fresh site;
- [ ] feature works on migrated site;
- [ ] release does not require client-specific code fork;
- [ ] shared-bench deployment remains cohort-safe;
- [ ] FBR/client legal data remains isolated.

---

## 33. Anti-patterns

Do not:

- put multiple unrelated clients into one site just to save setup effort;
- share one FBR token between sites;
- deploy different Ledgix commits to sites sharing one bench;
- update one shared tenant's app code independently;
- store per-client secrets in repository source;
- make per-client application branches;
- delete a tenant without verified backup/retention approval;
- restore one client's backup into another live client site.

---

## 34. Source map

| Concern | Current source |
|---|---|
| Tenant provisioning | deploy/provision_client_site_safe.sh |
| Shared update | deploy/deploy_update_shared_safe.sh |
| Single-site update | deploy/deploy_update_safe.sh |
| Backup | deploy/backup_safe.sh |
| Recovery proof | deploy/restore_drill.sh |
| Business Profile | api/client_setup.py / api/product_shell.py |
| Site isolation | Frappe multitenancy |

---

## 35. Summary

> **Ledgix SaaS uses Frappe's one-site/one-database client isolation and one shared application revision per bench; client differences are configuration, shared-bench releases move as an all-tenant cohort, and any client needing a different Ledgix revision must move to a separate bench rather than fork the product.**
