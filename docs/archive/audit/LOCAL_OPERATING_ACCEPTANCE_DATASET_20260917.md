# Local Operating / Acceptance Data

**Status:** COMPLETE / VERIFIED  
**Site:** `ledgix-erpnext.local`  
**Dataset:** `LEDGIX-RETAIL-OPERATING-V1`  
**Purpose:** realistic local ERPNext-core operating data for acceptance/UAT  
**Production use:** **NOT ALLOWED**

## Purpose

The local dataset is no longer a disposable minimal demo fixture. It is a realistic synthetic retail operating history used to exercise the post-migration Ledgix + ERPNext architecture.

The current verified dataset should be treated as **acceptance/operating evidence**, not casually cleaned or rebuilt between tests.

All business transactions are ERPNext-native. The loader must never repopulate the retired Ledgix business ledgers.

---

## 1. Current verified dataset

Final verified state:

| Measure | Verified value |
|---|---:|
| Company | `Ledgix ERPNext Integration` |
| Items | 52 |
| Customers | 16 |
| Suppliers | 8 |
| POS Profile | `Main Counter POS` |
| POS sales | 108 |
| B2B sales | 12 |
| Total sales | 120 |
| POS returns | 4 |
| B2B returns | 3 |
| Payment Entries | 9 |
| Purchase Invoices | 6 |
| Stock Entries | 88 |
| Split-payment POS invoices | 30 |
| Trade outstanding | 39,991.50 |
| Trade overdue | 28,197.50 |
| Active acceptance POS opening | `POS-OPE-2026-00030` |
| Negative retail bins | none |
| Unconsolidated managed POS | none |
| Visible old demo/spike artifacts | none |
| FBR transport disabled | true |
| Verifier result | `ok = true` |

Low/out-of-stock acceptance examples include:

```text
CM-BRD-003 = 0
CM-BEV-001 = 2
CM-BEV-004 = 5
```

Return/consolidation state:

```text
return POS Opening Entry: POS-OPE-2026-00029 -> Closed
POS Closing Entry:          POS-CLO-2026-00021
active UAT opening:         POS-OPE-2026-00030 -> Open
```

This is the canonical local acceptance state unless an explicit maintenance/reset decision replaces it.

---

## 2. Implementation

Primary operating-data modules:

```text
apps/ledgix_saas/setup/demo_data.py
apps/ledgix_saas/setup/retail_operating_profile.py
apps/ledgix_saas/setup/retail_v15_compat.py
apps/ledgix_saas/setup/retail_seed_safe.py
apps/ledgix_saas/setup/retail_cleanup_safe.py
apps/ledgix_saas/setup/erpnext_demo_data.py
scripts/prepare_local_demo.sh
```

`retail_operating_profile.py` defines the realistic fictional retail masters and dataset marker.

`retail_v15_compat.py` is the guarded ERPNext-v15 runtime adapter used by the preparation script. It verifies the pinned POS payment-child schema and historical B2B date assumptions.

`demo_data.py` contains the core dataset inspection/seed/verification contract.

---

## 3. ERPNext authority

The dataset intentionally exercises current business authority rather than legacy Ledgix transaction DocTypes.

It uses ERPNext-native:

- `Item`, `Item Group`, `Item Price`, Price Lists;
- `Customer`, `Supplier`;
- `Warehouse`;
- `Purchase Order`, `Purchase Receipt`, `Purchase Invoice`;
- `Stock Entry`, `Stock Reconciliation`, Stock Ledger / `Bin`;
- `POS Profile`, `POS Opening Entry`, `POS Invoice`, `POS Closing Entry`;
- `Sales Invoice`;
- `Payment Entry`;
- native Sales/POS returns;
- Batch / Serial No where applicable.

The loader must not create new current-operation records in:

```text
Ledgix Sale
Ledgix Purchase
Ledgix Payment
Ledgix Stock Movement
Ledgix POS Shift
Ledgix POS Hold
```

or the other frozen duplicate business ledgers.

---

## 4. Safety rules

The operating-data tooling is local-only and deliberately guarded.

It:

- refuses non-`.local` sites;
- takes a Frappe backup with files before the preparation flow changes data;
- uses Frappe/ERPNext document APIs rather than direct Stock Ledger manipulation;
- preserves submitted accounting/POS history;
- retires only known old local demo/spike artifacts through the safe cleanup helper;
- reuses deterministic current masters/history where designed rather than duplicating them;
- keeps Phase-12 frozen historical Ledgix evidence intact;
- forces FBR transport to `Disabled` for local operating-data generation;
- never creates fake FBR tokens, official invoice numbers, responses or certification evidence.

