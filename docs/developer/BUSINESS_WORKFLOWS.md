# Ledgix POS — Business Workflows

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Companion authority:** docs/developer/ARCHITECTURE.md

## 1. Purpose

This document describes the current end-to-end business workflows implemented by Ledgix after the ERPNext-core migration.

It is intentionally workflow-oriented. It answers:

- what document is created for each business event;
- which ERPNext record is authoritative;
- where Ledgix adds UX, idempotency, metadata or validation;
- how returns, payments, purchasing and stock corrections are represented;
- which historical Ledgix DocTypes must not be used for new business activity.

Detailed implementation documents cover POS, selling/payments and purchasing/inventory separately.

The governing rule is:

> **The Ledgix screen may initiate the workflow, but ERPNext owns the resulting business, stock and accounting truth.**

---

## 2. Authority map

| Business event | Current authority |
|---|---|
| Retail shift open | ERPNext POS Opening Entry |
| Retail sale | ERPNext POS Invoice |
| Retail tender / split payment | Native POS Invoice payment rows |
| Held retail cart | Draft ERPNext POS Invoice + Ledgix hold metadata |
| Held B2B cart | Draft ERPNext Sales Invoice + Ledgix hold metadata |
| Retail return | Return ERPNext POS Invoice |
| Retail shift close | ERPNext POS Closing Entry |
| POS consolidation/accounting | Standard ERPNext POS consolidation |
| B2B sale | ERPNext Sales Invoice |
| Customer receipt | ERPNext Payment Entry |
| Customer outstanding | ERPNext Sales Invoice + Payment Entry / GL state |
| B2B return / Credit Note | Return ERPNext Sales Invoice |
| Customer refund | ERPNext Payment Entry of type Pay |
| Exchange | Credit Note + replacement Sales Invoice |
| Purchase order | ERPNext Purchase Order |
| Goods receipt | ERPNext Purchase Receipt |
| Supplier invoice | ERPNext Purchase Invoice |
| Supplier payment | ERPNext Payment Entry |
| Purchase return | Return ERPNext Purchase Invoice |
| Stock receipt / issue / transfer | ERPNext Stock Entry |
| Physical count correction | ERPNext Stock Reconciliation |
| Quantity / valuation truth | ERPNext Stock Ledger Entry + Bin |
| Batch / serial identity | ERPNext Batch / Serial No / Serial and Batch Bundle |
| Monetary tax | ERPNext native taxes and charges |
| Accounting | ERPNext GL / AR / AP |
| FBR commercial source | Submitted ERPNext Sales Invoice / POS Invoice |

Historical Ledgix business DocTypes may remain physically present but are not valid current transaction authorities.

---

## 3. Common workflow principles

### 3.1 Company context must be valid

Current services resolve a real ERPNext Company.

A transaction must not silently fall back into a Ledgix-only commercial context.

### 3.2 Native identities are preferred

Current services resolve native:

- Customer;
- Supplier;
- Item;
- Price List;
- Mode of Payment;
- Warehouse.

Migration compatibility may resolve an old Ledgix identifier into its ERPNext counterpart.

That mapping support does not make the old record authoritative.

### 3.3 Idempotency metadata is not a ledger

Ledgix uses client/request identifiers on several current transaction paths.

Examples include client sale, payment, return, purchase, receipt and stock identifiers.

The purpose is to make retries safer and prevent accidental duplicate native transactions.

An idempotency key does not create a separate Ledgix transaction model.

### 3.4 Native document lifecycle must be respected

A draft, submitted and cancelled ERPNext document have different accounting/stock meaning.

Do not bypass native lifecycle by editing ledgers or creating shadow status rows.

### 3.5 UI success is not enough

For important operations, verify the ERPNext result:

- correct native document;
- correct docstatus;
- correct party/company;
- correct stock/accounting effect;
- correct references;
- correct outstanding or payable state;
- correct return/cancellation linkage.

---

## 4. Retail POS workflow

### 4.1 Preconditions

A retail workflow requires an ERPNext POS setup for the active user/company, including:

- enabled POS Profile;
- customer/default-customer behavior;
- Selling Price List;
- active leaf Warehouse;
- configured Modes of Payment;
- valid Company account mappings;
- user access;
- submitted POS Opening Entry before checkout.

The Ledgix POS screen consumes these native records.

### 4.2 Open shift

Flow:

    Ledgix POS
      -> open shift action
      -> ERPNext POS Opening Entry
      -> submit

