# Ledgix Client Site Lifecycle

This runbook covers the normal lifecycle for a Ledgix client site after the ERPNext Core Migration.

**Supported stack:** Frappe v15 + ERPNext v15 + `ledgix_saas`.

**Architecture rule:** each production client has its own Frappe site/database. The same Ledgix codebase is used for Invoice-only, Retail, B2B and Mixed clients; differences are configuration, not forks.

---

## 1. Host / bench preparation

Use the repository installer for a supported Frappe v15 bench:

```bash
cd /path/to/pos
./install.sh
```

The repository dependency contract requires ERPNext v15. Do not install `ledgix_saas` onto a Frappe-only site without ERPNext.

Before client work, validate the repository:

```bash
bash scripts/ci_local.sh
```

---

## 2. Local development site

The repository-managed local workflow intentionally keeps one canonical site:

```text
ledgix-erpnext.local
```

Create or repair it with:

```bash
bash site_setup.sh --ensure
```

For a deliberate destructive clean reset:

```bash
bash site_setup.sh --reset \
  --site ledgix-erpnext.local \
  --confirm "RESET ledgix-erpnext.local"
```

There is no app-selection menu. The local standard stack is always:

```text
Frappe -> ERPNext -> ledgix_saas
```

Local convenience credentials are separate from production policy.

---

## 3. Fresh production client site

Use the release-pinned provisioner documented in `docs/production/fresh_client_provisioning.md`.

Canonical wrapper:

```bash
PRODUCTION_SITE=client.example.com \
DEPLOY_RELEASE=<approved-immutable-sha-or-tag> \
PRODUCTION_URL=https://client.example.com \
bash deploy/production_setup.sh --action site
```

This path:

- creates a dedicated site/database;
- installs ERPNext before Ledgix;
- generates strong credentials;
- retains credentials outside the repository;
- runs dependency preflight and offline smoke checks;
- records provisioning evidence;
- does not create client business masters;
- does not apply a Business Profile;
- does not activate FBR Production.

---

## 4. Site dependency preflight

After app installation/migration, run:

```bash
bash scripts/run_ledgix_client_preflight.sh <site>
```

This is read-only and fails if:

- Frappe is missing;
- ERPNext is missing;
- Ledgix is missing;
- Frappe is not major version 15;
- ERPNext is not major version 15;
- Ledgix no longer declares ERPNext as a required app.

Do not continue client onboarding until this passes.

---

## 5. Configure standard ERPNext prerequisites

Ledgix does not create duplicate commercial/accounting masters through its setup wizard.

Configure the required native ERPNext records first:

- Company;
- Chart of Accounts / Company accounts;
- enabled Selling Price List;
- leaf Warehouse for profiles that use POS/inventory/buying;
- Mode(s) of Payment and Company account mappings;
- Customer(s), including a default walk-in customer for POS where required;
- POS Profile for POS-enabled profiles;
- taxes/accounts required by the Ledgix tax/FBR configuration.

For POS-enabled clients, the selected POS Profile must have:

- the correct Company;
- enabled state;
- default Customer;
- Warehouse;
- Selling Price List;
- at least one Mode of Payment.

---

## 6. Apply the Ledgix client profile

Sign in as `System Manager` or `Ledgix Admin` and open:

```text
/app/ledgix-setup
```

Choose one profile:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

Select/confirm the Company, Warehouse, Selling Price List and POS Profile as applicable.

Run **Check Readiness** first. Resolve every blocking item before applying configuration.

The wizard may apply safe site defaults for Company, Selling Price List and Warehouse. It never creates parallel Ledgix business masters or ledgers.

---

## 7. FBR onboarding

When the profile enables FBR, configure `Ledgix FBR Settings` separately.

Complete at minimum the seller identity/environment/token details required by the current FBR integration and verify them in Sandbox before Production use.

Do not treat the profile preset as permission to submit live FBR invoices automatically. Production activation remains an explicit compliance decision.

For migrated sites, historical `Ledgix Sale` FBR submission stays retired. New FBR business sources are native ERPNext `Sales Invoice` / `POS Invoice` documents.

---

## 8. Client acceptance checklist

Before handover, prove the workflows relevant to the selected profile.

### Invoice + FBR Only

- create Customer/Item as required;
- create and submit Sales Invoice;
- payment/receivable flow;
- FBR readiness/preview/submission in the intended environment;
- native A4 print with FBR metadata/QR where applicable.

### Small Retail

- open POS shift;
- search/barcode item;
- checkout;
- split payment/change if required;
- POS return;
- close shift;
- stock quantity effect;
- thermal print;
- FBR flow.

### Full Retail

Small Retail plus:

- Stock Entry/Reconciliation;
- Batch/Serial workflow where relevant;
- buying/receipt/valuation flow.

### B2B

- customer credit/receivable view;
- Sales Invoice checkout;
- partial/full payment;
- Credit Note/return;
- B2B print;
- FBR flow.

### Mixed

Run both the Retail and B2B acceptance paths.

---

## 9. Backup before upgrades or production changes

Create and verify a current site backup before every production deployment, migration, FBR Production switch or destructive maintenance action.

The R3 contract requires database, public files, private files, secure site-config inputs, release identity, stack versions and rollback ownership. Use `deploy/backup_safe.sh` and retain an off-host/off-server copy where appropriate.

Do not start destructive legacy-schema removal based only on Phase 12 freeze. Physical deletion remains a separately approved future migration after observation and backup/rollback planning.

---

## 10. Upgrade workflow

### Single-site bench

Use:

```text
deploy/deploy_update_safe.sh
```

It refuses a bench containing multiple sites.

### Shared multi-site bench

Use:

```text
deploy/deploy_update_shared_safe.sh
```

Every Ledgix tenant on the bench must be explicitly approved as part of the same release cohort. The shared updater backs up and places all tenants into maintenance before switching shared Ledgix code.

See `docs/production/multi_site_saas.md`.

---

## 11. Rollback principles

Rollback should restore the site/database/files and application revision together.

For Phase 12 migrated historical data, the legacy freeze has an explicit controlled unfreeze mechanism, but it is **not** a normal operating mode. Use it only as part of a deliberate rollback procedure.

Never run two financial/stock authorities in parallel to “keep both sides safe.” ERPNext is the active business authority.

---

## 12. Multi-site SaaS boundary

Ledgix SaaS uses native Frappe multitenancy:

- one codebase/application revision per bench;
- separate Frappe site per client;
- separate site database per client;
- per-site Business Profile and standard ERPNext configuration;
- per-site FBR credentials/settings;
- per-site backups and release evidence;
- shared infrastructure is acceptable for smaller tenants while keeping site/database boundaries;
- larger clients can move to dedicated infrastructure without changing application code.

If clients need different Ledgix releases, place them on separate benches rather than creating client forks.

---

## 13. Operational evidence to retain

For every production client, retain a short provisioning record with:

- site/domain;
- Company;
- selected Ledgix Business Profile;
- default Warehouse/Price List/POS Profile where applicable;
- FBR environment status;
- installed app versions;
- initial acceptance date;
- latest verified backup date;
- current deployed Git commit.

This is operational metadata only; ERPNext remains the business-data source of truth.