### Critical rule

**Do not use this dataset as a production data loader.**

---

## 5. Do not casually reset the current dataset

The previous documentation described the local data as a disposable V2 demo set that could be deleted and recreated on normal reruns. That is no longer the current operating model.

Current `scripts/prepare_local_demo.sh` explicitly preserves the managed submitted retail history because ERPNext POS closings/consolidation produce linked accounting/audit records that should not be destroyed merely to obtain a visually clean local site.

Normal reruns are intended to be marker-idempotent and preserve submitted history.

A destructive reset, if ever genuinely required, is a separate maintenance operation and must have:

1. an explicit reason;
2. a fresh backup;
3. inspection of linked ERPNext accounting/POS history;
4. deliberate scope;
5. post-reset verification.

Do **not** cancel/delete the completed dataset casually.

---

## 6. Canonical preparation command

From repository root:

```bash
./scripts/prepare_local_demo.sh ledgix-erpnext.local
```

The current script performs:

1. exact-sync current Ledgix app source into the local bench;
2. verify installed apps;
3. create a backup **with files**;
4. inspect the site before mutation;
5. safely retire known old Ledgix demo/spike artifacts;
6. create/reuse the ERPNext-authoritative realistic operating history through the v15-safe adapter;
7. repeat old-artifact cleanup after master normalization;
8. run the deterministic v15-aware verifier.

It does **not** intentionally delete the current submitted `LEDGIX-RETAIL-OPERATING-V1` history before reseeding.

Because the canonical dataset is already complete and verified, do not run the preparation command merely as a routine startup step. Run it only when the operating dataset genuinely needs repair/recreation and you intend to preserve its existing managed history semantics.

---

## 7. Read-only inspection and verification

Inspect current site state without rebuilding the dataset:

```bash
cd frappe-bench
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.inspect_site
```

Core verifier:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.verify
```

Pinned ERPNext-v15 guarded verifier used by the preparation workflow:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.retail_v15_compat.verify
```

For normal acceptance work, **verify first**. Do not reseed simply because a verifier command exists.

---

## 8. What the verifier proves

The current verifier checks the operating-data shape and critical architecture invariants, including:

- realistic ERPNext Item/Customer/Supplier counts;
- at least 100 submitted managed sales;
- retail and B2B return coverage;
- Purchase Invoice and Payment Entry coverage;
- split-payment POS coverage;
- positive trade receivables/outstanding;
- deliberate low/out-of-stock examples;
- no negative stock in the managed retail warehouse scope;
- no submitted managed POS invoice left unconsolidated;
- an active POS Opening Entry for manual acceptance testing;
- FBR remains disabled;
- old local demo/spike artifacts are not visible;
- ERPNext-v15 POS payment rows resolve through `Sales Invoice Payment`;
- managed historical B2B due dates/payment schedules are not earlier than posting dates.

A successful result must return:

```text
ok = true
```

The verifier defect that previously queried the non-existent `tabPOS Invoice Payment` table was corrected to ERPNext v15's actual `tabSales Invoice Payment` child table.

---

## 9. Dataset coverage

### Masters

The realistic profile includes:

- 52 retail/service ERPNext Items across normal, batch, serial and non-stock examples;
- realistic product groups;
- Retail, Trade and Buying price lists;
- deterministic item prices and reorder levels;
- 3 working warehouse concepts: Main Store, Retail Floor and Back Store;
- Walk-in and named retail customers;
- six Trade Customers with credit limits;
- eight Suppliers;
- common payment modes including Cash/Card/Bank/Wallet flows where configured;
- `Main Counter POS`;
- Ledgix tax/FBR mappings attached to ERPNext Items.

All names/business history are fictional local test data.

### Purchasing

The operating history exercises native ERPNext purchasing, including:

```text
Purchase Order -> Purchase Receipt -> Purchase Invoice
```

plus stock/accounting effects required to create meaningful inventory history.

### Inventory

The dataset exercises:

- purchase receipts;
- warehouse transfers;
- material receipts/movements;
- reorder state;
- batch examples;
- serial examples;
- healthy stock;
- deliberate low stock;
- deliberate out-of-stock cases;
- no negative retail bins in the verified final state.

