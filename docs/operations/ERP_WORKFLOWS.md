# Ledgix ERPNext Operating Workflows

**Status:** CURRENT  
**Architecture:** ERPNext-core migration COMPLETE  
**Applies to:** Frappe 15 / ERPNext 15 / `ledgix_saas`  
**Transaction authority:** ERPNext

## Purpose

This runbook describes the **current day-to-day business transaction flows** in Ledgix after the ERPNext-core migration.

It is intentionally operational. Architecture ownership is documented separately in `docs/architecture/CURRENT_ARCHITECTURE.md`; local acceptance data is documented in `docs/operations/LOCAL_DEMO_DATA.md`.

The central rule is simple:

> Ledgix may provide the product UI, workflow adapters, metadata and compliance layer, but ERPNext documents are the business, stock and accounting source of truth.

Do not create new operating data in retired duplicate Ledgix transaction ledgers.

---

## 1. Authority map

| Business operation | Current authority |
|---|---|
| Retail shift open | ERPNext `POS Opening Entry` |
| Retail sale | ERPNext `POS Invoice` |
| POS payment rows / split tender | ERPNext `Sales Invoice Payment` child rows on `POS Invoice.payments` |
| Held retail cart | Draft ERPNext `POS Invoice` + Ledgix hold metadata |
| Held B2B cart | Draft ERPNext `Sales Invoice` + Ledgix hold metadata |
| Retail return | ERPNext return `POS Invoice` linked to original POS Invoice |
| Shift close / POS consolidation | ERPNext `POS Closing Entry` + standard POS consolidation |
| B2B sale | ERPNext `Sales Invoice` |
| Customer receipt | ERPNext `Payment Entry` |
| B2B return / Credit Note | ERPNext return `Sales Invoice` |
| Customer refund | ERPNext `Payment Entry` of type `Pay` against Credit Note |
| Exchange | ERPNext Credit Note + replacement `Sales Invoice` |
| Purchase order | ERPNext `Purchase Order` |
| Goods receipt | ERPNext `Purchase Receipt` |
| Supplier invoice | ERPNext `Purchase Invoice` |
| Supplier payment | ERPNext `Payment Entry` |
| Stock movement | ERPNext `Stock Entry` |
| Physical/count adjustment | ERPNext `Stock Reconciliation` |
| Quantity/valuation truth | ERPNext Stock Ledger + `Bin` |
| Batch / serial tracking | ERPNext `Batch` / `Serial No` |
| FBR source transaction | Submitted ERPNext `Sales Invoice` / `POS Invoice` |

---

## 2. Retail POS lifecycle

### 2.1 Preconditions

A retail cashier needs a valid ERPNext POS configuration for the active Company:

- enabled `POS Profile`;
- assigned/default customer;
- active leaf Warehouse;
- Selling Price List;
- configured Modes of Payment and their Company accounts;
- user permission/role access;
- a submitted open `POS Opening Entry` before checkout.

The retained Ledgix POS screen reads these ERPNext records. It must not maintain parallel retail masters.

### 2.2 Open shift

Flow:

```text
Ledgix POS -> Open Shift -> ERPNext POS Opening Entry -> Submit
```

Opening cash is stored through the native opening balance rows for the POS Profile payment methods.

If the same user/Profile already has an active submitted opening, the adapter reuses that opening rather than creating a second active shift.

**Authority:** `POS Opening Entry`.

Do not create or revive `Ledgix POS Shift` for new operation.

### 2.3 Load catalog and prices

The Ledgix screen resolves:

- Item from ERPNext `Item`;
- selling price from ERPNext pricing/Price List;
- stock from ERPNext `Bin` / Stock Ledger;
- barcode from ERPNext Item Barcode;
- warehouse from the POS Profile/current Company;
- batch/serial requirements from ERPNext Item configuration.

A displayed Ledgix value is not a second stock or pricing ledger.

### 2.4 Complete a sale

Flow:

```text
Open POS shift
  -> select ERPNext Items
  -> ERPNext pricing/tax calculation
  -> add native POS payment rows
  -> submit ERPNext POS Invoice
```

Checkout is rejected if there is no active ERPNext POS opening for the cashier/Profile.

