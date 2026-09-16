# Phase 9 — FBR Source Cutover

**Implementation branch:** `main`  
**Integration site:** `ledgix-erpnext.local`  
**Pinned stack:** Frappe 15.113.4 / ERPNext 15.121.3

## Decision

Phase 9 changes **only the source transaction authority** for FBR.

Native source documents:

- B2B/invoice sale: ERPNext `Sales Invoice`;
- Retail POS sale: ERPNext `POS Invoice`;
- Credit Note/return: native ERPNext return invoice of the same source type.

Ledgix continues to own:

- FBR legal/tax classification inputs;
- immutable header/line FBR snapshots;
- Sandbox/Production settings and credentials;
- FBR HTTP client and response parsing;
- `Ledgix FBR Submission Log`;
- QR/reference/status/error metadata;
- reconciliation-required safeguards;
- external correction tracking.

ERPNext remains the accounting, customer, pricing, tax-total, payment and stock authority.

## Immutable payload rule

Phase 9 never reconstructs legal tax values from mutable masters after invoice submission.

Every native source line must carry `custom_ledgix_fbr_snapshot_json` written by the established ERPNext tax adapter. Payload items are generated from those snapshots and reconciled to ERPNext invoice totals before submission.

Missing/invalid snapshots fail closed.

## POS duplicate-source rule

ERPNext POS Closing creates consolidated `Sales Invoice` records for accounting.

Those consolidated invoices are **not** separate FBR source transactions. The original submitted `POS Invoice` owns FBR submission. Phase 9 explicitly excludes consolidated POS Sales Invoices to prevent duplicate official submissions.

## Legacy cutover rule

Legacy `Ledgix Sale` / `Ledgix Sales Return` records remain available for historical audit only.

The previous public production submit endpoint is overridden to a fail-closed retirement guard. New official FBR submissions must use ERPNext `Sales Invoice` or `POS Invoice`.

No legacy sale/payment/stock ledger is written by the native FBR adapter.

## Submission lifecycle

For an eligible submitted native source:

1. load immutable legal snapshots;
2. validate seller/buyer and line FBR requirements;
3. reconcile snapshot totals to native ERPNext totals;
4. build official Sale Invoice or Credit Note payload;
5. write FBR attempt audit to `Ledgix FBR Submission Log` with Dynamic Link to the native document;
6. persist only FBR metadata on the ERPNext source;
7. on a successful Production response, freeze FBR invoice/QR reference;
8. block destructive cancellation after official submission; use native return/Credit Note or correction tracking instead.

## Credit Notes

A native return:

- must reference the original submitted ERPNext invoice;
- uses the original source rate/tax snapshots;
- sends `invoiceType = Credit Note`;
- sends `invoiceRefNo` from the original document's official FBR invoice number;
- requires a reason;
- enforces the existing 180-day FBR return window check.

## Reconciliation safety

Production POST transport failures can be ambiguous. Phase 9 retains the existing fail-closed policy:

- mark `Reconciliation Required`;
- do not automatically retransmit;
- require external FBR/PRAL confirmation that the invoice was not received;
- only then release the document for a manual retry.

Scheduler retry remains disabled.

## Tax & FBR Center

The retained Ledgix Tax & FBR Center is patched to select either:

- `Sales Invoice`, or
- `POS Invoice`.

Preview, Sandbox/Production validation, Production submission and correction-request creation all use that native reference. Tax mapping/audit UI remains unchanged.

## Final gate

Runner:

`scripts/run_erpnext_phase9_final_gate.sh ledgix-erpnext.local`

The runtime gate is restricted to the integration site and uses **mocked FBR client adapters only**. It must make zero real FBR/PRAL network calls.

Required proofs:

- native Sales Invoice payload from immutable snapshots;
- native POS Invoice payload from immutable snapshots;
- native validation log references the ERPNext document;
- mocked Production submit is idempotent;
- native Credit Note references original FBR invoice;
- ambiguous Production POST enters reconciliation lock and blind retry is blocked;
- consolidated POS Sales Invoice is excluded as a second source;
- correction tracking accepts native references;
- no legacy business ledger or legacy FBR-source log is created.

Phase 9 closes only when `phase9_complete=true`, `phase10_ready=true`, every case passes, and `real_fbr_network_calls=0`.

## Next

Phase 10 — Final Print Redesign.