### Retail POS

The historical dataset includes **108 submitted POS sales**.

Coverage includes:

- Walk-in and named customers;
- multi-item sales;
- Cash;
- Card;
- Bank Transfer;
- EasyPaisa/JazzCash-style wallet modes where configured;
- split tender;
- discounts;
- non-stock service rows;
- POS opening/closing;
- native ERPNext consolidation;
- partial POS returns.

### Split payment

The final verified dataset contains **30 POS invoices with more than one native payment row**.

ERPNext v15 stores these rows in the `Sales Invoice Payment` child DocType used by `POS Invoice.payments`.

### B2B

The dataset includes **12 Sales Invoices** for the six Trade Customers.

Its payment pattern intentionally produces a mix of:

- fully paid invoices;
- partially paid invoices;
- unpaid invoices;
- outstanding and overdue receivables.

The final verified aggregate trade state is:

```text
outstanding = 39,991.50
overdue     = 28,197.50
```

### Returns

The completed dataset contains:

- **4 POS partial returns**;
- **3 B2B partial Credit Notes**.

All returns reference real original ERPNext invoices rather than independent custom Ledgix return ledgers.

---

## 10. POS acceptance state

The historical return shift has been deliberately closed and consolidated:

```text
POS Opening Entry: POS-OPE-2026-00029
status: Closed
POS Closing Entry: POS-CLO-2026-00021
```

The site then leaves a dedicated current opening available for acceptance testing:

```text
POS Opening Entry: POS-OPE-2026-00030
status: Open
POS Profile: Main Counter POS
user: Administrator
```

Do not close/reset this opening merely to make the site appear empty. Its purpose is to allow immediate POS UAT unless the current test specifically requires a closing scenario.

---

## 11. Manual acceptance checks

The deterministic verifier proves data/state invariants. It does **not** replace UI/device/manual UAT.

### Ledgix POS

Confirm:

- page loads using `Main Counter POS`;
- realistic catalog is visible;
- barcode search works;
- stock availability matches ERPNext;
- normal checkout creates an ERPNext `POS Invoice`;
- split payment works;
- POS return links to the original POS Invoice;
- active opening/shift state is correct;
- print target is the native ERPNext invoice/receipt format.

### B2B

Confirm:

- B2B checkout creates ERPNext `Sales Invoice`;
- customer pricing/credit behavior is appropriate;
- Payment Entry allocation changes native invoice outstanding;
- Accounts Receivable/Customer Statement agrees with the invoice/payment state;
- a return creates a native Credit Note linked to the original Sales Invoice.

### Buying / inventory

Confirm:

- Purchase documents open without legacy-ledger dependencies;
- stock quantity/valuation comes from ERPNext;
- transfers and low/out-stock examples appear correctly;
- Inventory Intelligence agrees with ERPNext Stock Balance/Stock Ledger for representative items.

### Tax & FBR

For this local dataset the expected transport state is:

```text
enabled = 0
mode = Disabled
production_post_armed = 0
```

No local operating-data result is valid FBR Sandbox/Production certification evidence.

---

## 12. Cleanup policy

### Safe old-artifact cleanup

The supported old-demo cleanup path is:

```text
ledgix_saas.setup.retail_cleanup_safe.cleanup_old_local_artifacts
```

It may remove unlinked obsolete local demo masters or disable/archive linked ones. Submitted accounting/POS history is retained.

### What normal cleanup must not do

Normal cleanup must not:

- wipe the database;
- truncate ERPNext tables;
- delete arbitrary invoices/customers/items/suppliers;
- cancel current submitted operating history merely because it is test data;
- delete Phase-12 frozen historical legacy evidence;
- erase unrelated FBR audit evidence;
- fabricate a clean state by bypassing ERPNext accounting/stock links.

If broader cleanup is required, classify records explicitly first.

---

## 13. Acceptance-data rule going forward

Treat `LEDGIX-RETAIL-OPERATING-V1` as the canonical local acceptance dataset until an explicit versioned replacement is approved.

Changes to its loader/verifier should preserve these principles:

- ERPNext remains transaction/master authority;
- realistic operating history is more valuable than an artificially empty site;
- reruns are safe and idempotent rather than destructive;
- acceptance edge cases remain deliberate and verifiable;
- FBR remains disabled unless a separate real Sandbox workflow is intentionally being exercised;
- a changed dataset contract should use an explicit new version/marker rather than silently redefining V1.