The current service reuses an existing active opening for the same applicable user/profile rather than deliberately creating a second active shift.

Opening balances are represented by the native opening balance rows.

Do not create a new Ledgix POS Shift.

### 4.3 Search catalog / pricing / stock

The POS screen resolves:

- Item from ERPNext Item;
- barcode from native item barcode data;
- price through ERPNext pricing / Price List;
- warehouse from POS Profile/company;
- quantity from ERPNext stock state;
- batch/serial requirements from ERPNext Item configuration.

The displayed catalog is a product view over native authority.

### 4.4 Preview checkout

Preview builds the intended native transaction and calculates according to ERPNext pricing/tax authority.

Preview is not a posting event.

It must not create accounting or stock truth independently of the final native invoice.

### 4.5 Complete retail sale

Flow:

    active POS Opening Entry
      -> build POS Invoice
      -> native payment rows
      -> submit POS Invoice
      -> ERPNext stock/accounting behavior
      -> optional FBR workflow on same POS Invoice

Checkout requires an active opening.

Where a client sale ID is supplied, a retry can resolve to the already-created native POS Invoice rather than intentionally create a duplicate.

### 4.6 Split tender

Split payment is stored on the ERPNext POS Invoice.

Example:

    POS Invoice
      payments:
        Cash: 1000
        Card: 2000

Rules enforced by the current service include:

- Mode of Payment must be configured on the POS Profile;
- payment amount must be positive;
- required payment reference must be supplied where configured;
- full payment is required unless the POS Profile permits partial payment;
- over-tendering requires an appropriate Cash mode that allows change.

Do not mirror the same tender into a new Ledgix Payment.

### 4.7 Hold / resume

Retail hold:

    cart
      -> draft ERPNext POS Invoice
      -> Ledgix hold metadata

B2B hold:

    cart
      -> draft ERPNext Sales Invoice
      -> Ledgix hold metadata

The draft document is the commercial draft.

Hold metadata helps restore the Ledgix user experience.

Cancelling a hold is not a financial cancellation because the held transaction has not been submitted.

### 4.8 Retail return

Flow:

    submitted original POS Invoice
      -> select returnable rows / quantities
      -> require reason
      -> ERPNext POS return mapper
      -> submit return POS Invoice

The service requires:

- submitted non-return source POS Invoice;
- return reason;
- active ERPNext POS opening;
- valid selected source rows;
- quantity not exceeding ERPNext returnable quantity.

The native return mapper preserves source economics.

A historical Ledgix Sales Return is not created as the financial authority.

### 4.9 Close shift

Flow:

    active POS Opening Entry
      -> expected tender totals
      -> operator actual cash
      -> ERPNext POS Closing Entry
      -> submit
      -> ERPNext standard consolidation

The current service builds the closing from the opening through ERPNext's native closing mapper.

Cash closing amount is applied to the applicable configured cash mode; other reconciliation rows use native expected amounts unless business input dictates otherwise.

After closing, verify the opening/closing lifecycle and consolidation state.

---

## 5. B2B sales workflow

### 5.1 Create sale

Flow:

    Customer + Items
      -> ERPNext pricing / tax
      -> Sales Invoice
      -> submit
      -> ERPNext AR / GL
      -> optional stock effect
      -> optional FBR workflow

The Ledgix service uses ERPNext-native pricing rather than a raw fallback that bypasses effective-date/UOM/pricing behavior.

### 5.2 Stock behavior

Sales Invoice stock effect depends on the selected ERPNext workflow.

Where update_stock is enabled, the invoice produces the stock effect.

Where the business uses delivery or another native stock flow, that native flow remains authoritative.

Do not maintain a Ledgix stock counter beside ERPNext.

### 5.3 Idempotent retry

A client sale ID can resolve to an existing active Sales Invoice for the same Company.

The retry returns the original native document instead of deliberately creating another invoice.

### 5.4 Customer receipt

Flow:

    submitted Sales Invoice(s)
      -> validate positive outstanding
      -> create Payment Entry
      -> allocate references
      -> submit
      -> ERPNext recalculates outstanding

Current Ledgix payment posting requires at least one invoice allocation.

For a true unapplied customer advance, use the native ERPNext Payment Entry workflow rather than inventing a fake invoice allocation.

### 5.5 Receivable truth

Receivable state comes from submitted ERPNext Sales Invoices and Payment Entries.

The current Ledgix service derives:

- positive outstanding;
- invoice credit;
- unallocated customer advance;
- net balance;
- overdue;
- available credit;
- oldest due date.

