# Ledgix FBR Architecture and Operations

## Purpose

This document describes the **current post-migration tax/FBR architecture**. It is operational documentation, not a migration plan.

The governing rule is simple:

> **ERPNext owns the commercial transaction. Ledgix owns the tax/FBR mapping, immutable compliance snapshot, transport controls, audit trail and product UX around that transaction.**

Ledgix must never create a second sale/accounting/stock ledger merely to satisfy FBR integration.

---

## 1. Transaction authority

### ERPNext is authoritative for

- `Sales Invoice`
- `POS Invoice`
- Sales Invoice returns / credit notes
- POS Invoice returns
- item quantities, rates, discounts and invoice totals
- stock effects and Stock Ledger Entries
- customer receivables
- payments / Payment Entries
- POS opening/closing and ERPNext POS consolidation

### Ledgix is authoritative for

- seller tax/FBR configuration
- item-to-FBR tax/classification mapping
- immutable per-line and header FBR snapshots captured on the ERPNext invoice
- payload construction
- readiness validation
- Sandbox validation transport
- Sandbox POST transport
- Production validation transport
- protected Production POST transport
- `Ledgix FBR Submission Log`
- invoice FBR status/reference/QR metadata
- reconciliation-required safeguards
- correction/reconciliation UX
- Tax & FBR Center
- readiness and go-live gates

### Explicit non-authority

Legacy `Ledgix Sale`, `Ledgix Sales Return`, `Ledgix Payment`, custom stock ledgers and similar retired business DocTypes are **not** FBR transaction sources for new activity.

A consolidated ERPNext Sales Invoice produced by POS Closing is an **accounting consolidation document**, not a second FBR source. The submitted source POS Invoices remain the FBR sources. `fbr_native.is_native_fbr_source()` explicitly excludes the consolidated Sales Invoice path.

---

## 2. Main components

| Layer | Current responsibility |
|---|---|
| ERPNext `Item` | Product authority |
| `Ledgix Item Tax Profile` | FBR classification mapped by `erpnext_item` |
| `Ledgix Tax Category` / `Ledgix Tax Rate` / Tax Profile | Ledgix tax policy/configuration |
| ERPNext invoice rows | Commercial line authority plus immutable Ledgix FBR snapshot fields |
| `erpnext_tax_foundation.py` | Converts Ledgix tax policy to ERPNext-owned tax rows/totals and writes snapshots |
| `fbr_native.py` | ERPNext-native readiness, payload, validation/submission and status orchestration |
| `fbr_payload.py` | FBR payload field mapping and legal-field validation |
| `fbr_client.py` | Controlled HTTP transport and endpoint/mode gates |
| `Ledgix FBR Settings` | Mode, tokens, seller identity, arming and safety state |
| `Ledgix FBR Submission Log` | Durable request/response/status audit trail |
| ERPNext invoice custom FBR fields | Official FBR number/reference/QR/status/reconciliation state |
| `ledgix-tax-center` | Operator/manager/admin compliance UX |

---

## 3. Normal invoice flow

```text
ERPNext Item / Customer / Ledgix tax mapping
                |
                v
Sales Invoice or POS Invoice
                |
                v
ERPNext computes commercial totals and accounting tax rows
                |
                v
Ledgix writes immutable FBR header + line snapshots
                |
                v
ERPNext invoice is submitted
                |
                v
FBR readiness validation
                |
                +---- Disabled / Paused / Manual Only --> no network POST
                |
                +---- Sandbox --------------------------> validate / optional POST
                |
                +---- Production -----------------------> validate / protected POST
                |
                v
Ledgix FBR Submission Log
                |
                v
Official FBR invoice/reference + QR/status stored on the SAME ERPNext invoice
                |
                v
Print/QR reads that authoritative ERPNext invoice
```

### Immutable snapshot rule

FBR payloads are **not reconstructed later from whatever tax settings happen to exist at that time**. Each submitted ERPNext invoice row carries a versioned immutable Ledgix FBR snapshot. `fbr_native` refuses payload generation when the required snapshot is missing/invalid.

This protects historical invoices from later configuration changes.

---

## 4. Return / Credit Note flow

The return authority is still ERPNext:

- POS return -> ERPNext `POS Invoice` with `is_return = 1` and `return_against`
- B2B return -> ERPNext `Sales Invoice` credit note with `is_return = 1` and `return_against`

For FBR:

