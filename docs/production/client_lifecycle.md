# Ledgix Client Site Lifecycle

This runbook covers the normal lifecycle for a Ledgix client site after the ERPNext Core Migration.

**Supported stack:** Frappe v15 + ERPNext v15 + `ledgix_saas`.

**Architecture rule:** each client site has its own Frappe site/database. The same Ledgix codebase is used for Invoice-only, Retail, B2B and Mixed clients; differences are configuration, not forks.

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

## 2. Create a local/new client site

For the repository-managed local workflow:

```bash
./site_setup.sh
```

Use the interactive **New Site** flow. The script creates a dedicated database/user, installs the selected apps, migrates the site, stores local development credentials under `.secrets/sites/`, and can add the local hosts entry.

For Ledgix client sites, ensure the installed app set includes:

1. `frappe`;
2. `erpnext`;
3. `ledgix_saas`.

ERPNext must be installed before Ledgix migration completes.

For production infrastructure, follow the existing production setup/deployment scripts under `deploy/` and keep one Frappe site/database per client.

---

## 3. Site dependency preflight

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

## 4. Configure standard ERPNext prerequisites

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

## 5. Apply the Ledgix client profile

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

## 6. FBR onboarding

When the profile enables FBR, configure `Ledgix FBR Settings` separately.

Complete at minimum the seller identity/environment/token details required by the current FBR integration and verify them in Sandbox before Production use.

Do not treat the profile preset as permission to submit live FBR invoices automatically. Production activation remains an explicit compliance decision.

For migrated sites, historical `Ledgix Sale` FBR submission stays retired. New FBR business sources are native ERPNext `Sales Invoice` / `POS Invoice` documents.

---

## 7. Client acceptance checklist

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

## 8. Backup before upgrades or production changes

Create a current site backup before every production deployment, migration, FBR production switch or destructive maintenance action.

Use the repository backup tooling under `deploy/`, for example the safe backup workflow already provided by the project, and verify the resulting database/files backup is stored outside the live site/instance when appropriate.

At minimum record:

- site name;
- current Git commit;
- Frappe version;
- ERPNext version;
- Ledgix version/branch;
- database backup location;
- public/private files backup location;
- rollback owner/window.

Do not start a destructive legacy-schema removal based only on Phase 12 freeze. Physical deletion remains a separately approved future migration after observation and backup/rollback planning.

---

## 9. Upgrade workflow

For an existing client site:

1. take and verify a fresh backup;
2. capture the current Git commit and installed app versions;
3. pull the approved Ledgix release/update;
4. ensure ERPNext dependency/alignment using the existing deployment helpers;
5. run repository validation;
6. migrate the target site;
7. rebuild Ledgix assets;
8. run the client dependency preflight;
9. smoke-test the client-profile workflows;
10. verify FBR mode/state before allowing Production submissions.

The repository contains safe production/deploy helpers under `deploy/`; use those rather than editing ERPNext core or copying client-specific code into the framework apps.

---

## 10. Rollback principles

Rollback should restore the site/database/files and application revision together.

For Phase 12 migrated historical data, the legacy freeze has an explicit controlled unfreeze mechanism, but it is **not** a normal operating mode. Use it only as part of a deliberate rollback procedure.

Never run two financial/stock authorities in parallel to “keep both sides safe.” ERPNext is the active business authority.

---

## 11. Multi-site SaaS boundary

Ledgix SaaS uses native Frappe multitenancy:

- one codebase/app revision;
- separate Frappe site per client;
- separate site database per client;
- per-site Business Profile and standard ERPNext configuration;
- per-site FBR credentials/settings;
- per-site backups;
- shared infrastructure is acceptable for smaller tenants while keeping site/database boundaries;
- larger clients can move to dedicated infrastructure without changing application code.

Do not implement per-client forks for feature selection. If a client needs a supported combination, model it through Business Profile/configuration and normal ERPNext permissions/settings.

---

## 12. Operational evidence to retain

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
