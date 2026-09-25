# Ledgix POS — Client Documentation

**Status:** CURRENT CLIENT GUIDE  
**Product baseline:** 2026-09-26

Welcome to the Ledgix POS client documentation.

This guide is for:

- business owners;
- client administrators;
- managers;
- cashiers;
- accountants/bookkeepers;
- staff responsible for stock, purchasing or FBR operations.

You do not need to understand the internal Ledgix codebase to use these documents.

---

## 1. What Ledgix is

Ledgix provides a focused POS/business interface on top of ERPNext.

In normal operation:

- Ledgix gives you the product experience;
- ERPNext stores the official business/accounting/stock records;
- FBR features are handled through the Ledgix Tax & FBR tools around your ERPNext invoices.

This means your real business records remain standard ERPNext records such as:

- Customer;
- Item;
- Sales Invoice;
- POS Invoice;
- Payment Entry;
- Purchase Invoice;
- Stock Entry;
- General Ledger.

---

## 2. Start here

If your site is newly installed, read in this order:

1. [GETTING_STARTED.md](GETTING_STARTED.md)
2. [USERS_ROLES_AND_NAVIGATION.md](USERS_ROLES_AND_NAVIGATION.md)
3. [MASTER_DATA_AND_PRICING.md](MASTER_DATA_AND_PRICING.md)
4. the workflow guide relevant to your business

---

## 3. Daily operations

The complete client pack will contain:

### [POS_DAILY_OPERATIONS.md](POS_DAILY_OPERATIONS.md)

For retail/counter staff:

- open shift;
- sell;
- barcode/search;
- split payment;
- hold/resume;
- return;
- close shift;
- print receipt.

### [SALES_RETURNS_AND_PAYMENTS.md](SALES_RETURNS_AND_PAYMENTS.md)

For invoice/B2B sales:

- Sales Invoice;
- customer payments;
- outstanding balance;
- returns/Credit Notes;
- refunds;
- exchanges.

### [PURCHASE_AND_INVENTORY.md](PURCHASE_AND_INVENTORY.md)

For purchasing/stock staff:

- suppliers;
- Purchase Orders;
- receipts;
- Purchase Invoices;
- supplier payments;
- stock transfers;
- stock corrections;
- batch/serial workflows.

### [REPORTS_AND_ACCOUNTING.md](REPORTS_AND_ACCOUNTING.md)

For owners/managers/accountants:

- sales reports;
- customer statements;
- stock reports;
- Accounts Receivable;
- General Ledger;
- Profit and Loss.

---

## 4. FBR

### [FBR_SETUP_AND_OPERATIONS.md](FBR_SETUP_AND_OPERATIONS.md)

For authorized administrators/managers:

- seller information;
- FBR Integration Profile;
- Item mappings;
- reference data;
- Sandbox certification;
- invoice status;
- Reconciliation Required;
- Known Offline;
- Production activation boundaries.

Important:

> Ledgix software being installed does not mean FBR Production is active.

Current product baseline:

- Software Ready for Client Certification: YES;
- Sandbox Certified: NO by default;
- Production Ready: NO by default;
- Production Active: NO by default.

Your own site must complete its genuine FBR onboarding/certification before Production use.

---

## 5. Go-live and support

### [BACKUP_DEPLOYMENT_AND_GO_LIVE.md](BACKUP_DEPLOYMENT_AND_GO_LIVE.md)

For owners/client administrators:

- client readiness;
- backup evidence;
- user/device UAT;
- release approval;
- FBR go-live boundary.

### [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

Use when:

- POS will not open;
- payment/stock looks wrong;
- user cannot see a screen;
- FBR status blocks an action;
- printing fails;
- system is in maintenance.

---

## 6. Business Profiles

Ledgix has five standard Business Profiles.

### Invoice + FBR Only

Best for:

- service businesses;
- tax invoice businesses;
- clients that do not manage retail POS/inventory through Ledgix.

Main experience:

- Sales Invoice;
- accounting;
- FBR.

### Small Retail

Best for:

- small shops;
- counter sales;
- normal purchasing/stock.

Main experience:

- POS;
- sales;
- normal inventory;
- buying;
- accounting;
- FBR.

Advanced batch/serial/stock-control screens are hidden by default.

### Full Retail

Best for:

- larger retail operations;
- businesses using full stock control.

Adds:

- advanced inventory;
- Stock Entry;
- Stock Reconciliation;
- Batch;
- Serial Number workflows.

### B2B

Best for:

- wholesale;
- account customers;
- invoice-led sales.

Main experience:

- Sales Invoice;
- B2B/customer receivables;
- accounting;
- FBR.

POS is not required.

### Mixed

Best for:

- businesses using both retail POS and B2B/account sales.

Includes:

- POS;
- B2B;
- purchasing;
- advanced inventory;
- accounting;
- FBR.

---

## 7. User roles

Ledgix normally uses:

- Ledgix Cashier;
- Ledgix Manager;
- Ledgix Admin;
- System Manager.

Basic intent:

| Role | Typical use |
|---|---|
| Ledgix Cashier | Counter sales/POS |
| Ledgix Manager | Operations, stock, reports, supervision |
| Ledgix Admin | Ledgix configuration and controlled administration |
| System Manager | Full ERPNext/Frappe system administration |

Exact access is also controlled by ERPNext permissions.

---

## 8. Important business rule

Do not create current business transactions in old historical Ledgix records.

For normal work use the current Ledgix screens and ERPNext records.

If you ever see old historical Ledgix documents marked read-only, that is intentional.

---

## 9. Where your data lives

Your client site has its own:

- database;
- users;
- Company;
- customers;
- suppliers;
- items;
- invoices;
- stock;
- FBR configuration/evidence;
- backups.

Ledgix can run multiple clients on shared infrastructure, but client business data remains separated by Frappe site.

---

## 10. Before changing important setup

For changes affecting:

- accounting;
- stock;
- FBR;
- production configuration;
- major system update,

coordinate with the responsible Ledgix/System Administrator.

Do not change accounting values merely to make a screen/test look correct.

---

## 11. Client documentation principle

These guides focus on:

- what to configure;
- what staff should do;
- what result to expect;
- when to stop and ask an administrator.

They intentionally avoid internal developer implementation details.

For software architecture, developers should use:

    docs/developer/

---

## 12. Quick start checklist

For a new client:

- [ ] Company configured
- [ ] Chart of Accounts configured
- [ ] Selling Price List configured
- [ ] Warehouse configured if required
- [ ] Modes of Payment/accounts configured
- [ ] Customers/Suppliers/Items configured
- [ ] POS Profile configured if POS is enabled
- [ ] Ledgix Business Profile selected
- [ ] Ledgix named users created
- [ ] roles assigned
- [ ] setup readiness green
- [ ] operational onboarding green
- [ ] FBR configured/certified if applicable
- [ ] printers/scanners/device UAT complete
- [ ] verified backup available
- [ ] go-live approved

---

## 13. One-sentence guide

> **Use Ledgix for the workflow, rely on ERPNext for the official business/accounting records, and complete FBR/production readiness explicitly before going live.**
