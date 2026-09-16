# Phase 6 — ERPNext Selling, Payments and Returns Cutover

**Branch:** `main`  
**Integration site:** `ledgix-erpnext.local`  
**Framework baseline:** Frappe 15.113.4 / ERPNext 15.121.3  
**Status:** COMPLETE — closed 2026-09-16  
**Final static-proof HEAD:** `3df4634dc4dc05d13231ead7427af353a799a71d`

## Goal

Move the new **B2B / invoice selling path** from Ledgix financial DocTypes to native ERPNext transaction authority while preserving current Ledgix UI/API compatibility.

Retail POS financial cutover remains Phase 8. FBR network submission/source cutover remains Phase 9.

## Authority after Phase 6

| Concern | Authority |
| --- | --- |
| B2B invoice | ERPNext `Sales Invoice` |
| B2B pricing | ERPNext `Price List` / `Item Price` / Pricing Rule |
| invoice totals / tax / GL | ERPNext |
| customer payment | ERPNext `Payment Entry` |
| payment allocation | ERPNext Payment Entry references |
| customer receivables / credit | ERPNext Sales Invoice + Payment Entry |
| return / credit note | ERPNext return `Sales Invoice` |
| customer refund | ERPNext `Payment Entry` with Payment Type `Pay` |
| exchange | native Credit Note + replacement Sales Invoice |
| FBR tax/legal snapshot | Ledgix extension fields on ERPNext transaction lines |
| FBR network submission | unchanged; Phase 9 |
| Retail POS backend | unchanged; Phase 8 |

## Canonical service

`ledgix_saas.services.erpnext_selling`

The adapter resolves migrated ERPNext Customer/Item/Price List/Mode of Payment identities, creates native Sales Invoice / Payment Entry / Credit Note transactions, applies the proven FBR/tax snapshot adapter and reads receivables from ERPNext state.

It does not create `Ledgix Sale`, `Ledgix Payment` or another custom financial ledger.

## Idempotency and recovery

Native transaction metadata includes Ledgix client sale/payment/return IDs, exchange reference, checkout source and immutable authorized manual price-override audit metadata.

B2B checkout tenders use deterministic IDs:

```text
<client_sale_id>:PAY:1
<client_sale_id>:PAY:2
...
```

An interrupted retry reuses existing native Payment Entries and creates only missing tenders.

## Payment policy

Ledgix-originated native Payment Entries enforce migrated Mode-of-Payment policy server-side:

- reference number when required;
- configured Company Mode-of-Payment account;
- paid-from/paid-to account consistency;
- unrelated ERPNext Payment Entries retain standard behavior.

## Returns / refunds / exchanges

Returns use ERPNext's native Sales Invoice return mapper and exact `sales_invoice_item` source-row link. Client-supplied return rates are ignored; the original submitted ERPNext line rate remains authoritative.

Refunds use native Payment Entry type `Pay` against the negative Credit Note. Exchanges are a Credit Note plus replacement Sales Invoice sharing one Ledgix exchange reference.

## Receivables preflight

`erpnext_phase6_receivables_preflight.run` compares mapped legacy customer net receivables with ERPNext net receivables. Any mismatch is a blocker; no fake opening invoice is silently invented.

## Final evidence

The guarded closure gate passed on `ledgix-erpnext.local` on 2026-09-16.

Runtime closure proved:

- Phase 2–5 regressions green;
- receivables preflight green;
- **17/17** Phase 6 transaction cases green;
- pricing/payment-policy proof green;
- no parallel Ledgix Sale/Payment/Return financial writes;
- retail POS explicitly deferred to Phase 8;
- FBR datasource/network cutover explicitly deferred to Phase 9.

The return-rate regression submitted a malicious client rate of `1.23` against a source line rate of `1000.00`; the ERPNext Credit Note preserved `1000.00` and the correct full-return total.

After fixing the Frappe-site test-disable false-green condition, the final fail-closed static contract ran **14 tests** and returned `OK` at HEAD `3df4634dc4dc05d13231ead7427af353a799a71d`.

## Exit criterion — SATISFIED

New B2B sales, customer payments, receivables and returns use ERPNext financial authority without parallel Ledgix financial writes. Phase 7 — Buying and Inventory Cutover — is the next migration phase.
