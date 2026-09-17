# Local Demo Data Operations

## Scope

The supported Ledgix demo dataset is designed for **local `.local` sites only** and exercises ERPNext-authoritative workflows over roughly 12 weeks of activity.

It must not be used as a production data loader.

Supported entrypoint:

```text
ledgix_saas.setup.demo_data
```

Implementation:

```text
apps/ledgix_saas/setup/demo_data.py
apps/ledgix_saas/setup/erpnext_demo_data.py
```

---

## Safety properties

The demo utility:

- refuses to run when the active site name does not end in `.local`;
- switches to Administrator only for the controlled operation and restores the previous user afterward;
- uses normal Frappe/ERPNext document APIs and ERPNext mapper/helpers for business transactions;
- never seeds new `Ledgix Sale`, `Ledgix Purchase`, `Ledgix Payment`, `Ledgix Stock Movement` or other frozen legacy business ledgers;
- identifies generated native transactions with deterministic `LEDGIX-ERP-DEMO-V2` client IDs/notes;
- cleanup is limited to those marker-owned transactions;
- does not delete arbitrary existing Items/Customers/Suppliers or Phase-12 legacy evidence;
- forces FBR transport to `Disabled` and disarms Production posting before transactions are created;
- does not create fake FBR responses, official invoice numbers, tokens or certification logs.

---

## Recommended one-command preparation

From repository root:

```bash
chmod +x scripts/prepare_local_demo.sh
./scripts/prepare_local_demo.sh ledgix-erpnext.local
```

The script performs this sequence:

1. confirms installed apps;
2. creates a Frappe backup **with files**;
3. prints a non-destructive pre-seed site snapshot;
4. removes only previous V2 demo transactions;
5. seeds native ERPNext demo data;
6. runs deterministic verification.

It does not remove unrelated test records automatically because the utility cannot safely infer which unmarked records are disposable.

---

## Individual commands

Inspect without changing data:

```bash
cd frappe-bench
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.inspect_site
```

Remove only a previous V2 demo transaction set:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.cleanup_seed_transactions
```

Seed:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.seed
```

Verify:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.verify
```

---

## Dataset shape

The seed is deterministic and currently targets:

### Masters

- existing configured ERPNext Company;
- 6 demo Item Groups;
- 26 ERPNext Items;
- stock and non-stock/service Items;
- EAN-style demo barcodes;
- Retail, Wholesale and Buying Price Lists;
- selling/buying Item Prices;
- reorder levels;
- 3 warehouses: Main Store, POS Floor and Back Store;
- 12 Customers including Walk-in and B2B accounts;
- 6 Suppliers;
- Cash, Card, Bank Transfer, EasyPaisa and JazzCash modes where required accounts exist;
- a Ledgix demo POS Profile;
- Ledgix tax mappings attached to ERPNext Items;
- 2 batch-tracked and 2 serial-tracked example Items.

The seed deliberately requires a valid leaf Cash account, Bank account and configured Ledgix tax accounts. If core ERPNext accounting setup is incomplete, it should fail rather than silently create misleading accounting.

### Purchasing

Across the historical window the seed creates ERPNext-native:

- Purchase Orders;
- Purchase Receipts;
- Purchase Invoices;
- varying costs across purchase cycles.

Stock effects come from ERPNext documents, not direct Stock Ledger writes.

### Inventory

The seed exercises:

- receipt stock;
- Main Store -> POS Floor transfers;
- Main Store -> Back Store movements;
- batch Material Receipt using ERPNext serial/batch fields;
- serial-number Material Receipt;
- reorder configuration;
- deliberate healthy, low and out-of-stock POS-floor examples.

### Retail POS

The seed creates 12 historical weekly ERPNext POS openings, each with 9 retail transactions, for **108 retail POS invoices**.

Sales include:

- Walk-in and named retail customers;
- multiple items per invoice;
- Cash;
- Card;
- Bank Transfer;
- EasyPaisa;
- JazzCash;
- split Cash/Card and Cash/Wallet tenders;
- periodic percentage discounts;
- occasional non-stock services.

Each historical shift is closed through ERPNext POS Closing Entry. This also exercises native POS consolidation behavior.

### B2B

The seed creates **12 ERPNext Sales Invoices** with stock impact and wholesale pricing.

The payment pattern intentionally leaves a mixture of:

- fully paid invoices;
- partially paid invoices;
- unpaid invoices;

so Accounts Receivable / Customer Statement data is meaningful.

### Returns

The demo includes:

- 4 POS Invoice partial returns posted within a real active ERPNext POS opening;
- 3 Sales Invoice partial credit notes.

Returns reference real original invoices and affect the native ERPNext transaction chain.

### Current POS state

After historical activity and return testing, the seed leaves one current ERPNext POS Opening Entry open for Administrator so the retained Ledgix POS can be opened immediately for manual UAT.

---

## Verification contract

`verify()` checks at least:

- >= 20 demo Items;
- >= 8 Customers;
- >= 5 Suppliers;
- >= 100 submitted demo sales;
- POS and B2B returns;
- purchase invoices;
- native Payment Entries;
- split-payment POS invoices;
- positive B2B receivable outstanding;
- low/out-of-stock examples;
- no negative demo warehouse bins;
- an active POS opening;
- FBR transport remains disabled.

A failed verification raises rather than presenting the dataset as ready.

---

## Manual workflow verification after seed

The deterministic data check is not a replacement for UI/UAT. After a successful seed, manually verify:

### Ledgix POS

- page loads;
- seeded Item list is visible;
- exact barcode search works;
- normal retail checkout works;
- split payment works;
- retail return against an existing POS Invoice works;
- shift state is visible;
- print action opens a usable invoice.

### B2B

- B2B checkout/profile behavior is correct for the active Business Profile;
- ERPNext Sales Invoice is the resulting authority;
- Payment Entry allocation changes invoice outstanding;
- Accounts Receivable matches the invoice/payment state;
- credit note references the original Sales Invoice.

### Buying

- Purchase Orders/Receipts/Invoices open without legacy dependencies;
- stock quantities match receipt/transfer history;
- Supplier and AP reports remain native.

### Inventory Intelligence

Confirm the page shows a meaningful mixture of:

- healthy stock;
- low stock;
- out-of-stock;
- transfers;
- purchases;
- sales/returns;
- batch/serial activity.

Compare values against ERPNext Stock Balance and Stock Ledger reports.

### Tax & FBR

The Tax & FBR Center should load tax/item configuration and invoice readiness data, but local demo transactions must remain network-inactive.

Expected state:

```text
mode = Disabled
enabled = 0
production_post_armed = 0
no fake official FBR numbers
```

---

## Re-running

The demo is intended to be repeatable through:

```bash
./scripts/prepare_local_demo.sh ledgix-erpnext.local
```

That command backs up first, deletes only marker-owned V2 demo transactions and then recreates/verifies the dataset.

Master records use deterministic codes/names and are reused rather than duplicated.

---

## What cleanup does not do

`cleanup_seed_transactions()` intentionally does **not**:

- wipe the database;
- delete all invoices;
- delete all customers/items/suppliers;
- truncate tables;
- delete Phase-12 historical legacy rows;
- clear FBR audit evidence that does not belong to this local seed;
- attempt to guess which manually created records are "test garbage".

If broader local cleanup is desired, inspect the site first and classify those records explicitly before deletion.
