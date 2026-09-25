# Ledgix POS — Reports and Accounting

**Audience:** Owners, managers, accountants/bookkeepers

## 1. Purpose

This guide explains the main reports/accounting views available through Ledgix and ERPNext.

ERPNext is the official accounting system.

Ledgix reports present or adapt ERPNext data.

Do not maintain a competing financial ledger outside ERPNext as the official source.

---

## 2. Main report areas

Depending on your Business Profile and role, the Ledgix workspace can show:

- Sales Report;
- Sales Return Report;
- Purchase Report;
- Customer Statement;
- Stock Balance;
- Stock Ledger;
- Accounts Receivable;
- General Ledger;
- Profit and Loss Statement;
- Inventory Intelligence.

---

## 3. Sales Report

Use Sales Report to review sales activity.

Typical review points:

- date;
- customer;
- invoice;
- sale type;
- quantity;
- amount;
- return impact.

The report is based on current ERPNext Sales Invoice/POS Invoice authority.

---

## 4. Avoid POS double counting

ERPNext POS closing can create accounting consolidation documents.

Current Ledgix reporting is designed around the native POS model so the consolidated accounting invoice should not be treated as a second independent retail sale.

If totals look duplicated, escalate instead of manually changing transactions.

---

## 5. Sales Return Report

Use Sales Return Report to review:

- returned Items;
- return invoice;
- original source;
- amounts/quantities;
- date/customer.

Returns should be linked to original native sales.

---

## 6. Purchase Report

Use Purchase Report to review ERPNext Purchase Invoice activity.

Typical values:

- Supplier;
- Items;
- quantities;
- purchase amount/cost.

For stock movement timing, also review Purchase Receipts/Stock Ledger where relevant.

---

## 7. Customer Statement

Customer Statement is based on ERPNext financial entries.

Use it to review:

- opening balance;
- invoices/debits;
- payments/credits;
- Credit Notes;
- running balance.

If the statement does not match expectation, inspect the underlying invoices/Payment Entries rather than adjusting a separate Ledgix balance.

---

## 8. Accounts Receivable

Use ERPNext Accounts Receivable to review:

- outstanding invoices;
- overdue amounts;
- due dates;
- customer balances.

This is the official receivable view.

---

## 9. Customer credit

For B2B customers, Ledgix can present receivable/credit context from ERPNext.

It can include:

- outstanding;
- invoice credits;
- unallocated advances;
- net balance;
- overdue.

Use this information together with the client's credit policy.

---

## 10. General Ledger

General Ledger is the official accounting-entry detail.

Use it to investigate:

- account movement;
- customer/supplier ledger impact;
- tax postings;
- cash/bank movement;
- stock/accounting effects.

Do not edit GL Entry directly.

Correct the source transaction.

---

## 11. Profit and Loss Statement

Use ERPNext Profit and Loss for financial performance.

Correctness depends on:

- Chart of Accounts;
- income/expense accounts;
- stock valuation/COGS;
- transaction posting.

Have the client's accountant review accounting configuration before relying on final financial statements.

---

## 12. Stock Balance

Stock Balance shows quantity/value position by Item/Warehouse.

Use it for:

- current inventory;
- valuation;
- location review.

ERPNext stock ledger/Bin remain authority.

---

## 13. Stock Ledger

Stock Ledger provides voucher-level stock movement.

Use it to investigate:

- purchase receipt;
- sale;
- return;
- transfer;
- reconciliation;
- material receipt/issue.

This is the best place to trace why quantity changed.

---

## 14. Inventory Intelligence

Ledgix Inventory Intelligence gives a business-friendly view over ERPNext stock data.

It can support:

- current stock;
- low-stock review;
- valuation;
- movement analysis.

It does not replace Stock Ledger.

---

## 15. Accounts Payable

Supplier payable comes from ERPNext:

- Purchase Invoice;
- Purchase return;
- Payment Entry;
- GL.

Use standard ERPNext AP reports where required.

---

## 16. Cash/bank reconciliation

Payment Entry and POS payment data feed accounting.

Managers/accountants should reconcile:

- cash drawer;
- bank/card terminal;
- bank statement;
- Payment Entries;
- POS closing totals.

Do not change invoices to make a cash count match.

---

## 17. POS closing review

At end of shift, review:

- opening cash;
- cash sales;
- expected cash;
- actual cash;
- non-cash totals;
- discrepancies.