1. The return must reference a real original submitted ERPNext invoice.
2. FBR readiness resolves the original invoice through `return_against`.
3. In Sandbox/Production the original must already have an official FBR invoice number before the credit note can be submitted.
4. The outgoing credit-note payload uses the original official FBR reference as `invoiceRefNo`.
5. A return reason is required.
6. The return date cannot precede the original invoice date; current validation also enforces the configured FBR age rule used by the implementation.
7. The credit note receives its own submission log/status/reference on the ERPNext return document.

The original and the credit note therefore remain linked in both ERPNext and the FBR compliance layer.

---

## 5. FBR operating modes

`Ledgix FBR Settings.mode` supports:

### Disabled

- No FBR network submission is allowed.
- Appropriate for local development/demo data and sites that are not yet configured.
- The ERPNext sale remains a valid ERPNext transaction.

### Sandbox

- Requires FBR Settings enabled and a configured **Sandbox token**.
- Validation can call the Sandbox validation endpoint.
- POST can call the Sandbox POST endpoint only when the configured workflow permits it.
- `sandbox_post_on_submit` is a separate explicit control for on-submit Sandbox POST behavior.

### Production

- Requires FBR Settings enabled and a configured **Production token**.
- Production validation is available for controlled checks.
- Production POST requires the additional `production_post_armed` interlock.
- Arming Production is a deliberate admin/System Manager go-live action, not an installation default.

### Paused

- Network submission is not permitted while paused.
- Pause metadata records the reason, time and user where supported by the control workflow.
- Use this state when FBR submission must be deliberately stopped without dismantling configuration.

### Manual Only

- Automatic network submission is not permitted by the transport mode gate.
- It is useful when operators need to prepare/review data without automatic transport.

---

## 6. Submit triggers

`submit_trigger` supports:

- `Manual`
- `On Submit`
- `Validate Only`

The trigger does not bypass mode/token/readiness/arming gates. It controls *when* the allowed FBR action is considered, not whether an unsafe request is allowed.

On-submit integration is attached to ERPNext `Sales Invoice` and `POS Invoice` hooks. The Production network action is performed after commit where configured so a remote transport failure does not invent or roll back a second business ledger.

---

## 7. Production safety model

### Production arming

Production POST is rejected unless all of the following are true:

- mode is `Production`;
- FBR is enabled;
- a Production token is configured;
- `production_post_armed = 1`;
- the ERPNext source invoice passes Ledgix/FBR readiness;
- the document is a supported native FBR source.

### Token storage

Sandbox and Production tokens are `Password` fields on `Ledgix FBR Settings`.

Operational rules:

- never print tokens in logs or docs;
- never return raw token values to browser APIs;
- never copy tokens into demo fixtures;
- never commit tokens to Git;
- error sanitization must redact bearer credentials.

### Ambiguous Production POST

A Production POST can fail in a way where Ledgix cannot prove whether FBR received the request (for example, a network error after request transmission).

In that case Ledgix uses:

```text
Reconciliation Required
```

The invoice is marked accordingly and automatic retransmission is intentionally blocked.

The operator must reconcile the invoice with FBR/PRAL before any retransmission. The implementation requires an explicit reconciliation confirmation workflow rather than guessing that a failed HTTP response means FBR never accepted the invoice.

### Why automatic retry is restricted

Blind retry of an ambiguous Production POST can create duplicate/legal ambiguity. For this reason `retry_enabled` is currently reserved/hidden and Production retransmission is deliberately reconciliation-safe rather than automatic.

---

## 8. Submission log and invoice state

Every real validation/submission attempt that reaches the relevant operation path is represented through Ledgix FBR status/logging controls.

ERPNext source invoices carry Ledgix custom fields for values such as:

- FBR status
- official FBR invoice number
- FBR reference
- QR code
- submitted timestamp
- error code/message
- submission log link
- reconciliation-required flag

The `Ledgix FBR Submission Log` stores the compliance attempt/audit record. It must not be treated as a replacement Sales Invoice.

Once an official FBR invoice number exists, a repeated submit request is treated as already submitted rather than creating a second network submission.

---

## 9. Seller and buyer identity

### Seller

Seller identity comes from configured Ledgix tax/FBR settings/profile data used by `fbr_payload` and `fbr_native`.

Do not seed or guess:

- NTN/CNIC
- legal seller business name
- registered province/address
- software registration number
- Production token

Those are client/legal configuration inputs.

### Buyer

Buyer tax identity is resolved from ERPNext `Customer` and Ledgix ERPNext Customer extension fields. Walk-in retail remains a valid ERPNext Customer pattern, but Production validation must use the legally correct buyer data required for the scenario.

---

## 10. Item tax mapping

The ERPNext Item is the product authority. New mappings use:

```text
Ledgix Item Tax Profile.erpnext_item -> ERPNext Item
```

