# Ledgix POS — ERPNext Core Migration Master Plan

**Status:** ACTIVE MASTER PLAN  
**Decision date:** 2026-09-16  
**Repository:** `mshahwaiz-ali/pos`  
**Target stack:** Frappe v15 + ERPNext v15 + `ledgix_saas`  
**Supersedes:** the architecture decision in `docs/plan/new_plan.md` that Ledgix V2 has no ERPNext dependency.

---

## 1. Executive Decision

Ledgix will remain **one product**, but ERPNext will become the authoritative business engine underneath it.

Technically the site will have both `erpnext` and `ledgix_saas` installed. For the user there will still be one Ledgix experience: one site, one database, one login, one company context, one permission system, one Desk, and one curated Ledgix workspace.

```text
                         LEDGIX
                           |
                Curated Ledgix Workspace
                           |
          +----------------+----------------+
          |                                 |
     ERPNext Core                     Ledgix Layer
          |                                 |
 Items / Customers / Suppliers          FBR / PRAL
 Sales / Purchases / Returns             Tax & FBR Center
 Stock / Valuation / Warehouses          Product UX
 Pricing / Payments / AR / AP            Selected POS UX
 Accounting / Ledgers                    Intelligence
 Serial / Batch                          Branding / Prints
```

### Core architecture rule

> **One business concept = one source of truth.**

We will not maintain permanent two-way copies such as:

- `Ledgix Item <-> ERPNext Item`
- `Ledgix Sale <-> Sales Invoice`
- `Ledgix Payment <-> Payment Entry`
- `Ledgix Stock Movement <-> Stock Ledger Entry`

During migration, old Ledgix documents may remain available for compatibility and reconciliation, but only one side becomes authoritative before the old side is retired.

### ERPNext core must not be forked

Ledgix must not copy ERPNext source code or modify ERPNext core files. We will extend standard DocTypes and workflows through supported Frappe mechanisms such as hooks, custom fields, events, permissions, fixtures, reports, and custom pages.

---

## 2. Why We Are Changing the Architecture

The current repository has evolved into a useful but increasingly large custom ERP engine.

The current code independently owns or recalculates:

- item/catalog data;
- customers and suppliers;
- price lists and item prices;
- retail and B2B sales;
- sales returns;
- purchases;
- stock movements;
- moving-average valuation;
- lots and serial numbers;
- payment methods;
- payments and invoice allocations;
- receivables, overdue and available credit;
- POS shifts;
- financial tax calculations;
- FBR tax snapshots and submission state.

The custom POS then calls those custom services, and the current workspace exposes the custom records directly.

That architecture works, but it duplicates business logic ERPNext already maintains. The migration goal is therefore **not a UI rewrite first**. The main goal is to remove duplicate financial, stock, pricing, buying, selling and receivable engines while preserving the Ledgix work that is genuinely product-specific.

---

## 3. Repository Audit Baseline

The following current areas were reviewed before locking this plan.

### 3.1 Application and dependency layer

- `apps/ledgix_saas/hooks.py`
- `apps/ledgix_saas/pyproject.toml`
- `install.sh`
- `site_setup.sh`

Current state: Ledgix declares only Frappe as a bench dependency and does not yet require ERPNext. The site installer treats ERPNext as a system app and does not install/fetch it as part of the normal Ledgix site flow.

### 3.2 Core custom business engine

- `services/sales.py`
- `services/stock.py`
- `services/pricing.py`
- `services/payments.py`
- `services/receivables.py`
- `services/tax.py`
- `api/taxation.py`

### 3.3 Main custom transactional DocTypes

- `Ledgix Item`
- `Ledgix Category`
- `Ledgix Customer`
- `Ledgix Supplier`
- `Ledgix Sale` / `Ledgix Sale Item`
- `Ledgix Sales Return` / return rows
- `Ledgix Purchase` / `Ledgix Purchase Item`
- `Ledgix Payment` / `Ledgix Payment Allocation`
- `Ledgix Payment Method`
- `Ledgix Price List` / `Ledgix Item Price`
- `Ledgix Stock Movement`
- `Ledgix Stock Lot` / allocation
- `Ledgix Stock Serial`
- `Ledgix POS Shift`
- `Ledgix POS Hold`
- generic Ledgix tax records

