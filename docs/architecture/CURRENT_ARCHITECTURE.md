# Ledgix Current Architecture

**Status:** CURRENT  
**Reviewed:** 2026-09-17  
**Repository authority:** `main`  
**Reviewed HEAD:** `74ae6c61c6e6cb55670d64afb2db0892916a22a0`  
**Supported stack:** Frappe `15.113.4` + ERPNext `15.121.3` + `ledgix_saas`

## Purpose

This document is the current architecture authority for Ledgix after the ERPNext-core migration.

Historical migration plans and phase evidence live under `docs/archive/migration/`. They explain how the architecture was reached, but they are **not** the operating authority for current development or administration.

The governing rule is:

> **One business concept = one authoritative source of truth.**

ERPNext owns standard business masters, transactions, stock and accounting. Ledgix owns the product experience and the product-specific configuration/compliance capabilities that ERPNext does not provide directly.

Ledgix does not vendor, fork or patch ERPNext core.

---

## 1. Current status

| Area | Status | Current meaning |
|---|---|---|
| ERPNext Core Migration | **COMPLETE** | Phases 0–13 are closed. There is no Phase 14. |
| ERPNext business authority | **CURRENT** | New masters, sales, purchases, payments, stock and accounting use ERPNext-native documents/ledgers. |
| Legacy Ledgix business ledgers | **COMPLETE / FROZEN HISTORY** | Historical custom business records remain only where required for migration/audit evidence. They are not active transaction authority. |
| Local operating/acceptance dataset | **COMPLETE / VERIFIED** | `LEDGIX-RETAIL-OPERATING-V1` passed `demo_data.verify()` with `ok = true` on `ledgix-erpnext.local`. |
| Ledgix POS / product shell | **CURRENT** | Retained Ledgix UX runs over ERPNext-native authority. |
| Tax/FBR application layer | **CURRENT** | ERPNext invoices are the source transactions; Ledgix owns compliance mapping, snapshots, transport controls and audit. |
| Real FBR Sandbox certification | **DEFERRED / EXTERNAL INPUT REQUIRED** | Real seller identity/token and actual FBR network evidence are still required. |
| FBR Production go-live | **NOT YET PRODUCTION-READY** | Production must remain unarmed until client-specific Sandbox proof and production activation gates pass. |
| Production release tooling | **IMPLEMENTED** | Release/update/backup/provisioning/final-gate tooling exists. |
| Real client production acceptance | **NOT YET PRODUCTION-READY** | Requires client-specific deployment evidence, verified backup, online smoke, manual/device UAT and FBR certification when FBR Production is in scope. |

---

## 2. Authority model

| Business concept | Current authority |
|---|---|
| Item / category | ERPNext `Item`, `Item Group` |
| Customer | ERPNext `Customer` |
| Supplier | ERPNext `Supplier` |
| Price list / item price / pricing rules | ERPNext `Price List`, `Item Price`, `Pricing Rule` |
| Retail sale | ERPNext `POS Invoice` |
| B2B sale | ERPNext `Sales Invoice` |
| Retail return | ERPNext return `POS Invoice` |
| B2B return / credit note | ERPNext return `Sales Invoice` |
| Retail tender rows / split payment | Native POS invoice payment rows (`Sales Invoice Payment` child table in ERPNext v15) |
| Customer payment / allocation | ERPNext `Payment Entry` + invoice references |
| Customer outstanding / overdue | ERPNext invoice/GL/receivable state |
| Purchase | ERPNext `Purchase Order`, `Purchase Receipt`, `Purchase Invoice` |
| Supplier payment / payable | ERPNext `Payment Entry` + AP/GL state |
| Warehouse / stock | ERPNext `Warehouse`, `Stock Ledger Entry`, `Bin` |
| Stock movement / correction | ERPNext `Stock Entry`, `Stock Reconciliation`, native document stock effects |
| Batch / serial | ERPNext `Batch`, `Serial No`, Serial and Batch Bundle |
| POS shift | ERPNext `POS Opening Entry`, `POS Closing Entry` |
| Accounting | ERPNext GL, AR/AP, tax rows and Company accounts |
| FBR commercial source | Submitted ERPNext `Sales Invoice` / `POS Invoice` and their native returns |
| FBR compliance state | Ledgix fields/snapshots/logs attached to the ERPNext source transaction |

ERPNext totals, ledgers and outstanding balances must not be shadowed by a second Ledgix monetary engine.

