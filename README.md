# Ledgix POS

Ledgix is a streamlined **retail + B2B POS, inventory, purchasing, sales, returns, payments, reporting and Pakistan FBR integration product** built on Frappe/ERPNext v15.

The current architecture is intentionally simple:

> **ERPNext is the business authority. Ledgix is the product UX, orchestration, tax/FBR, intelligence, branding and SaaS layer.**

Ledgix does not maintain a second active sales, stock or accounting ledger and does not vendor/patch ERPNext core.

---

## Current stack

```text
Frappe:       15.113.4
ERPNext:      15.121.3
Custom app:   ledgix_saas
Local site:   ledgix-erpnext.local
Branch:       main
```

The ERPNext-core migration through Phases 0–13 is complete. Completed migration plans and evidence are archived under `docs/archive/migration/`; they are not the active product roadmap.

---

## Authority model

| Area | Current authority |
|---|---|
| Items / Item Groups | ERPNext `Item`, `Item Group` |
| Customers | ERPNext `Customer` |
| Suppliers | ERPNext `Supplier` |
| Pricing | ERPNext `Price List`, `Item Price`, `Pricing Rule` |
| Retail sales | ERPNext `POS Invoice` |
| B2B sales | ERPNext `Sales Invoice` |
| Returns / credit notes | ERPNext native return documents |
| Payments | ERPNext `Payment Entry` and native POS payment rows |
| Purchasing | ERPNext PO / Purchase Receipt / Purchase Invoice |
| Warehouses / stock | ERPNext Warehouse, Bin and Stock Ledger |
| Transfers / adjustments | ERPNext `Stock Entry`, `Stock Reconciliation` |
| Batch / serial tracking | ERPNext Batch / Serial No / Serial and Batch Bundle |
| POS shifts | ERPNext `POS Opening Entry`, `POS Closing Entry` |
| Accounting / AR / AP | ERPNext General Ledger and receivable/payable reports |
| FBR source transaction | The submitted ERPNext Sales/POS Invoice |

Historical legacy Ledgix business DocTypes remain frozen where Phase-12 migration/audit evidence requires them. Physical table presence does **not** make them active authority. See `docs/architecture/LEGACY_AUDIT.md`.

---

## Retained Ledgix product UX

These custom Pages are intentionally retained:

### Ledgix POS — `ledgix-pos`

A fast product selling surface over ERPNext-native data and documents, including:

- barcode/item search;
- retail and B2B selling;
- native pricing and authorized discounts;
- Cash, Card, Bank and wallet-style modes of payment;
- split payment;
- ERPNext POS opening/closing;
- hold/resume metadata over ERPNext drafts;
- returns against the real ERPNext source invoice;
- native stock/accounting effects.

### Inventory Intelligence — `business-intelligence-center`

A Ledgix operational view over ERPNext stock, purchases, sales, returns, batches and serials. It does not create an alternate stock ledger.

### Tax & FBR Center — `ledgix-tax-center`

Ledgix tax/FBR mapping, readiness, submission status, reconciliation and compliance UX over ERPNext invoice authority.

### Setup Wizard — `ledgix-setup`

Business Profile and client configuration without recreating ERPNext masters.

---

## Product modules

### Sales & POS

- Ledgix POS
- ERPNext Sales Invoice / POS Invoice
- retail + B2B modes
- customers
- POS opening/closing
- split payment
- full and partial returns / credit notes
- printable invoices

### Catalog & pricing

- Items and Item Groups
- Price Lists / Item Prices
- Pricing Rules
- barcodes
- stock and non-stock/service items

### Purchasing

- Purchase Orders
- Purchase Receipts
- Purchase Invoices
- Suppliers
- supplier/accounting flows through ERPNext

### Inventory & stock

- Warehouses
- Stock Entry
- Stock Reconciliation
- Batch / Serial No
- Stock Balance / Stock Ledger
- Inventory Intelligence
- reorder/low-stock operational visibility