### 3.4 Product-specific layers worth preserving

- `ledgix/page/ledgix_pos`
- `ledgix/page/ledgix_tax_center`
- `ledgix/page/business_intelligence_center`
- FBR API/client/settings/preflight/payload/submission/reconciliation logic
- FBR Submission Log
- FBR Correction Request
- Tax Audit Log
- FBR-aware print formats and QR handling
- Brand Settings and Ledgix branding
- Ledgix roles and curated workspace concept

### 3.5 Important audit conclusion

The current POS is not just a thin UI. Its backend directly uses Ledgix Customer, Item, Price List, Item Price, Payment Method, POS Shift, Sale, custom tax calculation and custom receivables. Likewise FBR payload generation directly loads Ledgix Sale, Ledgix Customer, Ledgix Item and Ledgix return records. BI is also tightly coupled to custom lots, serials, purchases and sales.

Therefore, **nothing major is deleted first**. We move authority module-by-module, prove parity, switch reads/writes, then retire the duplicate model.

---

## 4. Final Ownership Matrix

| Current Ledgix concept | Target authority | Final decision |
| --- | --- | --- |
| Ledgix Item | ERPNext `Item` | Replace |
| Ledgix Category | ERPNext `Item Group` | Replace |
| Ledgix Customer | ERPNext `Customer` + Ledgix FBR fields | Replace + Extend |
| Ledgix Supplier | ERPNext `Supplier` | Replace |
| Ledgix Price List | ERPNext `Price List` | Replace |
| Ledgix Item Price | ERPNext `Item Price` | Replace |
| Custom pricing service | ERPNext pricing + Pricing Rules | Replace |
| Ledgix Sale | ERPNext `Sales Invoice` / `POS Invoice` | Replace |
| Ledgix Sale Item | Standard invoice child rows | Replace |
| Ledgix Sales Return | ERPNext Return / Credit Note | Replace |
| Ledgix Purchase | ERPNext Purchase Invoice / Purchase Receipt / Purchase Order as needed | Replace |
| Ledgix Payment Method | ERPNext `Mode of Payment` | Replace |
| Ledgix Payment | ERPNext `Payment Entry` or native POS payment rows where appropriate | Replace |
| Ledgix Payment Allocation | ERPNext payment references/reconciliation | Replace |
| Custom receivables | ERPNext AR/payment ledger | Replace |
| Ledgix Stock Movement | ERPNext Stock Ledger / Stock Entry | Replace |
| Ledgix Stock Lot | ERPNext Batch | Replace |
| Ledgix Stock Serial | ERPNext Serial No | Replace |
| Ledgix Lot Allocation | ERPNext Serial & Batch Bundle / stock ledger | Replace |
| Ledgix POS Shift | POS Opening/Closing workflow | Replace if parity passes |
| Ledgix POS Hold | Native unfinished/draft POS flow | Review before retirement |
| Ledgix POS page | ERPNext-native first; Ledgix UI may remain | Keep UI only if it adds real value |
| Ledgix Tax Category / Tax Rate | ERPNext tax/accounting configuration | Replace only after tax parity |
| Ledgix Tax Profile | Split into ERPNext financial settings + Ledgix compliance settings | Refactor / retire gradually |
| Ledgix Item Tax Profile | Ledgix FBR classification linked to ERPNext Item | KEEP and relink; rename later if useful |
| Ledgix Invoice/Return tax snapshots | ERPNext financial tax + immutable Ledgix FBR classification snapshots | Transitional / redesign |
| FBR Settings | Ledgix | KEEP |
| FBR Submission Log | Ledgix | KEEP |
| FBR Correction Request | Ledgix | KEEP |
| Tax Audit Log | Ledgix | KEEP |
| Tax & FBR Center | Ledgix | KEEP |
| Brand Settings | Ledgix | KEEP |
| BI Center | Ledgix UI/intelligence, ERPNext datasource | KEEP / REWORK |
| Ledgix User Profile | Frappe User + roles/role profiles/permissions | Replace |
| Ledgix roles | Ledgix roles mapped to ERPNext permissions | KEEP |
| FBR print formats / QR | Ledgix | KEEP / adapt |