---

## 3. What Ledgix intentionally owns

Ledgix remains more than a theme over ERPNext. The retained layer is intentional, but it must never become a second financial or stock engine.

### Product pages

| Surface | Responsibility |
|---|---|
| `ledgix-pos` | Fast retail/B2B selling UX over ERPNext Items, Customers, pricing, POS opening/closing, POS Invoice, Sales Invoice and native payment/stock state. |
| `business-intelligence-center` | Inventory Intelligence over ERPNext stock, purchasing and selling data. It is not a separate inventory ledger. |
| `ledgix-tax-center` | Tax/FBR setup, readiness, submission status and audit UX over ERPNext-native invoice sources. |
| `ledgix-setup` | Configuration-only client onboarding using existing ERPNext Company/Price List/Warehouse/POS Profile records and Ledgix Business Profile. |

### Retained Ledgix configuration/compliance records

Current Ledgix-specific records include, where applicable:

- `Ledgix Business Profile`;
- `Ledgix Brand Settings`;
- `Ledgix User Profile` as product/profile UX metadata only, **not** authorization authority;
- `Ledgix Tax Profile`;
- `Ledgix Tax Category`;
- `Ledgix Tax Rate`;
- `Ledgix Item Tax Profile` linked to ERPNext `Item`;
- `Ledgix FBR Settings`;
- `Ledgix FBR Submission Log`;
- `Ledgix Tax Audit Log`;
- legacy-retirement state/digest controls;
- release/readiness/UAT evidence required by the current product.

These records extend ERPNext; they do not replace ERPNext Item, Customer, Supplier, invoice, payment, stock or accounting authority.

---

## 4. Compatibility/service boundaries

Ledgix keeps compatibility endpoints where the existing UI or older clients still call historical method names. Compatibility naming does **not** imply legacy business authority.

Key current boundaries include:

```text
api/product_shell.py
api/pos_compat.py
services/erpnext_pos.py
services/erpnext_selling.py
services/erpnext_buying_inventory.py
services/erpnext_reporting.py
services/erpnext_reporting_compat.py
api/fbr_native.py
api/client_setup.py
```

`hooks.py` explicitly routes old POS/selling RPC names to the ERPNext-native compatibility layer. The historical `Ledgix Sale` FBR submit endpoint is routed to a fail-closed legacy guard rather than allowed to create a second official submission path.

---

## 5. Retail POS architecture

```text
Ledgix POS
  -> ERPNext POS Profile
  -> active POS Opening Entry
  -> ERPNext Item / Customer / Price List / stock state
  -> ERPNext POS Invoice
  -> native payment rows / split tenders
  -> Stock Ledger + GL
  -> optional Ledgix FBR workflow on the same POS Invoice
  -> POS Closing Entry
  -> ERPNext native POS consolidation
```

### Opening and shift state

`services/erpnext_pos.py` resolves the active ERPNext `POS Profile` and `POS Opening Entry`. Ledgix does not create a new `Ledgix POS Shift` for current operation.

### Sale and split payment

A retail checkout creates/submits an ERPNext `POS Invoice`. Split tender is represented by multiple native ERPNext payment rows; no `Ledgix Payment` is created for the retail transaction.

### Holds

A held retail cart is a draft ERPNext `POS Invoice`. A held B2B cart is a draft ERPNext `Sales Invoice`. Ledgix metadata may identify/restore the hold, but the draft ERPNext document owns the commercial values.

### Return

A retail return is a native ERPNext return `POS Invoice` linked to the original invoice. Source rates remain authoritative; client-supplied replacement return rates are not allowed to rewrite the original sale economics.

### Closing and consolidation

ERPNext `POS Closing Entry` owns shift closing and consolidation. The consolidated `Sales Invoice` created by ERPNext is an accounting consolidation document; it is **not** a second FBR source transaction.

---

## 6. B2B selling, credit and payments

```text
Customer / Item / ERPNext pricing
  -> Sales Invoice
  -> optional stock effect (`update_stock` when applicable)
  -> Payment Entry allocation(s)
  -> ERPNext outstanding / AR / GL
  -> native Sales Invoice return / Credit Note
  -> optional refund Payment Entry
  -> optional Ledgix FBR workflow on the same ERPNext source
```

`services/erpnext_selling.py` creates ERPNext Sales Invoices and uses native pricing. Ledgix client IDs are idempotency/routing metadata, not a second invoice ledger.

