# Ledgix POS

> **A retail POS and ERP product built on Frappe v15 + ERPNext v15, with ERPNext as the authority for business data and Ledgix adding the focused retail, product, tax/FBR, onboarding, and operational experience.**

## Current Product Architecture

Ledgix is no longer a parallel custom ERP model. The current product uses ERPNext-native masters and ledgers for operational truth:

- **Items / pricing:** ERPNext `Item`, `Item Group`, `Price List`, `Item Price`, `Pricing Rule`
- **Customers / suppliers:** ERPNext `Customer`, `Supplier`
- **Sales:** ERPNext `Sales Invoice`, `POS Invoice`, `Payment Entry`
- **Purchasing:** ERPNext `Purchase Order`, `Purchase Receipt`, `Purchase Invoice`
- **Inventory:** ERPNext `Warehouse`, `Stock Entry`, `Stock Reconciliation`, batches and serials
- **Accounting / receivables:** ERPNext accounting ledgers and reports
- **POS shifts:** ERPNext `POS Opening Entry` / `POS Closing Entry`

Ledgix keeps the product-specific layer that ERPNext does not provide directly:

- fast retail POS experience
- curated role/profile-aware workspace
- Inventory Intelligence
- Tax & FBR Center and FBR submission/audit controls
- business profile, brand settings, and Ledgix user-profile UX
- onboarding/readiness evidence and SaaS deployment controls

See `docs/architecture/ERP_AUTHORITY.md` and `docs/architecture/LEGACY_AUDIT.md` for the authority and retirement boundaries.

---

## Supported Stack

```text
Frappe:   15.113.4 / version-15
ERPNext:  15.121.3 / version-15
Ledgix:   ledgix_saas
Python:   Frappe v15 compatible environment
Database: MariaDB
Queue:    Redis
```

Do not vendor or patch ERPNext core. Ledgix extends ERPNext through the app layer.

---

## Main User Surfaces

### Quick Actions

The Ledgix workspace exposes four focused product shortcuts:

1. **Ledgix POS** — fast retail checkout
2. **Inventory Intelligence** — stock visibility and operational insights
3. **Tax & FBR Center** — tax mapping, readiness, logs, and FBR controls
4. **Setup Wizard** — configuration-only onboarding

### Business Areas

The main workspace is organized into:

- Sales & POS
- Catalog & Pricing
- Purchasing
- Inventory & Stock
- Reports & Accounting
- Tax & FBR
- Administration

The workspace links to native ERPNext DocTypes/reports wherever ERPNext is the business authority. Ledgix-specific pages remain custom only where they add product value.

---

## Role / Profile Model

Ledgix curates the product shell for:

- `Ledgix Cashier`
- `Ledgix Manager`
- `Ledgix Admin`
- `System Manager`

Business profiles control product presentation and feature availability without replacing Frappe/ERPNext authorization. Permissions remain authoritative at the framework/DocType level.

The client shell hides irrelevant workspace cards/links/shortcuts and compacts the remaining grid so role/profile filtering does not leave visual gaps.

---

## Legacy Boundary

Historical Ledgix business DocTypes are retained only where required for migration evidence, rollback/reconciliation history, or frozen audit context. They are not the active business authority.

Active product flows must not create new records in retired parallel business models such as:

- `Ledgix Item`
- `Ledgix Customer`
- `Ledgix Supplier`
- `Ledgix Sale`
- `Ledgix Purchase`
- `Ledgix Payment`
- `Ledgix Stock Movement`

See `docs/architecture/LEGACY_AUDIT.md` for the current classification.

---

## Local Development

Repository:

```bash
cd ~/data_drive/pos
```

Integration site:

```text
ledgix-erpnext.local
```

Typical local start:

```bash
./start.sh
```

Useful checks:

```bash
cd frappe-bench
bench --site ledgix-erpnext.local list-apps
bench --site ledgix-erpnext.local migrate
bench build --app ledgix_saas
```

---

## Validation

### Fast repository checks

```bash
./scripts/ci_local.sh
```

This validates repository structure, DocType names, ERPNext dependency rules, and accidental secret exposure.

### Current post-migration / pre-client gate

Use the consolidated integration gate for the current product state:

```bash
./scripts/run_pre_client_final_gate.sh ledgix-erpnext.local
```