---

## 5. Target Data Model

### 5.1 Item

`Item` becomes the only product master.

Ledgix-specific FBR classification remains outside the generic Item master through the existing Item Tax Profile initially, relinked from `Ledgix Item` to `Item`.

The migration must map at least:

- item code / name;
- category -> Item Group;
- barcode;
- stock UOM;
- active/disabled state;
- tracking type -> normal / serial / batch configuration;
- opening stock through ERPNext stock opening mechanisms, not a mutable Item field;
- selling prices -> Item Price;
- valuation/cost -> ERPNext stock valuation, never a Ledgix-maintained average-cost field.

### 5.2 Stock modes by customer requirement

Ledgix must support the same product with configuration rather than separate codebases.

**Invoice/FBR-only customer**

- non-stock Item or stock workflow intentionally disabled for relevant items;
- Sales Invoice + accounting + FBR;
- no fake negative inventory requirement.

**Normal retail inventory**

- stock Item;
- warehouse;
- purchase/receipt or opening stock;
- stock ledger/valuation;
- sale/return stock effect.

**Negative-stock business**

- use ERPNext controls only where supported;
- serial/batch tracked items must follow ERPNext v15 restrictions and cannot depend on negative stock.

### 5.3 Customer

ERPNext `Customer` becomes authority for commercial identity and receivables context.

Ledgix/FBR-specific fields are added as Custom Fields or a linked compliance profile, including the current concepts:

- Buyer Registration Type;
- NTN/CNIC;
- STRN;
- Province;
- FBR Address;
- verification status/date where still useful.

Normal contacts/addresses should use ERPNext Contact/Address infrastructure instead of duplicate fields where practical.

Credit limits, payment terms, price-list defaults and outstanding balances should use ERPNext rather than Ledgix-calculated cache fields.

### 5.4 Supplier

Use ERPNext `Supplier`, Supplier Group, Address/Contact, tax ID and native AP/purchasing integration.

### 5.5 Sales

The legal/business transaction source becomes:

- `POS Invoice` or the appropriate native POS document for retail checkout after the POS spike;
- `Sales Invoice` for normal/B2B invoicing;
- native Credit Note / Return for corrections and returns.

Ledgix must not create a parallel submitted `Ledgix Sale` after cutover.

### 5.6 Payments and receivables

Use ERPNext Payment Entry/payment references/reconciliation and native invoice outstanding.

Ledgix stops manually maintaining:

- paid amount calculations as an independent ledger;
- remaining invoice balance as authority;
- payment allocations;
- unallocated credit;
- overdue totals;
- available credit.

Ledgix may show these values in a custom UI, but the values must come from ERPNext.

### 5.7 Purchase and inventory

Use native documents according to the client workflow:

```text
Full process:
Purchase Order -> Purchase Receipt -> Purchase Invoice -> Payment Entry

Small-shop process:
Purchase Invoice (+ stock effect where appropriate) -> Payment Entry

Internal stock movement:
Stock Entry / Stock Reconciliation
```

ERPNext becomes authority for quantity, valuation, COGS, serial and batch history.

---

## 6. Tax and FBR Architecture — Critical Split

This migration must not confuse **financial tax accounting** with **FBR legal classification**.

### 6.1 ERPNext owns financial amounts and ledgers

ERPNext must own the invoice's official monetary totals and GL impact, including configured sales tax and any additional tax components that legally affect the invoice payable.

The current Ledgix engine adds components such as Extra Tax, Further Tax and FED to the payable amount while Sales Tax Withheld at Source is represented separately. We must map these cases explicitly into ERPNext taxes/accounts before retiring the Ledgix tax engine.

### 6.2 Ledgix owns FBR classification and payload metadata

Ledgix keeps fields ERPNext generic tax records do not fully express for our FBR integration, including:

