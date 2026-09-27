# Ledgix Application Map

**Repository:** `~/data_drive/ledgix-pos`
**Canonical local site:** `ledgix-erpnext.local`

## Current site stack

Install applications in dependency order:

1. `frappe` — framework and site runtime;
2. `erpnext` — business, accounting, stock, tax, payments, and invoice authority;
3. `ledgix_saas` — product UX, ERPNext extensions, onboarding, reporting, and SaaS/release tooling;
4. `fbr_v1` — current Federal Tier-1 POS / IMS V1 integration and evidence layer.

Verify the canonical local site with:

```bash
cd ~/data_drive/ledgix-pos/frappe-bench
bench --site ledgix-erpnext.local list-apps
```

Ledgix runs as one required application stack: Frappe -> ERPNext -> ledgix_saas -> fbr_v1. Ledgix-owned source lives directly in `frappe-bench/apps/ledgix_saas/` and `frappe-bench/apps/fbr_v1/`; there is no second outer app copy and no source-to-bench sync step. Frappe and ERPNext remain their upstream Git checkouts inside the same bench and their approved versions are part of the Ledgix release contract.

## Authority boundaries

ERPNext owns Company, Items, Customers, Suppliers, Sales/POS Invoices, returns, purchases, stock, tax, GL, payments, receivables, and totals. `ledgix_saas` must extend those native records rather than create parallel ledgers. `fbr_v1` owns only fiscal mapping, immutable snapshots, V1 serialization/transport, response/reconciliation evidence, offline/compliance/correction/closing evidence, print/QR metadata, and readiness.

`frappe-bench/apps/fbr_v12` is frozen Digital Invoicing V1.2 source reference. Do not install it alongside `fbr_v1` as an active client integration unless a separately approved migration/research task explicitly requires it.

## Normal local workflow

Use the repository-managed commands:

```bash
cd ~/data_drive/ledgix-pos
./scripts/core/install.sh --local
./scripts/core/site_setup.sh --ensure
./scripts/core/start.sh
./scripts/core/start.sh --smoke --site ledgix-erpnext.local
```

Use `bench migrate`, installation/removal, and build commands only when the relevant runbook explicitly calls for them. Production follows an approved immutable release and the production deployment runbooks; it does not follow a moving development branch.

## Current documentation

- [Current architecture](../architecture/CURRENT_ARCHITECTURE.md)
- [Local installation](../local/LOCAL_INSTALLATION.md)
- [Federal V1 documentation](../fbr/fbr_v1/README.md)
- [Production index](../production/README_PRODUCTION.md)
