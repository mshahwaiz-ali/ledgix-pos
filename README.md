# Ledgix POS

> **Retail POS and ERP product on Frappe v15 + ERPNext v15. ERPNext owns business, stock and accounting truth; Ledgix adds the focused retail UX, product shell, tax/FBR layer, onboarding and operational tooling.**

## Current status

- ERPNext-core migration: **COMPLETE**
- Migration phases 0–13: **CLOSED / ARCHIVED**
- Current business authority: **ERPNext**
- Frozen legacy Ledgix business ledgers: **READ-ONLY HISTORICAL EVIDENCE**
- Local operating/acceptance dataset: **COMPLETE / VERIFIED**
- FBR application-side integration: **IMPLEMENTED**
- Real FBR Sandbox certification: **EXTERNAL / PENDING**
- FBR Production activation: **NOT YET PRODUCTION-READY**

There is no Phase 14. New work should improve the current product/release state rather than restart the migration.

---

## Supported stack

Production release contract:

```text
Frappe:   15.113.4 / version-15
ERPNext:  15.121.3 / version-15
Ledgix:   ledgix_saas
Database: MariaDB
Queue:    Redis
```

The exact production pin lives in `deploy/release_contract.env`.

Do not vendor or modify ERPNext core. Ledgix extends ERPNext through the app layer.

---

## Architecture

ERPNext is authoritative for:

- Items, Item Groups, Price Lists and pricing
- Customers and Suppliers
- Sales Invoice / POS Invoice
- Payment Entry and receivables
- Purchase Order / Purchase Receipt / Purchase Invoice
- Warehouse, Stock Entry, Stock Reconciliation, Batch/Serial and Stock Ledger
- POS Opening / Closing
- accounting and financial reports

Ledgix intentionally owns:

- `ledgix-pos`
- Inventory Intelligence (`business-intelligence-center`)
- Tax & FBR Center (`ledgix-tax-center`)
- Setup Wizard (`ledgix-setup`)
- Business Profile / branding / Ledgix user UX
- FBR mapping, immutable compliance snapshots, guarded transport and audit logs
- onboarding/readiness/release evidence and SaaS tooling

Read first:

```text
docs/architecture/CURRENT_ARCHITECTURE.md
docs/architecture/LEGACY_AUDIT.md
docs/operations/ERP_WORKFLOWS.md
```

---

## Legacy boundary

Historical custom business DocTypes such as:

- `Ledgix Item`
- `Ledgix Customer`
- `Ledgix Supplier`
- `Ledgix Sale`
- `Ledgix Purchase`
- `Ledgix Payment`
- `Ledgix POS Shift`
- `Ledgix POS Hold`
- `Ledgix Stock Movement`

are not current business authorities.

They remain frozen only for migration/audit/reconciliation evidence until a separately approved schema-retirement project proves physical removal safe.

Compatibility endpoint names may remain, but current writes must resolve to ERPNext-native services.

---

## Main user surfaces

Ledgix keeps four focused product shortcuts:

1. **Ledgix POS** — fast retail checkout over ERPNext POS
2. **Inventory Intelligence** — ERPNext stock visibility/insights
3. **Tax & FBR Center** — mapping, readiness, logs and guarded FBR controls
4. **Setup Wizard** — configuration-only Business Profile onboarding

Workspace/business areas link to native ERPNext records wherever ERPNext is authoritative.

Frappe/ERPNext permissions remain the security authority; Business Profile visibility does not grant access by itself.

---

## Local development

Repository:

```bash
cd ~/data_drive/pos
```

Canonical local site:

```text
ledgix-erpnext.local
```

First-time/repair workflow:

```bash
./install.sh --local
./site_setup.sh --ensure
./start.sh
```

Useful status/smoke:

```bash
./site_setup.sh --status
./start.sh --status
./start.sh --smoke --site ledgix-erpnext.local
```

Current local setup authority:

```text
docs/local/LOCAL_INSTALLATION.md
```

---

## Local operating/acceptance dataset

Current dataset marker:

```text
LEDGIX-RETAIL-OPERATING-V1
```

The canonical dataset on `ledgix-erpnext.local` is already completed and verified. It exercises realistic ERPNext-native Retail, B2B, purchasing, stock, returns, payments, receivables and split-payment behavior.