- HS Code;
- FBR UOM;
- Sales Type;
- FBR rate description;
- Sandbox Scenario ID;
- SRO Schedule Number;
- SRO Item Serial Number;
- Third Schedule / Notified Retail Price information;
- FBR-specific component metadata where required for payload construction.

### 6.3 No competing grand-total engine

After tax cutover, Ledgix must **not** recalculate a second authoritative `grand_total` next to ERPNext.

The intended direction is:

```text
Ledgix FBR classification
          |
          v
ERPNext invoice tax configuration / tax rows
          |
          v
ERPNext official totals + GL
          |
          v
Immutable FBR snapshot / payload
```

### 6.4 Mandatory tax parity matrix

Before the old Ledgix financial tax engine is retired, test at minimum:

1. ordinary taxable item;
2. tax-inclusive price;
3. zero-rated item;
4. exempt item;
5. Third Schedule / Notified Retail Price case;
6. Further Tax;
7. Extra Tax;
8. FED;
9. Sales Tax Withheld at Source;
10. mixed-tax invoice;
11. full return;
12. partial return;
13. price-only credit note.

For every case compare:

- ERPNext net/tax/grand totals;
- GL postings;
- stock effect where relevant;
- Ledgix expected FBR payload;
- FBR preview/readiness behavior.

No tax DocType is removed until this matrix passes.

---

## 7. FBR Migration Strategy

FBR is a core Ledgix differentiator and must be preserved.

Current FBR code has valuable safeguards around settings, environment modes, readiness, logs, failure state and reconciliation. The datasource changes; the compliance layer remains.

### Target source

```text
ERPNext Sales Invoice / POS transaction
        |
        +-- ERPNext Customer + Ledgix FBR buyer fields
        +-- ERPNext Item + Ledgix FBR Item Profile
        +-- immutable invoice/item FBR snapshots
        |
        v
Ledgix FBR payload + preflight + submission
        |
        v
Ledgix FBR Submission Log / correction / reconciliation
```

### Required transaction fields

Add Ledgix-owned custom fields to the chosen ERPNext sales/return document as needed, for example:

- FBR Status;
- FBR Invoice Number;
- FBR QR/reference data;
- Submitted At;
- Error Code / Error Message;
- reconciliation-required state;
- source/submit trigger metadata;
- idempotency/client sale identifier where needed.

Per-line legal metadata that must remain historically stable should be snapshotted onto the submitted transaction or an immutable Ledgix compliance snapshot, rather than re-read from today's Item profile during a later reprint/retry.

### Transition rule

FBR adapters may temporarily support both old `Ledgix Sale` and ERPNext invoice sources for migration/testing, but **never submit both copies of the same business sale to FBR**.

Before the switch, use dual **preview/comparison**, not dual submission.

---

## 8. POS Strategy

Do not delete the existing POS first.

The current Ledgix POS already has substantial UI and workflow work. Its backend, however, is tightly coupled to custom Ledgix Item, Customer, pricing, stock, tax, shift, payment and Sale records.

### POS decision gate

After ERPNext is installed on a fresh integration site, run the native POS end-to-end and compare:

- barcode/search speed;
- item/category browsing;
- walk-in and named customer;
- Retail vs B2B needs;
- price list and manager override;
- discounts;
- split payment;
- partial payment where relevant;
- cash change;
- saved/unfinished invoice;
- opening/closing shift;
- return/refund;
- stock visibility;
- print flow;
- FBR post-submit integration;
- keyboard/scanner usability;
- mobile/tablet behavior where required.

### Possible outcomes

**A. Native ERPNext POS is sufficient**  
Retire Ledgix POS after parity and branding/workspace integration.

**B. Native engine is sufficient but UX is not**  
Keep the Ledgix POS page as a product UI, but make it create/use ERPNext transactions underneath.

**C. Native workflow has a real gap**  
Extend only the missing behavior. Do not restore a complete parallel sales/stock/payment engine.

Until the spike is complete, the default recommendation is **B as the safe migration path** because it preserves the current Ledgix frontend investment while removing backend duplication.

---

## 9. Business Intelligence and Reports

