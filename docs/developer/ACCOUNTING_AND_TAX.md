# Ledgix POS — Accounting and Tax

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Primary authority:** ERPNext accounting + ERPNext-native monetary tax  
**Companion documents:** ARCHITECTURE.md, SALES_RETURNS_AND_PAYMENTS.md, PURCHASE_AND_INVENTORY.md, FBR_ARCHITECTURE.md

## 1. Purpose

This document defines the current accounting and monetary-tax architecture of Ledgix POS.

The central rule is:

> **ERPNext is the sole current monetary, accounting, receivable, payable, stock-valuation and financial-tax authority.**

Ledgix may:

- provide product UX;
- enforce product policy;
- add FBR/legal classification metadata;
- provide approved taxable-base inputs for specific statutory treatments;
- map native tax evidence into FBR components;
- build reports over ERPNext documents and ledgers.

Ledgix must not:

- maintain a second grand total;
- maintain a second receivable/payable balance;
- maintain a second tax amount;
- post a duplicate financial ledger;
- construct hidden monetary tax rows outside ERPNext;
- modify ERPNext accounting merely to satisfy a legacy Ledgix test or historical expectation.

---

## 2. Accounting authority map

| Concept | Current authority |
|---|---|
| Sales amount | ERPNext Sales Invoice / POS Invoice |
| Purchase amount | ERPNext Purchase Invoice |
| Customer receivable | ERPNext Sales Invoice + Payment Entry + GL |
| Supplier payable | ERPNext Purchase Invoice + Payment Entry + GL |
| Customer receipt | ERPNext Payment Entry |
| Customer refund | ERPNext Payment Entry |
| Supplier payment | ERPNext Payment Entry |
| Sales return / Credit Note | ERPNext return Sales Invoice / POS Invoice |
| Purchase return | ERPNext return Purchase Invoice |
| Tax rows and monetary tax amounts | ERPNext native taxes and charges |
| Tax accounts | ERPNext Account |
| Stock quantity | ERPNext Stock Ledger Entry / Bin |
| Stock valuation | ERPNext stock/accounting engine |
| Cost of goods sold | ERPNext stock/accounting postings |
| General Ledger | ERPNext GL Entry |
| Standard financial reports | ERPNext accounting reports |
| Customer statement | ERPNext GL / native receivable state |
| FBR legal classification | Ledgix compliance metadata mapped to ERPNext transaction |
| FBR submission evidence | Ledgix FBR Submission Log + invoice fields |

---

## 3. Monetary tax authority

Current monetary tax authority is implemented in:

    services/erpnext_tax_authority.py

The service explicitly returns:

    ERPNext Native

There is no active site-config switch that selects a second Ledgix monetary tax engine.

The compatibility method native_tax_authority_enabled() returns true because the current runtime is ERPNext-native only.

---

## 4. Native sales-tax flow

Current sales/POS tax flow is conceptually:

    ERPNext Customer / Item / tax context
      -> native Tax Category / Tax Rule / Item Tax Template
      -> Sales Taxes and Charges Template / tax rows
      -> ERPNext calculate_taxes_and_totals
      -> ERPNext invoice totals
      -> ERPNext GL
      -> Ledgix FBR classification/snapshot consumes the result

Ledgix does not replace native tax rows after calculation.

---

## 5. Native tax preparation

apply_sales_tax_authority() can:

1. stamp approved legal taxable-base inputs;
2. invoke ERPNext native tax-row resolution;
3. run ERPNext calculate_taxes_and_totals;
4. assert the resulting native tax contract.

The service does not create Ledgix-owned monetary tax rows.

The historical replace_managed_rows argument is retained only for caller compatibility and has no monetary-engine effect.

---

## 6. Native tax contract validation

The current tax contract validates important invariants on Sales Invoice and POS Invoice.

### Company

The document must reference a valid ERPNext Company.

### Tax accounts

Each invoice tax row must reference a real ERPNext Account.

The account must:

- belong to the same Company;
- not be a group account;
- not be disabled.

### Native template

If taxes_and_charges is set, the Sales Taxes and Charges Template must:

- exist;
- belong to the same Company;
- be enabled.

### Item Tax Template

If an invoice item uses an Item Tax Template, the template must:

- exist;
- belong to the same Company;
- be enabled.

### Positive item-tax accounts

Positive item-tax accounts present in item_tax_rate should normally be represented by native invoice tax rows unless explicitly classified as non-posting FBR evidence.

### Legacy managed tax rows

Tax rows whose descriptions begin with the historical Ledgix managed-tax marker are rejected.

