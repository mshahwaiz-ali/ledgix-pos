# Ledgix POS

> **ERPNext-native retail, B2B, purchasing, inventory and FBR product on Frappe v15 + ERPNext v15. ERPNext owns business, stock, monetary tax and accounting truth; Ledgix owns the focused product experience, compatibility and FBR compliance/orchestration around those native transactions.**

## Current status

| Area | Status |
|---|---|
| ERPNext-core migration | **COMPLETE** |
| Migration phases 0–13 | **CLOSED / ARCHIVED** |
| Current business authority | **ERPNext** |
| Historical duplicate Ledgix business ledgers | **FROZEN / READ-ONLY EVIDENCE** |
| Ledgix POS / B2B / buying / inventory | **ERPNext-NATIVE CURRENT ARCHITECTURE** |
| FBR software | **READY FOR CLIENT CERTIFICATION** |
| Real FBR Sandbox certification | **PENDING CLIENT EVIDENCE** |
| FBR Production readiness | **NOT READY BY DEFAULT** |
| FBR Production active | **NO BY DEFAULT** |
| General FBR V2 network cutover | **DISABLED** |

There is no Phase 14.

New work should improve the current product/release state rather than restart the completed migration.

---

## Documentation

The documentation has been consolidated into two current sets.

### Developers / technical operators

Start here:

- [Developer documentation](docs/developer/README.md)
- [Architecture](docs/developer/ARCHITECTURE.md)
- [Codebase and extension points](docs/developer/CODEBASE_AND_EXTENSION_POINTS.md)
- [Business workflows](docs/developer/BUSINESS_WORKFLOWS.md)
- [FBR architecture](docs/developer/FBR_ARCHITECTURE.md)
- [Security and permissions](docs/developer/SECURITY_AND_PERMISSIONS.md)
- [Deployment and upgrades](docs/developer/DEPLOYMENT_AND_UPGRADES.md)
- [Testing and release gates](docs/developer/TESTING_AND_RELEASE_GATES.md)

### Clients / business operators

Start here:

- [Client documentation](docs/client/README.md)
- [Getting started](docs/client/GETTING_STARTED.md)
- [Users, roles and navigation](docs/client/USERS_ROLES_AND_NAVIGATION.md)
- [POS daily operations](docs/client/POS_DAILY_OPERATIONS.md)
- [Sales, returns and payments](docs/client/SALES_RETURNS_AND_PAYMENTS.md)
- [Purchasing and inventory](docs/client/PURCHASE_AND_INVENTORY.md)
- [FBR setup and operations](docs/client/FBR_SETUP_AND_OPERATIONS.md)
- [Backup, deployment and go-live](docs/client/BACKUP_DEPLOYMENT_AND_GO_LIVE.md)

### Historical evidence

Historical material lives under:

- [Documentation archive](docs/archive/README.md)
- [ERPNext migration archive](docs/archive/migration/README.md)
- [Final forensic inspection](docs/archive/audit/FINAL_FORENSIC_INSPECTION_20260926.md)

Archived documents can contain old phase-time wording and are not current operating authority.

---

## Architecture rule

The governing rule is:

> **One business concept = one authoritative source of truth.**

ERPNext owns current:

- Item / Item Group;
- Customer / Supplier;
- Price List / Item Price / Pricing Rule;
- Sales Invoice / POS Invoice;
- Payment Entry;
- Purchase Order / Purchase Receipt / Purchase Invoice;
- Warehouse / Stock Entry / Stock Reconciliation;
- Stock Ledger Entry / Bin;
- Batch / Serial No;
- POS Opening Entry / POS Closing Entry;
- monetary tax;
- General Ledger / AR / AP;
- standard accounting reports.

Ledgix intentionally owns:

- Ledgix POS product UX;
- Inventory Intelligence;
- Tax & FBR Center;
- Setup Wizard / Business Profile;
- compatibility APIs over ERPNext-native services;
- Ledgix branding/product metadata;
- FBR mappings/reference data;
- immutable FBR compliance snapshots;
- guarded FBR transport;
- FBR Submission Logs/certification/reconciliation evidence;
- client readiness/release evidence;
- deployment/recovery tooling.

Ledgix does **not** vendor or modify ERPNext core for normal product features.

---

## Current business workflows

### Retail POS

```text
ERPNext POS Profile
  -> POS Opening Entry
  -> Ledgix POS
  -> POS Invoice
  -> native payment rows / split tender
  -> ERPNext stock + accounting
  -> POS Closing Entry
  -> standard ERPNext consolidation
```

### B2B sales

```text
Customer + Item + ERPNext pricing
  -> Sales Invoice
  -> Payment Entry
  -> ERPNext outstanding / AR / GL
  -> native Credit Note / refund when required
```

### Purchasing

```text
Supplier
  -> Purchase Order
  -> Purchase Receipt
  -> Purchase Invoice
  -> Payment Entry
```

A direct Purchase Invoice path is also supported where the chosen ERPNext workflow calls for it.

### Inventory

```text
ERPNext Item + Warehouse
  -> purchase/sale/return stock effects
  -> Stock Entry / Stock Reconciliation
  -> Stock Ledger Entry + Bin
```

Historical Ledgix Sale, Purchase, Payment, POS Shift, Stock Movement and related duplicate business models are not current transaction authority.

---

## FBR

Current FBR commercial sources are submitted ERPNext:

- `Sales Invoice`;
- `POS Invoice`.

High-level flow:

```text
ERPNext invoice
  -> ERPNext monetary tax/accounting
  -> immutable Ledgix FBR snapshot
  -> readiness
  -> payload
  -> guarded transport
  -> Submission Log
  -> official FBR status/reference on the same ERPNext invoice
```

Key safety rules:

- historical `Ledgix Sale` submission is retired;
- payloads require hash-verified invoice-time snapshot evidence;
- Sandbox certification requires persisted real Validate/POST evidence;
- Production requires separate explicit readiness/arming;
- general V2 network cutover is disabled at the documented baseline;
- ambiguous Production POST becomes `Reconciliation Required`;
- **do not blindly retry** a reconciliation-required invoice;
- Known Offline is a separate operator-confirmed workflow and cannot be used after a Production POST attempt;
- local tests/mocks are never certification evidence.

See [FBR Architecture](docs/developer/FBR_ARCHITECTURE.md) and [Client FBR Guide](docs/client/FBR_SETUP_AND_OPERATIONS.md).

---

## Supported stack

The current production release contract lives in:

```text
deploy/release_contract.env
```

The documented baseline uses:

```text
Frappe:   15.113.4
ERPNext:  15.121.3
Ledgix:   ledgix_saas 15.0.1
Database: MariaDB
Queue:    Redis
```

Always treat `deploy/release_contract.env` in the selected release as the deploy-time version authority.

---

## Local development

Repository root:

```bash
cd ~/data_drive/ledgix-pos
```

Canonical local integration site:

```text
ledgix-erpnext.local
```

Typical setup:

```bash
./install.sh --local
./site_setup.sh --ensure
./start.sh
```

Useful checks:

```bash
./site_setup.sh --status
./start.sh --status
./start.sh --smoke --site ledgix-erpnext.local
bash scripts/ci_local.sh
```

Detailed guide:

- [Installation and configuration](docs/developer/INSTALLATION_AND_CONFIGURATION.md)

---

## Testing and release evidence

Different evidence levels must not be confused.

```text
static/unit proof
  -> local runtime proof
  -> recovery proof
  -> client readiness
  -> manual UAT
  -> real FBR Sandbox evidence
  -> strict Production release readiness
  -> explicit Production activation
```

Final forensic baseline recorded:

- focused final blocker regression: **19 passed / 0 failed**;
- broad setup regression: **472 passed / 0 failed**;
- final inspected software blockers: **closed**;
- real FBR/PRAL calls during final forensic audit: **0**;
- Production posting: **unarmed**.

These are point-in-time software proofs, not permanent test-count requirements or client certification.

See [Testing and release gates](docs/developer/TESTING_AND_RELEASE_GATES.md).

---

## Production / SaaS

Ledgix uses native Frappe site isolation:

```text
one approved Ledgix revision per bench
        |
        +-- client-a site + database
        +-- client-b site + database
        +-- client-c site + database
```

Each client has separate:

- database;
- site config;
- business data;
- users;
- FBR credentials/evidence;
- backups;
- release evidence.

If clients need different Ledgix releases, use separate benches instead of client code forks.

Production release rules:

- deploy immutable SHA/tag;
- create verified backup before update;
- use single-site updater for a single-site bench;
- use shared cohort updater for a shared bench;
- run migrate/build/smoke;
- preserve release evidence;
- run final acceptance gate separately;
- never activate FBR Production as an installation/update side effect.

See:

- [Deployment and upgrades](docs/developer/DEPLOYMENT_AND_UPGRADES.md)
- [Backup, restore and rollback](docs/developer/BACKUP_RESTORE_ROLLBACK.md)
- [Multi-site SaaS](docs/developer/MULTI_SITE_SAAS.md)

---

## Legacy boundary

ERPNext-core migration phases 0–13 are complete.

Historical duplicate Ledgix business data can remain physically present for:

- audit;
- migration provenance;
- reconciliation evidence;
- rollback reasoning.

On migrated sites these records are frozen/read-only and hash-verifiable.

Old mixed Ledgix monetary tax/FBR configuration masters were retired separately during the FBR redesign.

See [Migration and legacy retirement](docs/developer/MIGRATION_AND_LEGACY_RETIREMENT.md).

---

## Repository map

```text
ledgix-pos/
├── README.md
├── apps/
│   └── ledgix_saas/              # Ledgix Frappe application
├── deploy/                        # guarded production/update/recovery tooling
├── docs/
│   ├── developer/                 # CURRENT technical authority
│   ├── client/                    # CURRENT client/operator authority
│   └── archive/                   # HISTORICAL evidence only
├── scripts/                       # CI/readiness/release/gate utilities
├── install.sh
├── site_setup.sh
└── start.sh
```

---

## Security

Never commit:

- FBR tokens;
- site/database passwords;
- private keys/certificates;
- client API secrets;
- private site configuration;
- database/file backups;
- generated evidence containing credentials.

Use named users and least privilege.

Business Profile controls product visibility; Frappe/ERPNext permissions and server-side checks remain authorization authority.

Run:

```bash
bash scripts/check_secrets.sh
```

before release work.

See [Security and permissions](docs/developer/SECURITY_AND_PERMISSIONS.md).

---

## Known maintenance item

Documentation consolidation identified one source-level permission inconsistency:

- `Ledgix FBR Submission Log` DocType JSON intends read-only Desk evidence;
- `setup/permissions.py` still carries older broader System Manager/Ledgix Admin rights;
- `fast_permissions.py` can synchronize that older policy during migrate.

The intended direction is read-only Submission Log evidence.

This should be fixed in application code with migrate-level regression coverage before claiming that the read-only control is durable across every migration.

---

## Documentation authority

For current work:

1. current source/runtime wiring;
2. `docs/developer/` for technical work;
3. `docs/client/` for business/operator work;
4. `docs/archive/` only for historical evidence.

Do not follow archived phase instructions as current runbooks.

---

## Product summary

> **Ledgix is a focused ERPNext-native POS/business product: ERPNext owns commercial, stock, tax and accounting truth; Ledgix provides the operator experience and controlled FBR compliance layer, while historical duplicate Ledgix business records remain non-authoritative evidence and live FBR Production stays fail-closed until genuine client prerequisites are satisfied.**
