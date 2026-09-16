# Phase 6 — ERPNext Selling, Payments and Returns Cutover

**Branch:** `main`  
**Integration site:** `ledgix-erpnext.local`  
**Framework baseline:** Frappe 15.113.4 / ERPNext 15.121.3

## Goal

Move the new **B2B / invoice selling path** from Ledgix financial DocTypes to native ERPNext transaction authority while preserving the current Ledgix UI contracts.

Phase 6 does not redesign the retail POS screen. Retail POS financial cutover remains Phase 8. FBR network submission/source cutover remains Phase 9.

## Authority after Phase 6

| Concern | Authority |
| --- | --- |
| B2B invoice | ERPNext `Sales Invoice` |
| B2B pricing | ERPNext `Price List` / `Item Price` / Pricing Rule |
| invoice totals / tax / GL | ERPNext |
| customer payment | ERPNext `Payment Entry` |
| payment allocation | ERPNext Payment Entry references |
| customer receivables / credit view | ERPNext Sales Invoice + Payment Entry state |
| return / credit note | ERPNext return `Sales Invoice` |
| customer refund | ERPNext `Payment Entry` with Payment Type `Pay` |
| exchange | native Credit Note + replacement Sales Invoice |
| FBR tax/legal snapshot | Ledgix extension fields on ERPNext transaction lines |
| FBR network submission | unchanged; Phase 9 |
| Retail POS backend | unchanged; Phase 8 |

## Canonical service boundary

`ledgix_saas.services.erpnext_selling` owns the product adapter around ERPNext selling transactions.

It does not create `Ledgix Sale`, `Ledgix Payment` or another custom financial ledger.

Responsibilities:

- resolve migrated Customer / Item / Price List / Mode of Payment identities;
- use native ERPNext price resolution;
- create and submit Sales Invoice;
- apply the proven Ledgix FBR/tax snapshot adapter before submit;
- create Payment Entry allocations;
- read receivables from submitted ERPNext transactions;
- create native Credit Notes through ERPNext's return mapper;
- create customer refund Payment Entries;
- cancel Payment Entries using native cancellation;
- create exchange pairs as a Credit Note + replacement Sales Invoice.

## Idempotency

Ledgix client identifiers remain product metadata, not a second transaction ledger.

Native transaction fields:

### Sales Invoice

- `custom_ledgix_sale_channel`
- existing `custom_ledgix_client_sale_id`
- `custom_ledgix_client_return_id`
- `custom_ledgix_exchange_reference`
- `custom_ledgix_checkout_source`

### Payment Entry

- `custom_ledgix_client_payment_id`
- `custom_ledgix_payment_source`
- `custom_ledgix_reversal_reason`

The service locks the Company row inside the current database transaction before checking client IDs. Repeated active client IDs return the same native ERPNext transaction rather than creating a parallel Ledgix idempotency table.

## Existing UI / API compatibility

The user-facing POS rewrite is intentionally not mixed into Phase 6.

Existing RPC paths stay valid through `override_whitelisted_methods`:

- existing B2B checkout requests route to the ERPNext selling adapter;
- existing B2B customer-credit calls read ERPNext receivables;
- native Sales Invoice return requests route to ERPNext Credit Notes;
- **Retail** calls delegate to the existing retail backend until Phase 8.

The old module names are compatibility boundaries only. They are not financial authorities.

## Payment behavior

### Fully paid

Sales Invoice + submitted Payment Entry -> invoice outstanding becomes zero.

### Partial payment

Payment Entry allocates only the paid amount -> remaining Sales Invoice outstanding stays native.

### Multiple invoices

One Payment Entry may contain multiple Sales Invoice reference rows.

### Payment cancellation

The original Payment Entry is cancelled with a preserved Ledgix cancellation/reversal reason. ERPNext restores invoice outstanding from its own ledger entries.

Phase 6 does not create a second custom reversal-payment document.

## Returns and refunds

Returns use ERPNext's native `make_return_doc("Sales Invoice", source)` flow.

The pinned ERPNext v15 `Sales Invoice Item` return link is `sales_invoice_item`; Phase 6 uses that field to map exact source rows.

A Credit Note carries negative quantities/totals and is linked through `return_against`.

A cash/bank refund is a native Payment Entry against the negative-outstanding Credit Note. ERPNext resolves this as Payment Type `Pay`; the Payment Entry reference allocation remains negative, matching pinned ERPNext v15 semantics.

## Exchanges

An exchange is not another financial model. It is:

```text
Original Sales Invoice
        |
        +--> ERPNext Credit Note
        |
        +--> ERPNext replacement Sales Invoice
```

Both new documents carry the same `custom_ledgix_exchange_reference` for Ledgix UX/reporting.

## Receivables / credit

`get_customer_receivables` reads submitted ERPNext Sales Invoices and Payment Entries.

It reports:

- positive invoice outstanding;
- Credit Note credit;
- unapplied customer Payment Entry credit;
- net customer balance;
- overdue amount / oldest due date;
- Customer company credit limit;
- available credit.

Legacy mutable Ledgix Customer receivable fields are not updated by the Phase 6 path.

## FBR boundary

Phase 6 reuses the already-proven immutable ERPNext invoice-line FBR snapshots from Phase 4.

It does **not**:

- send an FBR/PRAL HTTP request;
- change production FBR Submission Log authority;
- switch the real FBR datasource;
- remove the legacy FBR path.

Those changes remain Phase 9.

## Final runtime matrix

Runner:

```bash
bash scripts/run_erpnext_phase6_final_gate.sh
```

The Phase 6 gate proves:

1. B2B client-sale idempotency;
2. fully paid invoice;
3. partially paid invoice;
4. unpaid credit sale / native AR view;
5. one payment across multiple invoices;
6. payment client-ID idempotency;
7. payment cancellation / outstanding restoration;
8. full Credit Note;
9. partial Credit Note;
10. customer refund Payment Entry;
11. equal-value exchange pair;
12. compatibility B2B API routes to ERPNext;
13. receivables are ERPNext-derived;
14. non-stock Phase 6 fixtures create no Stock Ledger Entry;
15. immutable FBR snapshot remains attached;
16. no parallel Ledgix Sale/Payment/Return financial records are created;
17. retail POS cutover is explicitly not claimed.

The consolidated runner also re-runs Phase 2, 3, 4 and 5 gates before Phase 6 closes.

## Exit criterion

Phase 6 is complete only when the guarded integration-site gate proves that new B2B sales, customer payments, receivables and returns work entirely through ERPNext financial documents without creating parallel Ledgix financial writes.

After that, Phase 7 moves buying/inventory authority, including the Supplier AP/opening state intentionally deferred by Phase 5.
