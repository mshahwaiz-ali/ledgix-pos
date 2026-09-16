# Ledgix Multi-Site SaaS Operations

Ledgix uses native Frappe multitenancy with one shared application codebase and strict per-site business isolation.

## Architecture

- one site per client;
- one database per site;
- independent site configuration and secrets;
- independent Company/POS/Warehouse configuration;
- independent Business Profile;
- per-site FBR credentials and environment;
- per-site backup and release evidence;
- the same Ledgix application revision for every Ledgix tenant that shares one bench;
- no client fork.

If two clients must run different Ledgix application revisions, they must not share the same bench. Move one client to a separate bench or dedicated host instead of branching the product per client.

## Shared-bench release rule

A shared application directory changes code for every site using that app. Therefore a single-site migration is not a safe way to update one Ledgix tenant on a shared bench.

`deploy/deploy_update_safe.sh` is intentionally restricted to single-site benches.

For a bench containing multiple Ledgix tenants, use:

```bash
deploy/deploy_update_shared_safe.sh \
  --release <approved-immutable-sha-or-tag> \
  --site client-a.example.com=https://client-a.example.com \
  --site client-b.example.com=https://client-b.example.com
```

Every Ledgix-consuming site discovered on that bench must be present in the explicit approved full cohort. Partial cohorts fail closed.

## Shared release sequence

The shared-bench updater performs this order:

1. resolve the immutable target release;
2. discover every site using `ledgix_saas`;
3. require the approved site list to exactly match that tenant set;
4. run per-site dependency preflight;
5. create and verify a per-site backup for every tenant;
6. put the full cohort into maintenance mode;
7. switch the repository/application to the approved release once;
8. build the shared Ledgix assets once;
9. migrate every approved site;
10. run per-site dependency and offline smoke checks;
11. restart shared processes once;
12. remove maintenance for the full cohort;
13. run online smoke checks for every tenant;
14. if any tenant fails online smoke, return the full cohort to maintenance;
15. write per-site release evidence with the common cohort digest.

This sequencing prevents one client from running old database state against newly switched shared Ledgix code while another tenant is being migrated.

## Tenant add

A tenant add uses the fresh client provisioning contract:

```text
deploy/provision_client_site_safe.sh
```

or the canonical production wrapper:

```text
deploy/production_setup.sh --action site
```

The tenant gets its own site/database/secrets and is then configured through native ERPNext prerequisites plus `/app/ledgix-setup`.

Adding a tenant does not create a new Ledgix branch or copy the application source.

## Tenant remove

Tenant remove is an explicit destructive operation and is not automated by the shared release helper.

Before removing a tenant:

1. stop new business activity for that tenant;
2. take a fresh per-site backup including database, public files, private files and secure site-config inputs;
3. verify checksums;
4. retain the exact application release identity;
5. retain the backup off-host/off-server according to policy;
6. confirm accounting/FBR retention obligations with the responsible operator;
7. only then use the normal Frappe site-removal procedure.

Removing one tenant must never delete or rewrite another tenant's site/database.

## Tenant restore

Tenant restore uses the R3 backup/restore contract.

Before a production restore, prove the backup on a non-production recovery target where practical. Restore database/files with the matching application release and preserve the source encryption key required for encrypted Frappe values.

After restore, run:

- dependency preflight;
- offline smoke;
- representative ERPNext/Ledgix reads;
- Phase 12 frozen-history verification for migrated sites;
- online smoke before reopening the tenant.

## FBR isolation

FBR is per site. Never place one client's token, seller identity or environment selection in another tenant's configuration.

A shared Ledgix application revision does not imply shared FBR credentials. Each site independently controls Sandbox/Production settings and audit logs.

## Backup isolation

Each tenant requires a per-site backup set and per-site evidence even when clients share one host or bench. A host snapshot alone is not a substitute for the Ledgix backup contract.

## Large-client separation

A larger client may be moved from shared infrastructure to a separate bench or dedicated host without changing Ledgix application code. The move preserves the same one-site/one-database boundary and uses backup/restore plus the matching approved release.

## Local development boundary

The developer workstation intentionally keeps one canonical local site, `ledgix-erpnext.local`. R4 does not require maintaining multiple local client sites. Multi-site behavior is enforced in production tooling and contracts while local development remains simple.