Historical Ledgix Sale/Payment rows are not used to reconstruct current AR.

---

## 6. Sales return / Credit Note workflow

### 6.1 B2B return

Flow:

    submitted Sales Invoice
      -> select exact source rows and quantities
      -> reason
      -> ERPNext return mapper
      -> submit return Sales Invoice

The returned Sales Invoice is the Credit Note.

The current service:

- requires a submitted non-return source invoice;
- uses exact source row mapping where possible;
- rejects unmatched requested rows;
- preserves the original native submitted line rate;
- does not accept a client-supplied replacement rate as return authority.

### 6.2 Customer refund

A Credit Note and a cash/bank refund are different events.

Refund flow:

    submitted Credit Note
      -> ERPNext Payment Entry mapper
      -> payment_type = Pay
      -> allocate negative Credit Note reference
      -> submit

The current service validates that:

- source is a submitted return invoice;
- refund amount is positive;
- refund does not exceed the Credit Note refundable outstanding;
- Mode of Payment resolves to a valid Company account.

### 6.3 Exchange

Exchange is represented as two native documents:

    1. Credit Note against original Sales Invoice
    2. replacement Sales Invoice

Ledgix may link them through an exchange reference.

Do not collapse the exchange into an invisible net custom transaction.

---

## 7. Purchasing workflow

### 7.1 Full purchase chain

Preferred controlled procurement flow:

    Supplier
      -> Purchase Order
      -> Purchase Receipt
      -> Purchase Invoice
      -> Payment Entry

Each stage is an ERPNext-native document.

### 7.2 Purchase Order

The service resolves:

- ERPNext Supplier;
- ERPNext Items;
- active leaf Warehouse;
- positive quantities.

It then creates the ERPNext Purchase Order.

A client purchase ID can prevent intentional duplicate creation on retry.

### 7.3 Purchase Receipt

A submitted Purchase Order can be mapped through ERPNext into a Purchase Receipt.

For stock items, the native receipt row receives the resolved target Warehouse.

Submitting the receipt creates native stock effects.

### 7.4 Purchase Invoice from receipt

A submitted Purchase Receipt can be mapped through ERPNext into a Purchase Invoice.

The Purchase Invoice becomes the AP authority.

### 7.5 Direct purchase invoice

The Ledgix service also supports a direct ERPNext Purchase Invoice.

When update_stock is enabled, the invoice itself creates the stock effect.

Do not create a duplicate Purchase Receipt for the same physical receipt unless that is intentionally part of the native ERPNext workflow.

### 7.6 Supplier payment

Flow:

    submitted non-return Purchase Invoice
      -> resolve Mode of Payment
      -> validate Company payment account
      -> build Payment Entry
      -> allocate amount
      -> submit

Payment amount must be positive and cannot exceed the current invoice outstanding.

### 7.7 Purchase return

Flow:

    submitted non-return Purchase Invoice
      -> ERPNext purchase return mapper
      -> submit return Purchase Invoice

The returned Purchase Invoice is native ERPNext return/accounting evidence.

---

## 8. Inventory workflow

### 8.1 Stock authority

Current stock truth is:

    ERPNext Stock Ledger Entry + Bin

Valuation and stock value are also native ERPNext concerns.

### 8.2 Stock snapshot

The Ledgix buying/inventory service exposes a snapshot from ERPNext Bin/stock state for a resolved Item + Warehouse.

It is a read model, not a new ledger.

### 8.3 Material receipt / issue / transfer

Supported Ledgix service operations create native ERPNext Stock Entry documents with one of:

- Material Receipt;
- Material Issue;
- Material Transfer.

Rules include:

- Item must be stock-controlled;
- quantity must be positive;
- purpose must be supported;
- source/target Warehouse must belong to the current Company and be a valid active leaf where required;
- batch/serial inputs use ERPNext's native stock-entry mechanisms.

### 8.4 Physical count / correction

Use ERPNext Stock Reconciliation for genuine quantity/valuation correction.

Flow:

    physical verified count
      -> Item + Warehouse
      -> target quantity / valuation
      -> Stock Reconciliation
      -> submit
      -> native ledger correction

Do not use Stock Reconciliation as a substitute for a missing sale, purchase or transfer when the real business event should be recorded instead.

### 8.5 Batch / serial

Batch and serial identity belongs to ERPNext.

The Ledgix service can:

- ensure a Batch exists for the correct Item;
- list available native Serial No records;
- pass batch/serial data into native stock transactions.

