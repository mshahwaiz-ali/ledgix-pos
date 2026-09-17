# Ledgix Current Architecture

## Product model

Ledgix is a retail/B2B POS and ERP product built on Frappe/ERPNext v15.

The post-migration architecture intentionally separates **business authority** from **Ledgix product experience**:

- **ERPNext** owns business masters, transactions, stock, accounting, receivables/payables and POS shift documents.
- **Ledgix** owns the simplified product shell, retained custom workflows, business profiles, branding, FBR/tax intelligence, compliance audit, reporting compatibility and deployment/SaaS orchestration.

Ledgix does not vendor or patch ERPNext core.

---

## Authoritative data model

| Business concept | Authority |
|---|---|
| Item / category | ERPNext `Item`, `Item Group` |
| Customer | ERPNext `Customer` |
| Supplier | ERPNext `Supplier` |
| Price list / item price / pricing rules | ERPNext `Price List`, `Item Price`, `Pricing Rule` |
| Retail sale | ERPNext `POS Invoice` |
| B2B sale | ERPNext `Sales Invoice` |
| Retail return | ERPNext POS Invoice return |
| B2B return / credit note | ERPNext Sales Invoice return |
| Customer/supplier payment | ERPNext `Payment Entry` or native POS payment rows |
| Purchase | ERPNext `Purchase Order`, `Purchase Receipt`, `Purchase Invoice` |
| Warehouse / stock | ERPNext `Warehouse`, Stock Ledger, `Bin` |
| Stock movement | ERPNext `Stock Entry`, `Stock Reconciliation`, native purchase/sales stock effects |
| Batch / serial | ERPNext `Batch`, `Serial No`, Serial and Batch Bundle |
| POS shift | ERPNext `POS Opening Entry`, `POS Closing Entry` |
| Accounting | ERPNext GL, AR/AP, tax rows and company accounts |
| FBR submission source | Submitted ERPNext Sales/POS Invoice |

---

## Retained Ledgix product UX

Four custom pages remain intentional first-class product surfaces:

### `ledgix-pos`

A simplified retail/B2B selling screen backed by ERPNext Items, Customers, pricing, POS Profile, POS Opening/Closing, POS Invoice, Sales Invoice and native payment/stock state.

It supports the Ledgix-specific UX for:

- fast item/barcode search;
- retail vs B2B channel routing;
- native pricing and authorized discount/rate controls;
- split payment;
- hold/resume using ERPNext draft invoices plus Ledgix metadata;
- native POS returns;
- shift/opening state.

### `business-intelligence-center`

Inventory Intelligence reads ERPNext-native stock, buying and selling activity and presents a product-specific operational view. It is not a separate stock ledger.

### `ledgix-tax-center`

Tax/FBR configuration, readiness, submission state and audit UX over ERPNext invoice authority.

### `ledgix-setup`

Client/business-profile setup and product configuration without replacing ERPNext masters that ERPNext already owns.

---

## Product shell and workspace

The public Ledgix workspace is a curated navigation layer, not a permission system.

Current groups:

- Quick Actions
- Sales & POS
- Catalog & Pricing
- Purchasing
- Inventory & Stock
- Reports & Accounting
- Tax & FBR
- Administration

`api/product_shell.py` computes role/business-profile visibility. `public/js/ledgix_phase11_product_shell.js` hides non-applicable navigation and compacts the visible workspace. ERPNext/Frappe permission checks remain authoritative when a target is opened.

### Role intent

- **Cashier** — retail/selling functions appropriate to the profile.
- **Manager** — operational buying/stock/reporting/FBR visibility as profile features allow.
- **Admin** — configuration plus operational access.
- **System Manager** — full Frappe/ERPNext administration; product shell does not try to reduce system authority.

---

## Selling architecture

### Retail

```text
Ledgix POS
  -> ERPNext POS Profile / active POS Opening Entry
  -> ERPNext Item + Price List + Customer
  -> ERPNext POS Invoice
  -> native POS payment rows / split tenders
  -> Stock Ledger + GL
  -> optional Ledgix FBR workflow
  -> POS Closing Entry / ERPNext consolidation
```

