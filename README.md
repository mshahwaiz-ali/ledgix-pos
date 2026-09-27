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

Current application stack:

```text
Frappe:   15.113.4 / version-15
ERPNext:  15.121.3 / version-15
Ledgix:   ledgix_saas + fbr_v1
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
cd ~/data_drive/ledgix-pos
```

Canonical local site:

```text
ledgix-erpnext.local
```

First-time/repair workflow:

```bash
./scripts/core/install.sh --local
./scripts/core/site_setup.sh --ensure
./scripts/core/start.sh
```

Useful status/smoke:

```bash
./scripts/core/site_setup.sh --status
./scripts/core/start.sh --status
./scripts/core/start.sh --smoke --site ledgix-erpnext.local
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
bash scripts/validation/ci_local.sh
```

Current local acceptance/readiness:

```bash
bash scripts/release/run_release_acceptance_readiness_gate.sh ledgix-erpnext.local
```

Final production acceptance:

```bash
bash scripts/release/run_ledgix_production_release_gate.sh \
  --site client.example.com \
  --url https://client.example.com \
  --release <approved-immutable-release>
```

The final gate validates evidence; it is not a replacement for deployment or real manual/FBR acceptance.

Historical phase gates remain regression/evidence tools for the completed migration only.

---

## Federal Tier-1 POS / IMS V1

The active implementation is `frappe-bench/apps/fbr_v1`. Submitted ERPNext `Sales Invoice` / `POS Invoice` and native returns/Credit Notes remain the business sources. Digital Invoicing V1.2 is frozen under `frappe-bench/apps/fbr_v12` and `docs/fbr/fbr_v12/` for historical reference only.

Key safety rules:

- historical `Ledgix Sale` submission is retired;
- FBR payloads use immutable invoice/line snapshots;
- general and Production network cutovers are separate and default off;
- Production also requires arming and complete profile/device/authority evidence;
- consolidated POS accounting Sales Invoices are not a second FBR source;
- `scheduler_events = {}` is intentional for FBR retransmission safety;
- an ambiguous Production POST becomes `Reconciliation Required`;
- real Sandbox/Production success evidence must never be fabricated.

Documentation:

```text
docs/fbr/README.md
docs/fbr/fbr_v1/README.md
docs/fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md
docs/fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md
```

Software implementation is verified locally at `e6f9b8f9986841584904a500f356e746ad1b415e`. Real client evidence, Sandbox acceptance, and Production activation remain external/pending; this is not a claim of FBR certification or Production acceptance.

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
ledgix-pos/
├── frappe-bench/
│   └── apps/
│       ├── ledgix_saas/      # product, ERPNext extensions and SaaS tooling
│       ├── fbr_v1/           # current Federal Tier-1 POS / IMS V1
│       └── fbr_v12/          # frozen Digital Invoicing V1.2 reference
├── deploy/                    # guarded production/backup/update helpers
├── docs/
│   ├── architecture/          # current authority + legacy boundaries
│   ├── fbr/fbr_v1/            # current V1 authority
│   ├── fbr/fbr_v12/           # frozen V1.2 records
│   ├── local/                 # local setup
│   ├── operations/            # operating dataset + ERP workflows
│   ├── production/            # production/client/release runbooks
│   └── archive/migration/     # completed migration history/evidence
├── scripts/                   # CI, readiness, release and guarded utilities
├── scripts/core/install.sh
├── scripts/core/site_setup.sh
└── scripts/core/start.sh
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
bash scripts/validation/check_secrets.sh
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
docs/fbr/README.md
docs/fbr/fbr_v1/README.md
docs/fbr/fbr_v1/FBR_V1_RUNTIME_ARCHITECTURE.md
docs/fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md
docs/fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md
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
