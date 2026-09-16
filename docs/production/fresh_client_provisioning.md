# Ledgix Fresh Client Provisioning

This runbook is the canonical production path for creating a new Ledgix client site after the ERPNext Core Migration.

## Contract

- use one approved immutable release SHA or tag;
- use a supported Frappe v15 + ERPNext v15 bench;
- create one isolated Frappe site and one database per client;
- install ERPNext before Ledgix;
- generate strong Administrator/database credentials automatically;
- retain credentials outside the repository with owner-only permissions;
- run dependency preflight and offline smoke checks before onboarding;
- do not create client business masters inside the provisioner;
- do not apply a Business Profile inside the provisioner;
- do not enable FBR Production inside the provisioner.

The provisioning step is infrastructure/application installation only. Client business setup remains explicit and configuration-only.

## Preferred command

On an already prepared production bench:

```bash
PRODUCTION_SITE=client.example.com \
DEPLOY_RELEASE=<approved-immutable-sha-or-tag> \
bash deploy/production_setup.sh --action site
```

The site action performs release-pinned provisioning and offline validation. It does not assume that Nginx/domain routing is already ready.

For a full host/bench/services rollout, provide the public URL to the full wrapper. The wrapper performs online smoke only after services/SSL are configured:

```bash
PRODUCTION_SITE=client.example.com \
DEPLOY_RELEASE=<approved-immutable-sha-or-tag> \
PRODUCTION_URL=https://client.example.com \
bash deploy/production_setup.sh --yes --action full
```

The wrapper delegates site creation to:

```text
deploy/provision_client_site_safe.sh
```

When infrastructure is already serving the target URL, the provisioner can also be called directly with `--url` for an immediate online smoke check.

Do not use the generic legacy-style site creation flow for normal Ledgix production onboarding.

## What the provisioner does

1. Requires an explicit site and immutable release.
2. Refuses an existing site.
3. Requires a valid prepared bench with Frappe and ERPNext checkouts.
4. Verifies the pinned Frappe/ERPNext versions from the selected release contract.
5. Syncs the exact Ledgix application revision into the bench.
6. Generates a dedicated database/user and strong passwords.
7. Creates the Frappe site.
8. Installs ERPNext before Ledgix.
9. Migrates, builds Ledgix assets and enables the scheduler.
10. Runs the Ledgix client dependency preflight.
11. Runs the ERPNext-native offline smoke suite.
12. Stores provisioning evidence under the site's private directory.
13. Stores generated credentials outside the repository.

## Credential handling

Production has no `admin`, `admin@123`, or other weak implicit defaults.

Generated client credentials are stored under the operator's configured Ledgix secrets directory, defaulting to:

```text
~/.config/ledgix/sites/<site>.env
```

The file is owner-readable only. The repository secret scan must remain clean.

Local development uses a separate convenience credential policy; that policy never applies to this production provisioner.

## After provisioning

The new site is deliberately not treated as business-ready yet.

Configure native ERPNext prerequisites first:

- Company;
- Chart of Accounts and accounting defaults;
- Selling Price List;
- required Mode(s) of Payment and account mappings;
- Warehouse for stock/POS profiles;
- Customer defaults including walk-in customer where needed;
- POS Profile for POS-enabled profiles;
- taxes/accounts required by the client flow;
- suppliers/purchasing prerequisites where buying is enabled.

Then sign in as System Manager or Ledgix Admin and open:

```text
/app/ledgix-setup
```

Choose one of the five supported Business Profiles and run readiness checks before applying it. The setup wizard remains configuration-only and does not create parallel Ledgix accounting, stock, customer, supplier or invoice authorities.

## FBR boundary

FBR configuration is per site. A Business Profile may enable the FBR product surface, but it does not authorize FBR Production.

Complete the client's FBR settings and Sandbox validation first. FBR Production activation is a separate explicit compliance/operations gate.

## Local development

The repository-managed local workflow intentionally keeps one canonical site:

```text
ledgix-erpnext.local
```

Use `site_setup.sh --ensure` or the explicit destructive `--reset` mode for local work. Do not create local client sprawl merely to model production multitenancy; production multitenancy is a deployment boundary, not a requirement for the developer bench.