Historical Ledgix Stock Lot / Stock Serial tables are not current stock identity authority.

---

## 9. Cancellation and correction

Submitted native documents should be corrected through native ERPNext lifecycle.

Examples:

- sales return -> Credit Note / return invoice;
- purchase return -> return Purchase Invoice;
- customer refund -> Payment Entry;
- supplier/payment correction -> native Payment Entry lifecycle;
- material reversal/correction -> appropriate ERPNext voucher;
- physical count correction -> Stock Reconciliation;
- cancellation -> only where native business/accounting rules allow.

Do not:

- edit GL Entry directly;
- edit Stock Ledger Entry directly;
- delete submitted vouchers to make a test clean;
- reactivate frozen Ledgix business ledgers;
- write compensating custom balances outside ERPNext.

---

## 10. FBR touchpoint

FBR does not replace the business workflow.

It attaches to the submitted ERPNext sales source.

Current commercial sources are:

- Sales Invoice;
- POS Invoice.

High-level relationship:

    valid ERPNext sale
      -> immutable Ledgix FBR evidence
      -> readiness / payload
      -> controlled FBR transport
      -> status/log/reconciliation

The business transaction remains an ERPNext transaction even while FBR is:

- Disabled;
- awaiting Sandbox evidence;
- Offline Pending;
- Reconciliation Required;
- not Production-ready.

FBR architecture is documented separately.

---

## 11. Reporting / verification

Current reporting should verify native ERPNext state.

Useful native evidence includes:

- Sales Invoice / POS Invoice;
- Payment Entry;
- Purchase Order / Receipt / Invoice;
- Stock Entry;
- Stock Reconciliation;
- Stock Ledger Entry;
- Bin;
- General Ledger;
- Accounts Receivable;
- Accounts Payable;
- POS Opening/Closing Entry.

Ledgix reports and Intelligence surfaces may aggregate these records.

They must not derive current business truth from frozen legacy transaction tables.

---

## 12. Legacy business behaviors that must not return

Do not create current transactions in:

- Ledgix Sale;
- Ledgix Purchase;
- Ledgix Payment;
- Ledgix Sales Return;
- Ledgix POS Shift;
- Ledgix POS Hold;
- Ledgix Stock Movement;
- Ledgix Stock Lot;
- Ledgix Stock Serial.

Do not:

- dual-post one business event to Ledgix and ERPNext;
- reconstruct current AR/AP from legacy rows;
- use historical Ledgix stock counters for availability;
- use a custom split-payment ledger beside POS Invoice.payments;
- use a historical negative-sale model instead of native returns;
- mutate accounting or stock merely to satisfy an obsolete migration-era test.

---

## 13. Operator/developer verification checklist

### Retail sale

Verify:

- submitted POS Invoice;
- correct POS Profile / Customer / Company;
- correct Warehouse;
- payment rows;
- stock/accounting behavior;
- active opening relationship;
- correct print target;
- FBR state only if enabled.

### Retail return

Verify:

- return POS Invoice;
- return_against/source relationship;
- negative returned quantities;
- correct remaining returnable quantity;
- stock/accounting reversal;
- active shift requirement satisfied.

### B2B sale

Verify:

- submitted Sales Invoice;
- native price/tax calculation;
- update_stock behavior as designed;
- current outstanding;
- FBR state if applicable.

### Customer payment

Verify:

- submitted Payment Entry;
- correct Customer and Company;
- correct references/allocations;
- invoice outstanding changed through ERPNext.

### Purchase

Verify:

- correct chain for the chosen workflow;
- stock received exactly once;
- AP appears on Purchase Invoice;
- supplier payment allocates correctly.

### Stock movement

Verify:

- submitted Stock Entry/Reconciliation;
- correct warehouse direction;
- Stock Ledger Entry reflects the result;
- Bin matches native stock state.

---

## 14. Source boundaries

Primary current implementation:

- services/erpnext_pos.py
- api/pos_compat.py
- services/erpnext_selling.py
- api/selling_compat.py
- services/erpnext_payment_policy.py
- services/erpnext_buying_inventory.py
- services/erpnext_reporting.py
- hooks.py

Historical migration documents may explain how these workflows were cut over, but this document and current code define present operation.

---

## 15. Summary

The current Ledgix workflow model is:

> **Ledgix initiates and presents the workflow; ERPNext creates and owns the commercial, stock and accounting records; Ledgix adds controlled UX, compatibility, idempotency, reporting and compliance metadata without recreating parallel business ledgers.**