Keep the Ledgix BI concept; replace its datasource.

The current BI API is heavily based on Ledgix Item, Stock Lot, Lot Allocation, Serial, Purchase, Sale and Return records. The target source set becomes primarily:

- Item;
- Warehouse / Bin where appropriate;
- Stock Ledger Entry;
- Serial No;
- Batch / Serial and Batch Bundle;
- Sales Invoice / POS transaction;
- Credit Notes / Returns;
- Purchase Receipt / Purchase Invoice;
- ERPNext accounting data where profit/COGS requires it.

### Report rule

If ERPNext already has a report that satisfies the use case, link the native report from the Ledgix workspace.

Keep a custom report only when Ledgix provides additional cross-document intelligence or a materially simpler product experience.

---

## 10. Users and Permissions

Retire `Ledgix User Profile` as an authorization source.

Keep product roles such as:

- Ledgix Cashier;
- Ledgix Manager;
- Ledgix Admin;
- standard ERPNext accounting roles where required.

Map those roles to actual DocType/Page/Report/API permissions.

The current role homepage idea remains valid:

```text
Cashier -> POS
Manager -> Ledgix Workspace
Admin   -> Ledgix Workspace
```

But homepage routing is UX only. Server-side and DocType permissions remain authoritative.

---

## 11. Target Ledgix Workspace

Ledgix remains the front door. The workspace will curate ERPNext and Ledgix features so users do not have to understand the underlying app split.

| Section | Shortcuts |
| --- | --- |
| Sell | Ledgix/native POS, Sales Invoice, Returns / Credit Notes |
| Customers & Money | Customer, Payment Entry, Accounts Receivable |
| Products & Pricing | Item, Item Group, Price List, Item Price, Pricing Rule |
| Purchase | Supplier, Purchase Invoice, Purchase Receipt, Purchase Order |
| Inventory | Warehouse, Stock Entry, Stock Reconciliation, Stock Balance, Stock Ledger, Serial No, Batch |
| Accounting | selected accounting reports/setup based on role |
| FBR & Tax | Tax & FBR Center, FBR Item Profiles, Submission Logs, Corrections, FBR Settings |
| Insights | Ledgix BI + selected native ERPNext reports |
| Administration | Company/business setup, users/roles, branding |

Workspace visibility should later be profile/role-aware so an invoice+FBR-only client never needs to see purchasing or inventory screens.

---

## 12. Client Profiles — Same Codebase

Ledgix should support client differences through configuration, not forks.

| Profile | Typical enabled experience |
| --- | --- |
| Invoice + FBR only | Customers, Items, Sales Invoice, Payments, FBR, Reports |
| Small retail | Stock Items, POS, simple purchase, payments, FBR |
| Full retail | Warehouses, purchase flow, stock control, POS, returns, accounting |
| B2B | Customers, payment terms, credit, Sales Invoice, Payment Entry, statements |
| Mixed | Retail POS + B2B invoicing + inventory |

A future Ledgix Setup/Business Profile wizard may configure and hide features, but it must not become another business engine.

---

# 13. Implementation Phases

Each phase has an explicit exit gate. We do not jump to deletion because the next screen looks better.

## Phase 0 — Baseline, Safety and Plan Lock

**Goal:** preserve the current working system and establish a migration reference.

Tasks:

- [x] audit the current repository architecture;
- [x] identify duplicate business-engine areas;
- [x] lock ERPNext-core direction in this document;
- [ ] capture current test/validation baseline;
- [ ] create a named pre-ERPNext git tag before functional changes;
- [ ] back up any site/database that contains meaningful Ledgix data before migration work;
- [ ] inventory production/staging sites and installed apps before deployment changes.

**Exit gate:** known-good baseline and rollback point exist.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site

**Goal:** make ERPNext a first-class supported dependency without breaking the current site blindly.

Tasks:

- add `required_apps = ["erpnext"]` to Ledgix hooks at the correct cutover point;
- declare/document compatible ERPNext v15 dependency/version policy;
- update local installer to fetch/prepare ERPNext version-15 alongside Frappe;
- update `site_setup.sh` so ERPNext is installed before Ledgix when Ledgix is selected;
- update production deployment/install flow similarly;
- add preflight checks for Frappe/ERPNext/Ledgix version alignment;
- create a **fresh ERPNext + Ledgix integration site** instead of converting the existing working site first;
- run migrations/build/assets and basic smoke test.

**Important:** do not add the required-app hook alone if the bench/site setup is not ready to provide ERPNext; dependency plumbing and installation order move together.

**Exit gate:** a clean new site can be created from repository scripts with ERPNext + Ledgix installed reproducibly.

---

## Phase 2 — Native ERPNext Capability Spike / Gap Matrix

**Goal:** decide what is truly replaceable before coding adapters.

Manually test on the fresh integration site:

- Company and PKR setup;
- chart of accounts basics;
- Warehouse;
- Mode of Payment;
- UOM / Item Group;
- stock and non-stock Item;
- Customer and Supplier;
- Price List / Item Price / Pricing Rule;
- Purchase Invoice / Receipt;
- Sales Invoice with and without stock effect;
- Payment Entry, partial and unallocated payment;
- AR/AP and customer outstanding;
- full and partial Sales Return / Credit Note;
- Stock Entry / Reconciliation;
- serial/batch flow;
- native POS;
- POS opening/closing;
- saved/unfinished POS behavior;
- split tender/payment behavior;
- print workflow.

Record each capability as:

- **USE NATIVE**;
- **EXTEND NATIVE**;
- **KEEP LEDGIX UI OVER NATIVE ENGINE**;
- **CUSTOM REQUIRED** with a written reason.

**Exit gate:** POS, tax and workflow unknowns have evidence-based decisions.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema

**Goal:** establish the target schema before transaction cutover.

Tasks:

- define ERPNext Customer FBR custom fields;
- relink/refactor Item Tax Profile to ERPNext Item;
- define necessary Sales Invoice/POS/return FBR fields;
- define immutable FBR line snapshot fields or snapshot structure;
- map Ledgix roles to ERPNext/Frappe permissions;
- define business-profile/site configuration without duplicating standard masters;
- add migration-safe fixtures/patches;
- build automated schema tests.

**Exit gate:** target standard DocTypes can hold every Ledgix-only datum needed for POS/FBR/prints without reintroducing duplicate masters.

---

## Phase 4 — Tax Parity and Accounting Foundation

**Goal:** make ERPNext the monetary/tax authority safely.

Tasks:

- configure/migrate tax templates, accounts and item-specific tax behavior;
- map current Ledgix tax categories/rates to ERPNext equivalents where possible;
- keep FBR classification metadata in Ledgix;
- implement the full tax parity matrix from Section 6;
- prove GL and payable totals;
- prove historical snapshot behavior;
- adapt FBR preview to read the ERPNext-based tax result in test mode.

**Exit gate:** all required tax scenarios produce correct accounting totals and equivalent FBR data.

---

## Phase 5 — Master Data Migration

**Goal:** move master authority once, not synchronize forever.

Recommended migration order:

1. Company prerequisites / UOM / Item Groups / Warehouses;
2. Price Lists;
3. Items;
4. Item Prices / pricing rules where applicable;
5. Customers + contacts/addresses + FBR fields;
6. Suppliers;
7. Modes of Payment;
8. FBR Item Profiles;
9. opening stock / serial / batch state when required.

Migration scripts/patches must be idempotent and produce a reconciliation report.

Old Ledgix masters become read-only/hidden only after target records and references are verified.

**Exit gate:** master counts, identifiers, prices and FBR mappings reconcile.

---

## Phase 6 — Selling, Payments and Returns Cutover

**Goal:** move the highest-value transactional path to ERPNext authority.

Tasks:

- create a Ledgix service/adapter boundary for native sales documents;
- preserve checkout idempotency/client-sale protection;
- switch B2B invoice creation to Sales Invoice;
- switch payment allocation to Payment Entry/native payment references;
- switch receivable/credit views to ERPNext;
- implement Return/Credit Note flow;
- verify fully paid, partially paid, unpaid, credit, refund and exchange cases;
- remove custom Sale/Payment writes from the new path only after parity.