**Do not casually reset or reseed it.** Use the read-only verifier first.

Documentation:

```text
docs/operations/LOCAL_DEMO_DATA.md
```

The filename is retained for compatibility, but the document now describes the operating/acceptance dataset rather than an old disposable V2 demo.

FBR transport remains disabled for this local dataset.

---

## Validation

Repository validation:

```bash
bash scripts/ci_local.sh
```

Current local acceptance/readiness:

```bash
bash scripts/run_release_acceptance_readiness_gate.sh ledgix-erpnext.local
```

Final production acceptance:

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site client.example.com \
  --url https://client.example.com \
  --release <approved-immutable-release>
```

The final gate validates evidence; it is not a replacement for deployment or real manual/FBR acceptance.

Historical phase gates remain regression/evidence tools for the completed migration only.

---

## FBR

Current FBR sources are submitted ERPNext `Sales Invoice` / `POS Invoice` and their native returns/Credit Notes.

Key safety rules:

- historical `Ledgix Sale` submission is retired;
- FBR payloads use immutable invoice/line snapshots;
- Production POST requires the explicit Production interlock;
- consolidated POS accounting Sales Invoices are not a second FBR source;
- `scheduler_events = {}` is intentional for FBR retransmission safety;
- an ambiguous Production POST becomes `Reconciliation Required`;
- real Sandbox/Production success evidence must never be fabricated.

Documentation:

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
docs/production/fbr_sandbox_production_activation.md
```

The older `FBR_TAX_LAYER.md` and `FBR_TAX_MODULE.md` filenames are retained only as deprecated historical pointers.

---

## Production / SaaS

Intended model:

```text
one approved Ledgix release per bench
        |
        +-- client-a Frappe site + DB
        +-- client-b Frappe site + DB
        +-- client-c Frappe site + DB
```

Each client receives separate business data, credentials, FBR configuration and backup/release evidence.

Start production work here:

```text
docs/production/README_PRODUCTION.md
docs/production/DEPLOYMENT.md
docs/production/PRODUCTION_CHECKLIST.md
```

Detailed runbooks cover fresh provisioning, immutable updates, shared-bench releases, backup/restore, onboarding, hardware UAT, FBR activation and the final release gate.

Production uses an approved immutable SHA/tag and verified recovery evidence. A moving `main` branch is development source of truth, not production release identity.

---

## Repository map

```text
pos/
├── apps/ledgix_saas/          # Ledgix Frappe app
├── deploy/                    # guarded production/backup/update helpers
├── docs/
│   ├── architecture/          # current authority + legacy boundaries
│   ├── fbr/                   # current FBR architecture/checklists
│   ├── local/                 # local setup
│   ├── operations/            # operating dataset + ERP workflows
│   ├── production/            # production/client/release runbooks
│   └── archive/migration/     # completed migration history/evidence
├── scripts/                   # CI, readiness, release and guarded utilities
├── install.sh
├── site_setup.sh
└── start.sh
```

---

## Security

Never commit:

- FBR tokens
- site/database passwords
- private keys/certificates
- client API secrets
- `site_config` recovery inputs
- database/file backups
- generated secret/evidence files containing credentials

Local credentials live under `.secrets/sites/`; production provisioning stores owner-only credentials outside the repository (default `~/.config/ledgix/sites/`).

Run:

```bash
bash scripts/check_secrets.sh
```

before release work.

See `docs/production/SECURITY.md`.

---

## Documentation index

### Current architecture / operations

```text
docs/architecture/CURRENT_ARCHITECTURE.md
docs/architecture/LEGACY_AUDIT.md
docs/operations/ERP_WORKFLOWS.md
docs/operations/LOCAL_DEMO_DATA.md
docs/local/LOCAL_INSTALLATION.md
```

### Current FBR

```text
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
docs/fbr/FBR_PRODUCTION_CHECKLIST.md
```

### Current production

```text
docs/production/README_PRODUCTION.md
docs/production/DEPLOYMENT.md
docs/production/PRODUCTION_CHECKLIST.md
docs/production/final_release_gate.md
```

### Historical migration evidence

```text
docs/archive/migration/
```

Archived migration documents may contain historical phase-time status wording or old internal paths. They are preserved as snapshots and are not current operating instructions.