### Customer payment behavior

Ledgix-originated B2B payments are submitted as ERPNext `Payment Entry` documents and allocated to submitted Sales Invoices through native references. Invoice outstanding, overdue and customer receivable values come from ERPNext state.

A native ERPNext Payment Entry may still be used directly for workflows such as unapplied customer advances; Ledgix does not need to duplicate that capability.

### Credit Note / refund behavior

B2B returns use ERPNext's native Sales Invoice return mapper. Returned rows retain the original submitted line rate. A customer refund is an ERPNext `Payment Entry` resolved as Payment Type `Pay` against the negative Credit Note.

---

## 7. Purchasing architecture

Supported current paths are ERPNext-native:

```text
Full buying:
Supplier
  -> Purchase Order
  -> Purchase Receipt
  -> Purchase Invoice
  -> Payment Entry

Direct/small-shop buying:
Supplier
  -> Purchase Invoice (`update_stock = 1` when inventory is enabled)
  -> Payment Entry
```

`services/erpnext_buying_inventory.py` is the Ledgix compatibility/service boundary. It writes only standard ERPNext purchasing/payment/stock documents.

Purchase returns and AP remain native ERPNext behavior. `Ledgix Purchase` is not a current purchasing ledger.

---

## 8. Inventory and stock architecture

```text
ERPNext Item + Warehouse
  -> Purchase/return/sales stock effects
  -> Stock Entry / Stock Reconciliation
  -> Batch / Serial No / Serial and Batch Bundle
  -> Stock Ledger Entry + Bin
  -> ERPNext reports / Ledgix Inventory Intelligence
```

Rules:

- quantity authority is ERPNext Stock Ledger / `Bin`;
- valuation and COGS are ERPNext-owned;
- internal receipt/issue/transfer uses `Stock Entry`;
- corrections use `Stock Reconciliation`;
- Batch/Serial identity uses ERPNext-native records/bundles;
- Inventory Intelligence is read/presentation logic only;
- current code must not write `Ledgix Stock Movement`, `Ledgix Stock Lot` or `Ledgix Stock Serial` as live ledgers.

---

## 9. Tax and FBR architecture

Detailed current authority is documented in `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md`.

The current flow is:

```text
ERPNext Sales/POS Invoice
  -> ERPNext monetary tax rows / totals / GL
  -> immutable Ledgix legal/FBR header + line snapshots
  -> Ledgix readiness + payload
  -> controlled Sandbox/Production transport
  -> Ledgix FBR Submission Log
  -> official FBR reference/QR/status on the same ERPNext invoice
```

Important boundaries:

- ERPNext owns monetary totals and accounting impact.
- Ledgix owns FBR/legal classification that generic ERPNext tax rows do not fully express.
- Historical `Ledgix Sale` / `Ledgix Sales Return` are not valid new FBR transaction sources.
- Production POST requires explicit arming and client-specific readiness.
- `hooks.py` currently registers **no automatic FBR retry/offline scheduler**. Ambiguous Production POST outcomes must enter reconciliation handling rather than blind retransmission.
- Local operating-data generation keeps FBR transport disabled.

**Current certification state:** application infrastructure exists, but real Sandbox network certification is still pending real seller identity/token/evidence. Production FBR must therefore be treated as **NOT YET PRODUCTION-READY**.

---

## 10. Product shell, roles and permissions

The Ledgix workspace is a curated navigation layer. It is not an authorization engine.

Current workspace groups are:

- Sales & POS;
- Catalog & Pricing;
- Purchasing;
- Inventory & Stock;
- Reports & Accounting;
- Tax & FBR;
- Administration.

`api/product_shell.py` computes role/profile-aware visibility. The product keeps these shortcut surfaces:

- Ledgix POS;
- Inventory Intelligence;
- Tax & FBR Center;
- Setup Wizard.

Role intent:

- **Ledgix Cashier** — selling/POS functions allowed by the selected profile and ERPNext permissions;
- **Ledgix Manager** — operational buying/stock/reporting/FBR visibility where profile features allow;
- **Ledgix Admin** — product configuration plus operational access;
- **System Manager** — full Frappe/ERPNext platform administration.

`Ledgix Business Profile` feature flags curate what users see. ERPNext/Frappe DocType/Page/Report permissions remain the security authority.

---

## 11. Business Profiles

One Ledgix codebase supports the configured product profiles:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