**Exit gate:** new business sales no longer require submitted Ledgix Sale/Payment records as financial authority.

---

## Phase 7 — Buying and Inventory Cutover

**Goal:** move stock and valuation authority to ERPNext.

Tasks:

- switch purchases to native purchase documents;
- switch internal movements to Stock Entry/Reconciliation;
- switch stock availability reads to ERPNext;
- switch valuation and COGS to ERPNext;
- migrate/validate Batch and Serial No;
- remove new writes to Ledgix Stock Movement/Lot/Serial infrastructure;
- verify cancel/return/backdated flows supported by ERPNext policy.

**Exit gate:** every new stock quantity and valuation change is represented in ERPNext stock ledgers only.

---

## Phase 8 — POS Engine Decision and Migration

**Goal:** preserve UX value while eliminating the parallel backend.

Tasks depend on Phase 2 outcome.

If keeping Ledgix POS UI:

- replace boot data with ERPNext Customer/Item/Price/stock/payment data;
- replace checkout write with native sales/POS documents;
- replace custom shift with native opening/closing if parity passed;
- replace hold with native draft/unfinished behavior if parity passed;
- keep manager discount/price override controls through native permissions/rules;
- preserve scanner speed, split payment, cash change and print experience.

If native ERPNext POS is sufficient:

- apply Ledgix branding/entry points only where maintainable;
- retire the custom POS after parity.

**Exit gate:** POS has no dependency on custom Ledgix Sale, stock ledger, pricing ledger or payment ledger.

---

## Phase 9 — FBR Submission Cutover

**Goal:** move FBR source of truth from Ledgix Sale to ERPNext transaction without weakening safeguards.

Tasks:

- introduce source adapter abstraction if needed during transition;
- build Sales Invoice/POS source adapter;
- build Credit Note/return adapter;
- switch buyer lookup to ERPNext Customer + FBR extensions;
- switch item lookup to ERPNext Item + FBR profile;
- preserve seller/buyer/item immutable snapshots;
- adapt submission logs/corrections to generic reference doctype/name where beneficial;
- preserve Sandbox/Production/Manual controls;
- preserve fail-closed ambiguous-network/reconciliation-required behavior;
- perform payload diff tests old vs new;
- run FBR Sandbox scenarios before production cutover.

**Exit gate:** FBR submission, reprint, retry, correction and return flows use ERPNext transactions as their business source.

---

## Phase 10 — BI, Reports and Print Migration

**Goal:** keep the useful product layer but feed it from ERPNext.

Tasks:

- replace BI custom stock/lot/serial queries with ERPNext sources;
- replace custom reports with native ERPNext reports where equivalent;
- keep only Ledgix-specific analytics/reports;
- adapt thermal/B2B/FBR print formats to Sales/POS Invoice and Credit Note;
- verify historical FBR QR/reference printing.

**Exit gate:** BI/reports/prints no longer require active duplicate transaction ledgers.

---

## Phase 11 — Workspace and Product Simplification

**Goal:** make the combined system feel like Ledgix, not two apps.

Tasks:

- rebuild Ledgix Workspace using standard ERPNext shortcuts plus Ledgix-only pages;
- hide unnecessary modules for simplified client profiles;
- keep native Forms/Lists rather than building duplicate CRUD pages;
- ensure Cashier/Manager/Admin landing routes and permissions are clean;
- remove obsolete workspace shortcuts to Ledgix duplicate DocTypes.

**Exit gate:** normal users can work from the Ledgix workspace without needing to navigate ERPNext's full module tree.

---

## Phase 12 — Legacy Freeze, Reconciliation and Retirement

**Goal:** remove duplicate code only when it is genuinely dead.

Sequence for every old module:

```text
Inventory current capability
        |
        v
Map replacement
        |
        v
Implement + migrate
        |
        v
Parity / reconciliation tests
        |
        v
Switch new reads/writes
        |
        v
Hide + read-only old records
        |
        v
Observation period
        |
        v
Delete obsolete code/schema in a later migration
```