### B2B

```text
Ledgix POS or ERPNext-native B2B flow
  -> ERPNext Customer / Item / pricing
  -> ERPNext Sales Invoice
  -> ERPNext Payment Entry / Accounts Receivable
  -> Stock Ledger where update_stock applies
  -> optional Ledgix FBR workflow
```

Core compatibility/service boundaries include:

```text
api/pos_compat.py
services/erpnext_pos.py
services/erpnext_selling.py
```

Old method names may remain for compatibility, but new documents are native ERPNext documents.

---

## Buying and inventory architecture

```text
Supplier
  -> Purchase Order
  -> Purchase Receipt
  -> Purchase Invoice
  -> Payment Entry

Warehouse / Item
  -> Stock Entry / Stock Reconciliation
  -> Batch / Serial No / Serial and Batch Bundle
  -> Stock Ledger Entry + Bin
  -> Inventory Intelligence / ERPNext reports
```

`services/erpnext_buying_inventory.py` is the Ledgix compatibility/service boundary for native purchasing and stock operations.

It deliberately does not mutate `Ledgix Purchase`, `Ledgix Stock Movement`, `Ledgix Stock Lot` or `Ledgix Stock Serial` as current ledgers.

---

## Reporting architecture

Ledgix retains focused reports/compatibility adapters where they improve the product UX, but values come from ERPNext-native documents/ledgers.

The workspace also links directly to selected ERPNext reports:

- Stock Balance
- Stock Ledger
- Accounts Receivable
- General Ledger
- Profit and Loss Statement

The goal is useful operator/manager reporting, not a dump of every ERPNext report.

---

## Tax/FBR architecture

See `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md`.

In short:

```text
ERPNext invoice
 -> immutable Ledgix tax/FBR snapshot
 -> readiness / payload
 -> controlled FBR transport
 -> submission log
 -> official reference/QR/status on same ERPNext invoice
```

A consolidated POS Sales Invoice is accounting consolidation, not a duplicate FBR source.

---

## Business Profiles

Ledgix Business Profile flags shape the product experience for different client types, for example whether a client uses:

- POS;
- Sales Invoice/B2B;
- buying;
- inventory;
- advanced inventory;
- accounting workspace;
- FBR.

These flags hide/enable product surfaces but do not grant permissions on their own.

This allows a light client that only wants selling/invoicing/FBR to avoid unnecessary stock-heavy navigation while a full retailer can use purchasing, warehouses, stock and accounting.

---

## Legacy history

See `docs/architecture/LEGACY_AUDIT.md`.

The key distinction is:

- obsolete **active authority/navigation** is retired;
- historical Phase-12 legacy tables/rows remain frozen where required for audit/migration evidence.

Do not interpret physical schema presence as current product authority.

---

## Multi-site SaaS model

Ledgix follows native Frappe multi-site principles:

```text
one maintained app/codebase
        |
        +-- client-a.example.com -> separate site + database
        +-- client-b.example.com -> separate site + database
        +-- staging.example.com  -> separate site + database
```

Each client site keeps independent business data/configuration/backups. Shared application code is deployed through the bench/app release process.

Large or higher-isolation clients can be moved to dedicated infrastructure without changing the application authority model.

---

## Backup and recovery

Backups are site-level Frappe backups and must include database/files as required by the recovery objective. Production backups should also be copied off the application server.

Before destructive local demo reset or migration operations:

```bash
bench --site <site> backup --with-files
```

Backup/restore runtime gates already exist under `scripts/` and deployment docs.

---

## Design rule for future development

Before adding a new Ledgix DocType for a business concept, ask:

1. Does ERPNext already own this concept?
2. Can the requirement be represented by ERPNext fields/workflow plus small Ledgix metadata?
3. Is the requested UI a better candidate for a custom Page over ERPNext-native documents?
4. Would a new DocType create a second monetary/stock/accounting truth?

If the answer to #4 is yes, the design is wrong unless there is a very specific documented exception.