The current native tax authority must not coexist with the retired custom monetary engine.

---

## 7. Non-posting FBR tax evidence

Some FBR components can be classification/evidence without being a financial invoice tax row.

The current tax-authority service treats the FBR component:

    Sales Tax Withheld At Source

as a special non-posting mapping when configured through Ledgix FBR Tax Component Mapping.

If such an account appears as a posting invoice tax row, the native tax contract rejects it.

This prevents an FBR evidence component from silently changing ERPNext monetary tax.

---

## 8. FBR Tax Component Mapping

Ledgix FBR Tax Component Mapping maps:

    ERPNext tax Account -> FBR component meaning

Current component values include:

- Sales Tax Applicable;
- Sales Tax Withheld At Source;
- Extra Tax;
- Further Tax;
- FED Payable.

The DocType itself states:

> classification only; the amount comes from ERPNext tax rows.

Therefore the mapping answers:

> "What does this native tax evidence mean to FBR?"

It does not answer:

> "What amount should ERPNext post?"

The amount remains native ERPNext evidence.

---

## 9. FBR Item Mapping and monetary tax

Ledgix FBR Item Mapping contains regulatory/classification data such as:

- Company;
- ERPNext Item;
- HS Code;
- FBR UOM;
- FBR Sale / Transaction Type;
- rate/reference description;
- tax basis;
- notified retail price;
- SRO references;
- effective date range;
- review/evidence metadata.

Its rate/reference field is explicitly classification/reference only.

It must not become a second invoice tax calculator.

---

## 10. Tax-basis extension

A specific legal requirement can require a taxable base different from ordinary transaction value.

Current code supports two basis labels:

- Transaction Value;
- Notified Retail Price.

Implementation:

    services/erpnext_taxable_base.py

This service supplies an approved per-line taxable base to ERPNext through the configured ERPNext taxable-base resolver extension.

ERPNext still applies the tax rate and calculates/post the tax amount.

---

## 11. Notified Retail Price / Third Schedule behavior

For a line mapped to Notified Retail Price:

1. resolve the effective Ledgix FBR Item Mapping for Company + Item + posting date;
2. reject overlapping active mappings;
3. reject a mapping still marked Needs Review;
4. require positive Notified Retail Price;
5. stamp the legal basis and value on the native ERPNext invoice item;
6. let ERPNext apply the tax rate and calculate totals.

The resolver returns:

    notified retail price × quantity

as the legal base when that basis is stamped.

This is a base-input extension, not a custom monetary tax engine.

---

## 12. Return tax-basis preservation

For native returns, the taxable-base service attempts to preserve the original source line's approved Notified Retail Price basis.

It resolves the source row from the original Sales Invoice or POS Invoice.

If the original line used Notified Retail Price:

- the return line receives the same basis;
- the same source notified value is carried.

If source-row identity is ambiguous, the service fails rather than guessing.

This preserves historical legal basis on returns.

---

## 13. Effective FBR mapping

FBR Item Mapping supports:

- effective_from;
- effective_to;
- active flag.

The taxable-base service chooses the effective mapping for the invoice date.

If multiple active mappings overlap for the same Company + Item + date, the transaction fails.

Overlapping regulatory mappings must be fixed rather than arbitrarily selecting one.

---

## 14. Native non-taxable/exempt case

The tax contract can warn when an invoice has:

- no Sales Taxes and Charges Template;
- no invoice tax accounts;
- no Item Tax Template.

This can be legitimate only when the transaction is intentionally non-taxable/exempt.

A warning is not permission to ignore an expected tax configuration.

---

## 15. Tax authority on sales

Current B2B sales build an ERPNext Sales Invoice and apply native tax authority before posting.

Ledgix-specific metadata can coexist with the native tax result, but:

- grand_total;
- tax total;
- net total;
- outstanding;
- GL result

remain ERPNext values.

---

## 16. Tax authority on POS

Current retail checkout builds ERPNext POS Invoice.

The same native tax authority applies.

Split payment rows do not change who owns tax calculation.

FBR submission later consumes the native commercial/tax evidence.

---

## 17. Tax authority on returns

Current native Sales/POS returns use ERPNext return mappers.

Ledgix preserves:

- source-line rate;
- source taxable-base evidence where required;
- native return relationships.

Ledgix does not calculate an independent return-tax amount.

---

## 18. Payments

Payment Entry is the financial authority for:

- customer receipts;
- customer refunds;
- supplier payments;
- other native ERPNext settlement workflows.

Ledgix payment services may enforce additional product rules but do not maintain a second payment ledger.

---

## 19. Ledgix Payment Entry policy