### Accounting & reporting

- Payment Entry
- Accounts Receivable
- General Ledger
- Profit & Loss
- Ledgix sales / return / purchase / customer-statement views
- ERPNext stock and accounting reports as the underlying authority

### Tax & FBR

- ERPNext invoice authority
- Ledgix Item Tax Profiles linked to ERPNext Items
- immutable invoice tax/FBR snapshots
- payload validation
- Sandbox/Production transport modes
- protected Production arming
- FBR Submission Log
- QR/reference printing metadata
- reconciliation-required protection for ambiguous Production POSTs

Full current FBR design: `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md`.

---

## Business Profiles

Ledgix supports different client complexity through configuration rather than forks.

Business Profile flags can shape whether a site exposes POS, B2B/Sales Invoice, buying, inventory, advanced inventory, accounting workspace and FBR features.

The product shell uses those flags plus Ledgix roles to curate navigation. **ERPNext/Frappe permissions remain the security authority.**

Typical roles:

- Ledgix Cashier
- Ledgix Manager
- Ledgix Admin
- System Manager

---

## Workspace

`/app/ledgix` is the curated product home and is grouped into:

```text
Quick Actions
Sales & POS
Catalog & Pricing
Purchasing
Inventory & Stock
Reports & Accounting
Tax & FBR
Administration
```

The top Quick Actions are:

- Ledgix POS
- Inventory Intelligence
- Tax & FBR Center
- Setup Wizard

Role/profile-inapplicable cards and links are hidden as navigation only; visible cards compact into the remaining grid.

---

## Repository layout

```text
pos/
├── README.md
├── apps/
│   └── ledgix_saas/
├── docs/
│   ├── architecture/
│   ├── archive/
│   │   └── migration/
│   ├── fbr/
│   ├── local/
│   ├── operations/
│   ├── production/
│   └── testing/
├── scripts/
├── deploy/
├── config/
├── env/
├── install.sh
├── site_setup.sh
└── start.sh
```

The local `frappe-bench/` is generated/ignored and is not the source of truth for application code.

---

## Local development

Clone and bootstrap using the repository setup tooling:

```bash
git clone https://github.com/mshahwaiz-ali/pos.git
cd pos
chmod +x install.sh site_setup.sh start.sh
./install.sh
```

For the canonical integration site, application work is expected against:

```text
ledgix-erpnext.local
```

Common commands:

```bash
cd frappe-bench
bench --site ledgix-erpnext.local list-apps
bench --site ledgix-erpnext.local migrate
bench build --app ledgix_saas
bench start
```

Repository static checks:

```bash
./scripts/ci_local.sh
```

---

## Realistic local demo data

Ledgix includes a deterministic **ERPNext-authoritative** demo seed for local `.local` sites.

Recommended command from repository root:

```bash
chmod +x scripts/prepare_local_demo.sh
./scripts/prepare_local_demo.sh ledgix-erpnext.local
```

The script:

1. confirms installed apps;
2. takes a database/files backup;
3. inspects the current site;
4. removes only prior `LEDGIX-ERP-DEMO-V2` transactions;
5. seeds roughly 12 weeks of realistic ERPNext-native purchasing, stock, POS, B2B, returns and payment activity;
6. verifies the seeded dataset.

The seed includes 20+ items, customers/suppliers, three warehouses, barcode/pricing data, batch/serial examples, purchase cycles, 100+ sales, split tenders, open/partial/paid receivables, returns and low/out-of-stock examples.

It does **not** create new legacy Ledgix sale/stock/accounting records and it does **not** fabricate FBR credentials or network evidence.

Full guide: `docs/operations/LOCAL_DEMO_DATA.md`.

---

## FBR status

The software/setup layer is implemented, including native invoice hooks, immutable FBR snapshots, validation/transport controls, logs, Production arming and reconciliation protection.