Where client request IDs are supplied, the compatibility layer uses them for idempotency so a repeated request does not intentionally create a duplicate sale.

### 2.5 Split payments

Split tender is native POS payment data.

Example:

```text
POS Invoice
  payments:
    Cash  = 1,000
    Card  = 2,000
```

ERPNext v15 stores those rows in the `Sales Invoice Payment` child DocType used by `POS Invoice.payments`.

Do not create a separate `Ledgix Payment` to represent the same POS tender.

Payment behavior follows the active POS Profile, including:

- allowed Modes of Payment;
- required references where configured;
- partial-payment policy;
- cash/change policy.

### 2.6 Hold and resume

Current Hold/Resume deliberately avoids the historical `Ledgix POS Hold` ledger.

Retail hold:

```text
cart -> draft ERPNext POS Invoice -> Ledgix hold metadata
```

B2B hold:

```text
cart -> draft ERPNext Sales Invoice -> Ledgix hold metadata
```

The draft carries fields such as the Ledgix hold ID/status/request payload. Resume reconstructs the cart from the draft/request data and current ERPNext pricing context.

Cancel Hold marks the hold metadata cancelled; it does not create a financial transaction.

**Important:** a held cart is a draft convenience state, not a submitted sale/accounting entry.

### 2.7 Retail return

Flow:

```text
submitted original POS Invoice
  -> select returnable original rows/quantities
  -> require reason
  -> ERPNext return mapper
  -> submit return POS Invoice
```

A retail return requires an active ERPNext POS opening.

The return must reference the original submitted non-return POS Invoice. Already-returned quantity is considered so the operator cannot legitimately return more than the remaining returnable quantity.

The return remains part of ERPNext's native POS/stock/accounting chain.

Do not post a new `Ledgix Sales Return` as the financial authority.

### 2.8 Close shift

Flow:

```text
active POS Opening Entry
  -> calculate expected payment totals
  -> enter actual cash
  -> ERPNext POS Closing Entry
  -> submit
  -> standard ERPNext POS consolidation
```

The closing is built from the active ERPNext opening and its unclosed POS invoices.

Before treating a shift as complete, verify:

- the `POS Closing Entry` submitted successfully;
- the opening is closed;
- managed submitted POS invoices are consolidated as expected;
- cash variance, if any, is understood;
- no duplicate active opening was created for the same cashier/Profile.

---

## 3. B2B sales and receivables

### 3.1 B2B sale

Current B2B sale authority is ERPNext `Sales Invoice`.

Flow:

```text
Customer
  -> ERPNext pricing / tax plan
  -> Sales Invoice
  -> submit
  -> ERPNext receivable/outstanding
```

Ledgix may provide a faster B2B checkout surface, but the resulting financial document is the native Sales Invoice.

The invoice can carry Ledgix metadata for channel, idempotency, checkout source, exchange reference and FBR state without becoming a parallel ledger.

### 3.2 Stock effect

Do not assume every B2B Sales Invoice must behave identically.

ERPNext `Sales Invoice.update_stock` determines whether that invoice directly creates stock impact. The selected business workflow must intentionally choose either:

- Sales Invoice with stock update; or
- a separate ERPNext delivery/stock workflow where appropriate.

The authoritative result must always be visible in ERPNext Stock Ledger/Bin, never in a Ledgix-only stock counter.

### 3.3 Customer payment

For invoice settlement through the Ledgix cutover path:

```text
submitted Sales Invoice(s)
  -> validate positive outstanding
  -> create ERPNext Payment Entry
  -> allocate to invoice reference(s)
  -> submit
  -> ERPNext recalculates outstanding
```

The Ledgix adapter requires at least one Sales Invoice allocation for this path.

For an **unapplied customer advance**, use native ERPNext Payment Entry directly rather than faking an invoice allocation.

A payment allocation cannot cross Customer or Company boundaries, and an allocation cannot exceed the invoice's current positive outstanding.

### 3.4 Receivable truth

Customer receivable state comes from submitted ERPNext `Sales Invoice` and `Payment Entry` records.

Use ERPNext values for:

- outstanding;
- overdue;
- credit balance;
- unallocated customer advance;
- available credit;
- due date.