Current policy hook:

    services/erpnext_payment_policy.py

hooks.py registers it on Payment Entry validate.

The hook applies only to Payment Entries marked as Ledgix-originated through current Ledgix metadata.

It checks:

- valid ERPNext Mode of Payment;
- optional enabled state if the field exists;
- configured Ledgix reference requirement;
- Company-specific Mode of Payment default account;
- paid_to / paid_from account consistency.

This is product policy over native ERPNext Payment Entry.

It is not accounting authority.

---

## 20. Customer receipts

Current customer receipt flow:

    submitted Sales Invoice(s)
      -> Payment Entry
      -> references / allocations
      -> submit
      -> native outstanding changes

For Ledgix cutover payment APIs, at least one invoice allocation is required.

A true unapplied customer advance should use native ERPNext Payment Entry directly.

---

## 21. Customer refunds

Current customer refund flow:

    submitted Credit Note
      -> ERPNext Payment Entry mapper
      -> Payment Type Pay
      -> native account/reference allocation
      -> submit

The Credit Note records the sales reversal.

The Payment Entry records actual money leaving the business.

Do not treat the Credit Note as proof of refund cash movement.

---

## 22. Supplier payments

Current supplier payment flow:

    submitted Purchase Invoice
      -> ERPNext Payment Entry mapper
      -> Company Mode of Payment account
      -> reference allocation
      -> submit

Partial payment is supported within native outstanding constraints.

---

## 23. Receivables

Current customer receivable state comes from ERPNext.

The selling service can derive:

- positive invoice outstanding;
- invoice credits;
- unallocated customer advances;
- net balance;
- overdue;
- available credit;
- oldest due date.

Authority is explicitly:

    ERPNext Sales Invoice + Payment Entry

Historical Ledgix Sale / Payment data must not be used for current AR.

---

## 24. Payables

Supplier payable truth comes from:

- Purchase Invoice;
- Payment Entry;
- AP/GL.

Do not reconstruct current supplier payable from historical Ledgix Purchase rows.

---

## 25. General Ledger

ERPNext GL is the accounting ledger.

Ledgix must not:

- insert substitute GL evidence in custom DocTypes;
- directly edit GL Entry to fix tests;
- treat a custom report total as more authoritative than native GL;
- recreate GL balances from historical Ledgix transactions.

Any discrepancy must be investigated at the native transaction/configuration layer.

---

## 26. Stock valuation and COGS

ERPNext stock/accounting owns:

- valuation;
- stock value;
- COGS;
- stock-related GL effects.

Ledgix may display these values through current reporting.

It must not maintain independent cost/valuation state as a current authority.

The final forensic hardening explicitly removed unsafe stale/fallback cost behavior from active reporting paths.

---

## 27. POS consolidation accounting

ERPNext v15 can consolidate POS activity into native accounting structures during POS closing.

Current reporting understands that native consolidation model.

The consolidated Sales Invoice is:

- an ERPNext accounting/consolidation artifact;
- not a duplicate retail business event;
- not a second FBR submission source for the same POS Invoice.

---

## 28. Current reporting authority

Implementation:

    services/erpnext_reporting.py

The module explicitly states that current Ledgix reporting reads ERPNext:

- standard masters;
- transaction documents;
- GL Entry;
- Bin;
- Stock Ledger Entry.

It does not use historical Ledgix Sale/Purchase/Payment/Stock ledgers as current truth.

---

## 29. Customer statement

Current Ledgix customer-statement reporting reads ERPNext GL Entry filtered by:

- Company;
- party_type = Customer;
- Customer;
- non-cancelled entries.

Opening balance for a selected period is computed from prior GL movement.

Running balance is:

    prior balance + debit - credit

This is a read view over native GL.

---

## 30. Sales reporting

Current sales reporting reads native:

- Sales Invoice;
- POS Invoice.

It separates normal sales from returns and avoids double-counting consolidated POS accounting invoices as independent sales.

Profit/cost calculations use native ERPNext transaction/stock evidence.

---

## 31. Purchase reporting

Current purchase reporting reads ERPNext Purchase Invoice.

Report values such as:

- quantity;
- total cost;
- average cost

are reporting projections of native Purchase Invoice rows.

---

## 32. Stock reporting

Current stock reports use ERPNext:

- Item;
- Bin;
- Stock Ledger Entry;
- Warehouse;
- Item Reorder;
- Item Price where appropriate for presentation.

Stock quantity and valuation remain native.

---

## 33. Financial correction principles

Correct accounting through supported ERPNext lifecycle.

Examples:

- customer return -> native Credit Note;
- customer refund -> Payment Entry;
- purchase return -> return Purchase Invoice;
- payment correction -> native Payment Entry lifecycle;
- stock correction -> appropriate Stock Entry / Stock Reconciliation;
- invoice cancellation -> native cancellation only where legally/accountingly allowed.

Never:

- delete submitted evidence to hide an error;
- edit GL rows directly;
- edit Stock Ledger rows directly;
- create custom offset balances outside ERPNext.

---

## 34. FBR relationship

FBR is not the accounting engine.

Relationship:

    ERPNext transaction
      -> native monetary tax
      -> native total / GL
      -> Ledgix immutable compliance snapshot
      -> FBR payload
      -> FBR submission evidence

FBR Item Mapping and FBR Tax Component Mapping add legal/classification meaning.

They do not replace native financial calculation.

---

## 35. Submission Log is not accounting

Ledgix FBR Submission Log records compliance transport/evidence such as:

- reference document;
- FBR status;
- FBR invoice number;
- attempt information;
- request/response evidence;
- errors;
- offline evidence.

It must never be used as:

- sales ledger;
- receivable ledger;
- tax ledger;
- GL substitute.

The ERPNext invoice remains the commercial/accounting record.

---

## 36. Retired tax models

The old mixed Ledgix monetary-tax architecture has been retired from current authority.

Retired current-use concepts include historical Ledgix:

- Tax Profile;
- Tax Category;
- Tax Rate;
- Item Tax Profile;
- global FBR Settings monetary/configuration model.

Current monetary tax uses ERPNext.

Some historical audit/detail records remain evidence only.

---

## 37. Retired managed tax rows

The native tax contract explicitly rejects historical invoice tax rows marked with the old Ledgix managed-tax prefix.

This is a runtime guard against accidentally mixing:

- current ERPNext-native tax;
- retired custom tax-row management.

---

## 38. Company isolation

Accounting/tax configuration is Company-sensitive.

Examples:

- Account must belong to invoice Company;
- Sales Taxes and Charges Template must belong to invoice Company;
- Item Tax Template must belong to invoice Company where applicable;
- Mode of Payment account must belong to transaction Company;
- FBR mappings are Company-scoped.

Cross-company fallback is a defect.

---

## 39. Permission boundary

Accounting authority does not imply every Ledgix role can edit every native ERPNext document.

Frappe/ERPNext permission rules remain server authority.

Ledgix product visibility is only navigation.

See SECURITY_AND_PERMISSIONS.md for detailed authorization rules.

---

## 40. Testing principles

Accounting/tax tests should verify:

- native document result;
- native tax rows;
- native totals;
- native GL/stock effects where applicable;
- correct Company/account mapping;
- native return behavior;
- no legacy managed tax rows;
- no second monetary engine.

Do not mutate production-like accounting configuration just to satisfy an obsolete historical test expectation.

---

## 41. Current code map

| Concern | Current source |
|---|---|
| Monetary tax authority | services/erpnext_tax_authority.py |
| Legal taxable-base input | services/erpnext_taxable_base.py |
| Customer receipts/refunds/AR | services/erpnext_selling.py |
| Supplier payments/AP workflow | services/erpnext_buying_inventory.py |
| Ledgix Payment Entry policy | services/erpnext_payment_policy.py |
| Reporting/customer statement | services/erpnext_reporting.py |
| Invoice tax/FBR hooks | hooks.py |
| FBR component mapping | Ledgix FBR Tax Component Mapping |
| FBR item classification | Ledgix FBR Item Mapping |

---

## 42. Development checklist

Before changing accounting/tax behavior, confirm:

- [ ] ERPNext still calculates monetary tax.
- [ ] ERPNext still owns invoice totals.
- [ ] ERPNext still posts GL.
- [ ] Account belongs to correct Company.
- [ ] Tax templates belong to correct Company.
- [ ] Return preserves native source economics.
- [ ] Any legal taxable-base extension supplies only the base, not the tax amount.
- [ ] FBR mapping remains classification/evidence.
- [ ] Payment Entry remains settlement authority.
- [ ] Current reports read ERPNext-native evidence.
- [ ] No legacy tax-managed rows are reintroduced.
- [ ] No current AR/AP is reconstructed from frozen Ledgix records.
- [ ] No ERPNext core file is modified.

---

## 43. Summary

The accounting and tax architecture in one sentence is:

> **ERPNext calculates and posts every current monetary/accounting outcome; Ledgix may enforce product policy and add FBR-specific legal classification or taxable-base inputs, but it never owns a competing tax amount, balance, ledger or financial truth.**