**Real Sandbox network certification is currently pending because the required client/FBR token is not available.**

Therefore this repository must not contain or claim:

- fake Sandbox success responses;
- fake official FBR invoice numbers;
- fake legal seller identity;
- a fabricated Production token;
- false certification evidence.

Local demo preparation forces FBR transport to `Disabled`.

Production switching should follow `docs/fbr/FBR_PRODUCTION_CHECKLIST.md` and `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md`.

---

## Multi-site SaaS architecture

Ledgix uses native Frappe multi-tenancy:

```text
one maintained ledgix_saas codebase
        |
        +-- client-a.example.com -> separate Frappe site + database
        +-- client-b.example.com -> separate Frappe site + database
        +-- staging.example.com  -> separate Frappe site + database
```

Each client site has isolated business data, configuration and backups while sharing the maintained app release. Higher-isolation clients can move to dedicated infrastructure without changing the application model.

---

## Production deployment

Production helpers remain under `deploy/` and operational guides under `docs/production/`.

Typical production update flow is based on:

```text
git pull
bench --site <site> migrate
bench build --app ledgix_saas
service/process restart as appropriate
smoke/readiness checks
```

Use the provided deployment/update scripts rather than hand-editing ERPNext/Frappe core or production database tables.

---

## Backup and recovery

Before migrations, destructive maintenance or demo resets, take a site backup:

```bash
cd frappe-bench
bench --site <site> backup --with-files
```

Production backups should also be replicated off-server according to the deployment/recovery policy.

Existing repository gates include:

```text
scripts/run_backup_restore_static_gate.sh
scripts/run_backup_restore_runtime_gate.sh
```

---

## Testing and release gates

Useful current checks include:

```bash
# Repository/static validation
./scripts/ci_local.sh

# Completed migration/profile regression gate
./scripts/run_erpnext_phase13_final_gate.sh ledgix-erpnext.local

# Full Ledgix application tests
cd frappe-bench
bench --site ledgix-erpnext.local run-tests --app ledgix_saas --skip-test-records
```

The migration phase gates are retained as regression/evidence tooling even though the phases themselves are complete.

Before client testing, also run the deterministic demo-data verification and perform UI UAT for POS, barcode lookup, split payment, opening/closing, returns, B2B receivables, buying, stock/batch/serial behavior, reports, print formats, Inventory Intelligence and the network-inactive Tax & FBR Center.

---

## Documentation map

| Document | Purpose |
|---|---|
| `docs/architecture/CURRENT_ARCHITECTURE.md` | Current post-migration authority and product architecture |
| `docs/architecture/LEGACY_AUDIT.md` | Retained/frozen/obsolete legacy classification |
| `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md` | Complete tax/FBR architecture and operational safety |
| `docs/fbr/FBR_PRODUCTION_CHECKLIST.md` | FBR go-live checks |
| `docs/operations/LOCAL_DEMO_DATA.md` | Local backup/seed/verification workflow |
| `docs/local/` | Local installation/setup notes |
| `docs/production/` | Production deployment, security, backup and troubleshooting |
| `docs/archive/migration/` | Completed migration/release-hardening history and evidence |

---

## Security

Never commit:

- FBR tokens;
- database credentials;
- private keys;
- SSL private keys;
- backups;
- secrets files;
- production environment files.

Use the repository secret scanner:

```bash
./scripts/check_secrets.sh
```

See `docs/production/SECURITY.md` for production security guidance.

---

## Development rule

Before adding another custom Ledgix business DocType, verify that ERPNext does not already own the concept.

Prefer:

```text
ERPNext authority
+ minimal Ledgix extension metadata
+ custom Ledgix Page/UX only where it materially improves the product
```

Avoid any design that creates a second monetary, stock or accounting truth.

---

## License

Private/internal project unless a separate license is added. Define commercial ownership/licensing terms before public distribution or third-party reuse.