Do not reconstruct receivables from historical `Ledgix Payment` / `Ledgix Sale` rows.

### 3.5 B2B return / Credit Note

Flow:

```text
submitted original Sales Invoice
  -> choose original invoice rows and return quantities
  -> require reason
  -> ERPNext return mapper
  -> submit return Sales Invoice / Credit Note
```

The return mapper carries the original submitted line rate. A client-supplied return rate must not replace it.

The resulting Credit Note references the source Sales Invoice and participates in native ERPNext accounting.

### 3.6 Refund after Credit Note

If money must actually be paid back to the customer:

```text
submitted Credit Note with refundable outstanding
  -> ERPNext Payment Entry
  -> payment_type = Pay
  -> allocate to Credit Note
  -> submit
```

Do not treat creation of a Credit Note by itself as proof that cash/bank refund occurred.

### 3.7 Exchange

An exchange is intentionally represented as two native financial documents:

```text
1. Credit Note against original Sales Invoice
2. Replacement Sales Invoice
```

A shared exchange reference may link the two for product UX/audit purposes.

Do not net the exchange into a hidden custom transaction that bypasses ERPNext.

---

## 4. Purchasing workflow

### 4.1 Standard purchase chain

Preferred full purchasing flow:

```text
Supplier
  -> Purchase Order
  -> Purchase Receipt
  -> Purchase Invoice
  -> Payment Entry
```

All documents are ERPNext-native.

Use the normal chain when receiving and invoicing need independent operational control.

### 4.2 Purchase Order

A Ledgix purchase request resolves the native Supplier, Items and target leaf Warehouse, then creates ERPNext `Purchase Order`.

The Purchase Order is the order authority. `Ledgix Purchase` is historical only.

### 4.3 Goods receipt

A submitted Purchase Order can be mapped to ERPNext `Purchase Receipt`.

For stock items, the resolved warehouse is written to the native receipt rows. Submission creates the normal ERPNext stock effects.

### 4.4 Supplier invoice

A submitted Purchase Receipt can be mapped to ERPNext `Purchase Invoice`.

The invoice becomes Accounts Payable authority.

### 4.5 Direct Purchase Invoice

For a simpler workflow, the compatibility service also supports a direct ERPNext `Purchase Invoice`.

When `update_stock = 1`, the Purchase Invoice itself produces the stock effect. Use this intentionally; do not also post a duplicate receipt for the same physical receipt unless the ERPNext workflow calls for it.

### 4.6 Supplier payment

Supplier settlement is an ERPNext `Payment Entry` created against a submitted non-return Purchase Invoice.

The selected Mode of Payment must have a valid Company account mapping.

---

## 5. Inventory and stock control

### 5.1 Stock truth

Current quantity and valuation authority is:

```text
ERPNext Stock Ledger Entry + Bin
```

Ledgix Inventory Intelligence may aggregate/present this information, but must not maintain an independent stock balance.

### 5.2 Stock Entry

Use ERPNext `Stock Entry` for supported operational movements such as:

- Material Receipt;
- Material Issue;
- Material Transfer.

The source/target warehouse must be a valid active leaf warehouse for the Company.

Where an Item is batch/serial controlled, use ERPNext batch/serial fields and rules.

### 5.3 Stock Reconciliation

Use ERPNext `Stock Reconciliation` when the business purpose is correcting system quantity/valuation to a verified physical count.

Do not use reconciliation as a routine substitute for missing purchase, sale or transfer documents.

### 5.4 Batch and serial tracking

Batch/serial ownership belongs to ERPNext.

- batch-controlled Item -> ERPNext `Batch` rules;
- serial-controlled Item -> ERPNext `Serial No` rules;
- availability -> native stock state/warehouse;
- sale/transfer/receipt must carry the required native tracking data.

Historical `Ledgix Stock Lot` and `Ledgix Stock Serial` records are not the current operational authority.

### 5.5 Negative stock

Whether ERPNext permits negative stock is a site/accounting policy decision, but Ledgix must not hide or fabricate quantity to work around it.

If a transaction fails because ERPNext stock rules reject it, fix the underlying ERPNext stock chronology/configuration rather than writing around the Stock Ledger.

---

## 6. Cancellation and correction principles

Submitted ERPNext business documents are accounting/stock evidence.