Reconcile at minimum:

- master counts;
- sales totals;
- returns/credits;
- payment totals and allocation;
- customer outstanding;
- stock quantities;
- stock valuation;
- purchase totals;
- tax totals;
- FBR submission references/statuses.

**Exit gate:** obsolete Ledgix business-engine DocTypes/services have zero active write/read dependencies and can be removed safely.

---

## Phase 13 — Client Profiles and SaaS Productization

**Goal:** use one codebase for different client complexity levels.

Tasks:

- profile-aware workspace visibility;
- simple Ledgix setup wizard only for configuration;
- defaults for invoice-only, retail, B2B and mixed clients;
- deployment checks that enforce ERPNext dependency;
- documentation for site creation, backup, upgrade and client onboarding.

**Exit gate:** a new client can be provisioned without code changes or custom forks.

---

## 14. Migration Safety Rules

These rules are non-negotiable during implementation.

1. **No delete-first migrations.** Hide/read-only before schema removal.
2. **No permanent dual ledgers.** Compatibility adapters are temporary.
3. **No ERPNext core edits.** Use extension points.
4. **No silent tax drift.** Financial and FBR tax parity must be proven.
5. **No FBR dual submission.** Comparison can be dual-read; submission is one authoritative transaction only.
6. **No master-data two-way sync.** Migrate authority once.
7. **No UI-first rewrite against an unstable backend.** Lock target documents/services first.
8. **No reliance on mutable current master data for historical FBR documents.** Snapshot legal fields at posting/submission boundaries.
9. **Every destructive retirement needs a reconciliation report and rollback path.**
10. **Existing Ledgix functionality remains working until its replacement passes the exit gate.**

---

## 15. Test Strategy

Every phase should add or migrate tests rather than waiting for the end.

### Required layers

- schema/migration tests;
- permission tests;
- native document integration tests;
- POS checkout tests;
- idempotency tests;
- payment/partial/unallocated/refund tests;
- stock/valuation/serial/batch tests;
- tax parity tests;
- FBR payload golden tests;
- FBR failure/reconciliation tests;
- return/Credit Note tests;
- BI/report reconciliation tests;
- installer/site-creation smoke tests.

### Cutover test principle

For modules being replaced, build temporary comparison tests where useful:

```text
same business scenario
       |
       +--> old Ledgix result
       |
       +--> ERPNext target result
                 |
                 v
       explicit parity report
```

Once cutover is complete, delete the old result path from production code, not necessarily the historical test evidence.

---

## 16. Definition of Done

The ERPNext migration is complete only when all of the following are true:

- ERPNext is a declared and reproducibly installed Ledgix dependency;
- Item, Customer, Supplier, pricing, sales, purchase, stock, payments and accounting have one ERPNext authority;
- Ledgix POS, if retained, is UI/workflow only over ERPNext documents;
- ERPNext financial tax totals/GL are authoritative;
- Ledgix FBR metadata, submission, correction, logs and safeguards are preserved;
- FBR uses ERPNext sales/return transactions as source;
- BI and custom reports read ERPNext data;
- Ledgix Workspace is the curated product entry point;
- legacy duplicate Ledgix business DocTypes are no longer used for new transactions;
- reconciliation has passed;
- obsolete services/DocTypes are retired through controlled migrations;
- client differences are configuration, not separate codebases.

---

# 17. Immediate Next Work

The next implementation unit is intentionally small and safe:

### Phase 0 closeout

1. capture the current validation/test baseline;
2. create the pre-ERPNext rollback tag;
3. confirm the local integration-site name and existing-site backup status when running locally.

### Then Phase 1

1. add ERPNext fetch/version plumbing to the installer;
2. make site setup install ERPNext before Ledgix;
3. add `required_apps = ["erpnext"]` only together with that plumbing;
4. create a fresh ERPNext + Ledgix site;
5. smoke-test install/migrate/build;
6. do not touch the existing Ledgix business DocTypes yet.

This gives us a safe platform for the native ERPNext capability spike before any major backend replacement begins.