The older `item -> Ledgix Item` field is transition/history compatibility only.

An item tax mapping can carry, where applicable:

- tax category
- taxable/zero/exempt classification
- transaction-value vs notified-retail-price basis
- HS code
- FBR UOM
- sale type
- FBR rate description
- Sandbox scenario ID
- SRO references
- extra/further/FED/withholding components

The mapping affects the Ledgix FBR snapshot and ERPNext tax adapter. It does not make Ledgix Item the master again.

---

## 11. ERPNext accounting relationship

`erpnext_tax_foundation.py` builds a tax plan from the Ledgix mapping/snapshot and writes **ERPNext Sales/POS invoice tax rows** using configured Company tax accounts.

ERPNext therefore remains authoritative for:

- net total
- tax rows
- grand total
- GL impact
- customer receivable

Ledgix snapshot totals are validated against the ERPNext invoice totals. A mismatch is a readiness error, not something Ledgix silently overwrites after submission.

---

## 12. POS consolidation rule

ERPNext may generate a consolidated `Sales Invoice` during `POS Closing Entry`.

That consolidated document:

- is accounting consolidation;
- is **not** a second FBR source;
- must not generate another FBR legal invoice for the same underlying POS sales.

`fbr_native._is_consolidated_pos_sales_invoice()` enforces this distinction.

---

## 13. Sandbox certification evidence

A valid Sandbox proof package should be based on real FBR network responses and should include, at minimum:

- configured Sandbox token (kept secret; do not paste it into the evidence package);
- legally correct seller identity;
- required Item/FBR scenario mappings;
- successful readiness output;
- real Sandbox validation response(s);
- real Sandbox POST response(s) where required;
- return/Credit Note scenario proof where required;
- persisted `Ledgix FBR Submission Log` records;
- corresponding ERPNext invoice/return status fields;
- QR/reference rendering checks;
- no Production posting.

A local/mock payload, a fabricated response or a manually typed FBR number is **not certification evidence**.

---

## 14. Production-switch readiness

Production should remain unarmed until all applicable gates are complete:

1. ERPNext invoice/return workflows pass client UAT.
2. Tax account mapping is complete.
3. Item classifications are reviewed.
4. Seller identity is confirmed by the client.
5. Real Sandbox certification/proof is accepted.
6. Production token is installed securely.
7. Production validation is checked where appropriate.
8. Backup/recovery and operational ownership are confirmed.
9. Operators understand `Reconciliation Required` handling.
10. A Ledgix Admin/System Manager explicitly arms Production POST.

Do not switch to Production merely because application tests pass.

---

## 15. Current project state

As of the final pre-client-testing cleanup:

- ERPNext-native Sales Invoice/POS Invoice FBR integration is implemented.
- Immutable tax/FBR snapshots are implemented.
- Sandbox/Production validation and POST transport code is implemented.
- FBR Submission Log, reconciliation-required handling, print/QR metadata and readiness tooling are implemented.
- Production arming protection is implemented.
- Software/setup/static/runtime infrastructure is at the code-complete release-hardening stage.
- **The required real FBR token is currently unavailable for this project session.**
- Therefore **real Sandbox network certification is still pending**.
- No fake Sandbox certification, fake official FBR invoice number, fake token or fabricated network-success evidence is to be created.

This distinction must remain visible in handoffs and release documentation.

---

## 16. Local demo-data rule

`scripts/prepare_local_demo.sh` and `ledgix_saas.setup.demo_data` deliberately force FBR transport to `Disabled` before generating local demo transactions.

The demo may populate tax/classification fields for UI/workflow testing, but it must not create:

- Sandbox/Production transport success records;
- official FBR invoice numbers;
- fake FBR responses;
- fake legal seller identity;
- a Production token.

---

## 17. Useful source map

```text
apps/ledgix_saas/api/fbr_native.py
apps/ledgix_saas/api/fbr_client.py
apps/ledgix_saas/api/fbr_payload.py
apps/ledgix_saas/api/fbr_settings.py
apps/ledgix_saas/api/fbr_submission.py
apps/ledgix_saas/setup/erpnext_tax_foundation.py
apps/ledgix_saas/setup/erpnext_phase9_extensions.py
apps/ledgix_saas/ledgix/doctype/ledgix_fbr_settings/
apps/ledgix_saas/ledgix/doctype/ledgix_fbr_submission_log/
apps/ledgix_saas/ledgix/page/ledgix_tax_center/
```

For historical cutover rationale, use `docs/archive/migration/`. For current production switching, use `docs/fbr/FBR_PRODUCTION_CHECKLIST.md` together with this document.