Corrections should use the native ERPNext lifecycle appropriate to the document:

- return / Credit Note for sales return;
- Payment Entry cancellation/reversal where appropriate;
- native voucher cancellation where business/accounting rules permit;
- Stock Reconciliation for genuine physical-count adjustment;
- linked replacement documents where required.

Do not directly delete submitted vouchers or edit GL/Stock Ledger rows to make a test appear clean.

The local acceptance dataset follows the same principle: submitted history is preserved rather than casually reset.

---

## 7. FBR touchpoint

FBR is a **compliance layer around native ERPNext sales documents**, not a second sales ledger.

Current source documents are:

```text
Sales Invoice
POS Invoice
```

The business transaction must remain valid ERPNext state regardless of FBR transport state.

### Current readiness boundary

- FBR architecture/code: CURRENT.
- Local operating dataset: FBR transport intentionally `Disabled`.
- Real client Sandbox proof/certification: DEFERRED until real seller credentials/token/scenario evidence are available.
- FBR Production activation: **NOT YET PRODUCTION-READY** without the required real-client Sandbox/production gates.

Ambiguous Production POST outcomes must be reconciled explicitly. Current hooks deliberately do **not** provide a blind scheduled retry loop.

See `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md` for the compliance workflow.

---

## 8. Legacy behaviors that must not return

Do not use these retired Ledgix business ledgers as the authority for new transactions:

```text
Ledgix Sale
Ledgix Purchase
Ledgix Payment
Ledgix Sales Return
Ledgix POS Shift
Ledgix POS Hold
Ledgix Stock Movement
Ledgix Stock Lot
Ledgix Stock Serial
```

Compatibility fields/adapters may still exist to preserve migration references or old client API contracts. That does **not** make the legacy DocTypes valid write targets.

Also do not:

- write parallel stock balances;
- calculate a second receivable ledger;
- post a legacy Ledgix sale and ERPNext invoice for the same business event;
- create split-payment rows outside the native POS Invoice payment children;
- bypass ERPNext returns with an independent negative custom sale;
- blindly retry ambiguous FBR Production submissions.

---

## 9. Operator verification by workflow

After an important transaction, verify the authoritative ERPNext result rather than only trusting a success toast.

### Retail sale

Check:

- submitted `POS Invoice` exists;
- correct Customer/Profile/Warehouse;
- payment rows and amounts are correct;
- stock effect matches the sold Items;
- invoice is associated with the active shift;
- print target is the native POS Invoice.

### Shift close

Check:

- `POS Closing Entry` submitted;
- expected vs actual tender values are understood;
- opening is closed;
- POS consolidation completed as expected;
- no managed submitted POS invoice remains unexpectedly unconsolidated.

### B2B sale/payment

Check:

- submitted `Sales Invoice`;
- correct due date/customer/pricing;
- `Payment Entry` reference/allocation;
- invoice `outstanding_amount` after payment;
- Accounts Receivable agrees with the document state.

### Return/refund

Check:

- return document references the original invoice;
- returned quantities do not exceed returnable quantities;
- native accounting/stock effects are present;
- if money was refunded, the corresponding Payment Entry exists.

### Purchase

Check:

- native PO/PR/PI chain is correct for the chosen workflow;
- stock receipt occurred exactly once;
- Purchase Invoice is the AP authority;
- supplier Payment Entry is allocated correctly.

### Inventory movement

Check:

- submitted native Stock Entry/Reconciliation;
- correct source/target warehouse;
- batch/serial data where required;
- resulting Stock Ledger/Bin quantity.

---

## 10. Implementation map

Current compatibility/service boundaries:

```text
apps/ledgix_saas/services/erpnext_pos.py
apps/ledgix_saas/services/erpnext_selling.py
apps/ledgix_saas/services/erpnext_buying_inventory.py
```

Related architecture/operations documentation:

```text
docs/architecture/CURRENT_ARCHITECTURE.md
docs/architecture/LEGACY_AUDIT.md
docs/operations/LOCAL_DEMO_DATA.md
docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
```

When implementation and documentation disagree, inspect the current `main` source and correct the documentation. Do not preserve an old workflow merely because it appears in an archived migration plan.