Investigate discrepancies rather than rewriting the sale history.

---

## 18. Tax reporting

Monetary tax comes from ERPNext invoice tax rows/accounts.

Use accounting/tax reports appropriate to the client's configuration.

FBR Submission Log is compliance transport evidence, not a tax ledger.

---

## 19. FBR reports/evidence

For FBR-enabled clients, review:

- invoice FBR status;
- FBR Submission Logs;
- FBR invoice/reference number;
- certification evidence;
- Offline Pending queue;
- Reconciliation Required items.

These explain compliance state around the ERPNext invoice.

They do not replace accounting reports.

---

## 20. Reconciliation Required review

This FBR state requires special attention.

It means the remote Production POST outcome may be uncertain.

Do not re-submit based only on accounting reports.

The FBR outcome must be reconciled separately.

---

## 21. Daily management review

Suggested daily checks:

- POS closings;
- failed/held transactions;
- sales totals;
- returns;
- unusual discounts/overrides;
- cash/card reconciliation;
- FBR failed/reconciliation states if enabled.

---

## 22. Weekly review

Suggested weekly:

- Accounts Receivable;
- overdue customers;
- stock shortages;
- stock adjustments;
- purchase activity;
- supplier payable;
- FBR pending/error items;
- backup status.

---

## 23. Monthly/accounting-period review

Suggested with accountant:

- General Ledger;
- Profit and Loss;
- Balance Sheet;
- tax accounts;
- AR/AP;
- stock valuation;
- bank reconciliation;
- manual journals;
- returns/credit notes;
- FBR compliance evidence where applicable.

---

## 24. Report permissions

Reports are generally intended for:

- Ledgix Manager;
- Ledgix Admin;
- System Manager;
- appropriate ERPNext accounting roles.

Cashiers should not automatically receive full financial reporting access.

---

## 25. Filters

Always check report filters:

- Company;
- date range;
- Customer/Supplier;
- Warehouse;
- status.

Many apparent report errors are actually wrong filter context.

---

## 26. Export

Authorized users may export reports where permissions allow.

Treat exported data as sensitive business information.

Do not send client financial exports through insecure channels.

---

## 27. If a report does not match the screen

Identify the official source document.

Example:

If Customer Statement disagrees with a manual spreadsheet:

- inspect Sales Invoice;
- Payment Entry;
- Credit Note;
- GL.

Do not overwrite ERPNext to match the spreadsheet without proving ERPNext is wrong.

---

## 28. If stock report looks wrong

Trace Stock Ledger Entry vouchers.

Check:

- correct Warehouse;
- posting date/time;
- Purchase Receipt;
- Sales/POS Invoice;
- returns;
- Stock Entry;
- Stock Reconciliation.

---

## 29. If profit looks wrong

Review:

- selling revenue;
- Item valuation/COGS;
- purchase/stock chronology;
- expense/income account configuration;
- returns;
- taxes.

Do not substitute selling price for valuation.

---

## 30. If receivable looks wrong

Review:

- submitted Sales Invoice;
- due date;
- outstanding_amount;
- Payment Entry references;
- Credit Notes;
- unallocated advances.

The current balance must come from ERPNext.

---

## 31. Audit trail

Do not delete submitted transactions simply to clean reports.

Use:

- proper cancellation where allowed;
- return/Credit Note;
- Payment Entry correction;
- Stock Reconciliation where physically justified.

Preserving transaction history is important.

---

## 32. Accounting responsibility

Ledgix provides software workflows.

The client remains responsible for:

- correct Chart of Accounts;
- legally correct tax treatment;
- correct accounting policy;
- reconciliation;
- financial review.

Use a qualified accountant/tax adviser where needed.

---

## 33. Management checklist

- [ ] daily POS closing reviewed
- [ ] cash/card reconciled
- [ ] receivables reviewed
- [ ] overdue reviewed
- [ ] purchases/payables reviewed
- [ ] stock balance reviewed
- [ ] unusual stock adjustments reviewed
- [ ] GL/P&L reviewed periodically
- [ ] FBR exceptions reviewed if enabled
- [ ] verified backups monitored

---

## 34. Summary

> **Use Ledgix reports for focused operational visibility and ERPNext reports/ledgers for official accounting truth; when a number looks wrong, trace the native source transactions instead of maintaining a second manual balance.**