This is **not another migration phase**. It validates the current workspace/product shell, frozen legacy boundary, client profiles, ERPNext-native demo-data contract, release/deployment hardening, tenant-provisioning safety, and machine-verifiable release readiness. It exact-syncs the Ledgix app into the local bench, migrates the integration site, builds Ledgix assets, runs dependency/offline smoke checks, and records readiness evidence.

The gate does **not** seed/clean demo data, make an FBR network submission, arm FBR Production, or claim physical device/manual UAT or external FBR certification has passed.

Historical `run_erpnext_phase*_final_gate.sh` scripts remain regression/evidence tools for the completed migration phases.

### Release acceptance / production gates

Release and production controls remain separate from local product validation. Relevant scripts include:

```text
scripts/run_release_acceptance_static_gate.sh
scripts/run_release_acceptance_readiness_gate.sh
deploy/deploy_update_safe.sh
deploy/deploy_update_shared_safe.sh
scripts/run_ledgix_production_release_gate.sh
```

Production deployment requires an immutable release reference, verified backup evidence, explicit site identity, and the release gates documented under `docs/production/`.

---

## ERPNext-Native Demo Dataset

The supported demo entrypoint is:

```text
ledgix_saas.setup.demo_data
```

For the guarded local integration workflow, use:

```bash
./scripts/prepare_local_demo.sh ledgix-erpnext.local
```

The helper:

1. refuses non-local sites;
2. creates a backup before changing demo data;
3. cleans only the deterministic Ledgix V2 demo marker set;
4. seeds the ERPNext-native dataset;
5. verifies the resulting dataset.

The demo dataset exercises ERPNext Items, Customers, Suppliers, Warehouses, purchasing, POS, Sales Invoices, Payment Entries, stock movement, returns, batches/serials, split tenders, receivables, and low/out-of-stock scenarios.

FBR transport remains disabled during demo seeding.

See `docs/operations/LOCAL_DEMO_DATA.md` before reseeding.

---

## FBR

FBR is a retained Ledgix product capability layered over ERPNext-native invoice authority.

Key rules:

- Sales/POS accounting authority remains ERPNext.
- Ledgix owns FBR mapping, readiness, transport orchestration, submission logs, and tax audit evidence.
- Demo/local seed operations keep FBR disabled.
- Sandbox certification and Production activation are separate guarded workflows.
- Production posting is never armed by general setup or readiness flows.

Documentation:

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_SANDBOX_RUNBOOK.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
```

---

## SaaS / Multi-Site Model

The intended deployment model is:

```text
one Ledgix codebase
        |
        +-- client-a site + DB
        +-- client-b site + DB
        +-- client-c site + DB
```

Each customer receives a separate Frappe site/database while running the same approved Ledgix application revision. Client complexity is configuration, not a fork.

For shared benches, release updates must operate on the complete approved tenant cohort. Large clients can be moved to dedicated infrastructure when required.

See:

```text
docs/production/fresh_client_provisioning.md
docs/production/multi_site_saas.md
docs/production/release_install_update.md
```

---

## Repository Map

```text
pos/
├── apps/ledgix_saas/          # Ledgix Frappe app
├── deploy/                    # safe backup/deploy/smoke helpers
├── docs/
│   ├── architecture/          # current authority + legacy boundaries
│   ├── fbr/                   # FBR architecture/runbooks/checklists
│   ├── operations/            # local/demo operating guides
│   ├── production/            # client/release/deployment runbooks
│   └── archive/migration/     # completed migration planning/history
├── scripts/                   # CI, gates, local guarded utilities
├── install.sh
├── site_setup.sh
└── start.sh
```

Completed migration plans are intentionally archived under `docs/archive/migration/`; they are historical evidence, not the active implementation plan.

---

## Security / Secrets

Never commit:

- FBR tokens or credentials
- site/database passwords
- private keys or SSL material
- backup archives
- generated local bench data
- client-specific secrets

Keep secrets outside the repository and use the guarded production helpers/runbooks. Run:

```bash
./scripts/check_secrets.sh
```

before release work.

---

## Documentation Starting Points

```text
docs/architecture/ERP_AUTHORITY.md
docs/architecture/LEGACY_AUDIT.md
docs/operations/LOCAL_DEMO_DATA.md
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/production/client_onboarding_readiness.md
docs/production/final_release_gate.md
docs/production/release_install_update.md
```

---

## Status

The ERPNext-core migration is complete. Current work is **product readiness, client acceptance, demo realism, FBR certification, and production provisioning/hardening** on top of the single ERPNext-authoritative architecture.

No new parallel Ledgix business ledger should be introduced without an explicit architecture decision.