Profile flags can enable/hide POS, B2B, buying, inventory, advanced inventory, accounting and FBR product surfaces. They do not create a client-specific fork and do not grant server permissions.

The Setup Wizard is configuration-only: it selects/validates existing ERPNext Company, Selling Price List, Warehouse and POS Profile records as required by the selected profile. It must not silently create a parallel business master engine.

---

## 12. Legacy boundary

See `docs/architecture/LEGACY_AUDIT.md` for the complete frozen set.

The active distinction is:

- **current business activity** -> ERPNext native documents/ledgers;
- **retained Ledgix product/compliance capability** -> supported custom pages/configuration/audit records;
- **historical duplicate Ledgix business records** -> frozen audit/migration evidence only.

Physical schema presence is not active authority.

### Old behavior that must not be used for new business activity

Do not create new current-operation records in the retired parallel business models, including:

- `Ledgix Item` / `Ledgix Category` as product masters;
- `Ledgix Customer` / `Ledgix Supplier` as commercial masters;
- `Ledgix Sale` / `Ledgix Sales Return` as sale/return ledgers;
- `Ledgix Purchase` as purchasing authority;
- `Ledgix Payment` as payment/receivable authority;
- `Ledgix POS Shift` / `Ledgix POS Hold` as current POS authority;
- `Ledgix Stock Movement` / `Ledgix Stock Lot` / `Ledgix Stock Serial` as live stock ledgers.

Compatibility resolvers may still understand legacy identifiers so historical clients/data can be mapped to native ERPNext records. That is not permission to resume legacy writes.

---

## 13. Verified local operating-data milestone

The canonical integration site currently has a completed realistic acceptance dataset:

```text
dataset: LEDGIX-RETAIL-OPERATING-V1
company: Ledgix ERPNext Integration
POS profile: Main Counter POS
items: 52
customers: 16
suppliers: 8
POS sales: 108
B2B sales: 12
total sales: 120
POS returns: 4
B2B returns: 3
Payment Entries: 9
Purchase Invoices: 6
Stock Entries: 88
split-payment POS invoices: 30
trade outstanding: 39991.50
trade overdue: 28197.50
active POS opening: POS-OPE-2026-00030
FBR transport disabled: true
negative retail bins: none
unconsolidated managed POS: none
visible old artifacts: none
verifier: ok = true
```

The dedicated return opening `POS-OPE-2026-00029` is closed through `POS-CLO-2026-00021`. The current acceptance-testing opening is `POS-OPE-2026-00030`.

This dataset is completed operating/acceptance evidence and should **not** be casually cleaned, rebuilt or reset. See `docs/operations/LOCAL_DEMO_DATA.md` for the operating-data policy; that document is being updated to reflect this completed V1 state.

---

## 14. Reporting architecture

Ledgix retains focused reports/compatibility adapters where they improve product UX, but values must come from ERPNext-native documents/ledgers.

The workspace also exposes selected ERPNext reports such as:

- Stock Balance;
- Stock Ledger;
- Accounts Receivable;
- General Ledger;
- Profit and Loss Statement.

The objective is a focused Ledgix operator/manager experience, not a duplicate reporting database.

---

## 15. Multi-site SaaS model

Ledgix follows native Frappe site isolation:

```text
one approved Ledgix application revision
        |
        +-- client-a.example.com -> separate site + database
        +-- client-b.example.com -> separate site + database
        +-- staging.example.com  -> separate site + database
```

Each client keeps independent business data, ERPNext setup, Business Profile, FBR credentials/configuration, backups and release evidence. Shared benches may host multiple small clients under the documented cohort-update rules. Larger clients can move to dedicated infrastructure without changing application architecture.

---

## 16. Backup and release boundary

Site backups use supported Frappe backup/restore flows and must include database/files required by the recovery objective. Production backup evidence should also be copied off the application server where required by the deployment policy.

Production release approval is separate from local architecture/acceptance proof. A real client release still requires the production runbooks and final release gate under `docs/production/`.

---

## 17. Design rule for future development

Before adding a new Ledgix DocType, ledger or service for a business concept, ask:

1. Does ERPNext already own this concept?
2. Can the requirement be represented by ERPNext fields/workflow plus small Ledgix metadata?
3. Is the requirement primarily a better product UX over native documents?
4. Would the change create a second monetary, stock, receivable/payable or accounting truth?

If the answer to #4 is yes, the design conflicts with the current architecture unless a separately documented architecture decision proves why the exception is necessary.
