# Ledgix FBR Architecture and Operations

**Status:** CURRENT - 2026-09-24
**ERPNext monetary tax authority:** LOCAL CUTOVER COMPLETE
**FBR Production:** NOT YET PRODUCTION-READY

## Purpose

This is the current post-migration FBR/tax architecture.

> **ERPNext owns the commercial transaction. Ledgix owns FBR/tax mapping, immutable compliance snapshots, guarded transport, audit state and product UX around that transaction.**

Ledgix must not create a second sales, accounting, payment or stock ledger to satisfy FBR integration.

---

## 1. Authority model

### ERPNext owns

- `Sales Invoice`
- `POS Invoice`
- native Sales Invoice returns / Credit Notes
- native POS Invoice returns
- Item, Customer, pricing and invoice totals
- stock effects and Stock Ledger Entries
- receivables and Payment Entries
- POS Opening/Closing and POS consolidation

### Ledgix owns

- seller FBR configuration;
- item-to-FBR classification mapping;
- immutable per-invoice and per-line FBR snapshots;
- payload construction and readiness validation;
- Sandbox and protected Production transport;
- `Ledgix FBR Submission Log`;
- invoice FBR status/reference/QR metadata;
- reconciliation-required safeguards;
- Tax & FBR Center UX;
- activation/readiness evidence checks.

### Explicit non-authority

Frozen legacy records such as `Ledgix Sale`, `Ledgix Sales Return`, `Ledgix Payment` and custom stock ledgers are **not** current FBR transaction sources.

An ERPNext Sales Invoice created by POS Closing is an accounting consolidation document. The underlying submitted POS Invoices remain the legal FBR sources; the consolidation invoice must not be submitted as a second FBR invoice.

---

## 2. Current components

| Component | Responsibility |
|---|---|
| ERPNext `Item`, `Customer`, `Company`, `Address` | Commercial/master identity authority |
| ERPNext Tax Category / Tax Rule / Sales Taxes and Charges Template / Item Tax Template | Financial tax configuration |
| `erpnext_tax_authority.py` | Active transaction tax-authority boundary; delegates monetary calculation to ERPNext |
| `erpnext_taxable_base.py` | Supplies approved special taxable-base inputs such as notified retail value without calculating tax itself |
| ERPNext Sales Invoice / POS Invoice rows and tax rows | Authoritative commercial/tax values |
| `erpnext_fbr_snapshot.py` | Captures/reconciles immutable FBR evidence from authoritative ERPNext values |
| `Ledgix FBR Item Mapping` and V2 compliance records | FBR legal classification/mapping only |
| `fbr_native.py` | Native ERPNext-invoice readiness, payload orchestration, guarded validation/submission and FBR state |
| `fbr_payload.py` | Shared FBR formatting/validation helpers plus retained legacy code; legacy exposed execution is fail-closed |
| `fbr_submission.py` | Shared response/log/locking helpers plus retained legacy execution code; old exposed Sale/Return actions are fail-closed |
| `fbr_client.py` | Guarded HTTP transport and endpoint/mode checks |
| `fbr_activation.py` | Read-only Sandbox/Production readiness evidence evaluation |
| `Ledgix FBR Submission Log` | Durable compliance attempt/audit record |
| ERPNext invoice custom fields | FBR status/reference/QR/error/reconciliation state |
| Tax & FBR Center | ERPNext-native tax setup + FBR V2 operator/readiness UX |

`erpnext_tax_foundation.py` and old Ledgix monetary tax masters may still exist physically for historical/setup/migration compatibility. They are not the active new-business transaction tax authority.

## 3. Native invoice flow

```text
ERPNext Item / Customer + Ledgix FBR mapping
        -> Sales Invoice or POS Invoice
        -> ERPNext commercial/tax totals
        -> immutable Ledgix FBR snapshots
        -> ERPNext submit
        -> FBR readiness checks
        -> allowed validate / POST operation
        -> Ledgix FBR Submission Log
        -> official status/reference/QR on the SAME ERPNext invoice
```

FBR payloads are not reconstructed later from whichever configuration happens to be current. Submitted invoices retain versioned snapshot data so later tax/configuration changes do not silently rewrite historical legal payloads.

A missing or invalid required snapshot is a readiness failure.

---

## 4. Returns and Credit Notes

Return authority remains ERPNext:

- Retail return: return `POS Invoice` with `is_return = 1` and `return_against`.
- B2B return: return `Sales Invoice` / Credit Note with `is_return = 1` and `return_against`.

For FBR, the return must resolve a real submitted original transaction. Where the FBR scenario requires it, the original official FBR number becomes the credit-note reference. The return carries its own compliance snapshot, submission log and FBR result state.

Do not recalculate a historical return from a retired `Ledgix Sale` or use a manually entered fake original FBR reference.

---

## 5. Operating modes

### Disabled

No FBR network posting. This is the required state for the completed local operating/acceptance dataset.

### Sandbox

Requires enabled FBR configuration and a real Sandbox token. Validation and POST are permitted only through the configured guarded workflow.

### Production

Requires enabled FBR configuration, a real Production token and the separate Production POST interlock. Production activation is never an installation default.

### Paused

Transport is deliberately stopped while preserving configuration and audit state.

### Manual Only

Automatic transport is not permitted; operators can prepare/review data through the supported manual workflow.

`submit_trigger` controls when an allowed action is considered. It never bypasses mode, token, readiness, reconciliation or Production-arming rules.

---

## 6. Production safety model

Production POST requires the supported native source invoice to pass all configured safety gates, including:

- FBR enabled;
- mode `Production`;
- Production token configured;
- `production_post_armed = 1`;
- invoice readiness successful;
- no unsupported/consolidation source path.

### Token handling

Sandbox and Production tokens are secret settings. Never:

- print token values in logs;
- return raw tokens to browser APIs;
- store tokens in fixtures/demo data;
- paste tokens into documentation/evidence;
- commit tokens to Git.

---

## 7. Ambiguous Production response: fail closed

If a Production request may have reached FBR but Ledgix cannot prove the outcome, the invoice becomes:

```text
Reconciliation Required
```

This is intentionally different from a known rejection.

Current `apps/ledgix_saas/hooks.py` defines:

```python
scheduler_events = {}
```

There is no blind retry/offline upload scheduler. A timeout or dropped response must **not** be interpreted as proof that FBR did not accept the invoice.

The operator must reconcile externally with FBR/PRAL and use the explicit supported reconciliation workflow before any retransmission decision.

---

## 8. Submission log vs financial record

`Ledgix FBR Submission Log` records compliance attempts, request/response state and audit evidence. It is not a Sales Invoice or accounting ledger.

The authoritative ERPNext source invoice retains current FBR fields such as:

- FBR status;
- official FBR number/reference;
- QR data;
- submitted timestamp;
- safe error state;
- submission-log link;
- reconciliation-required state.

Once a supported invoice has an official accepted FBR identity, repeated submission must not create a second legal invoice.

---

## 9. Seller, buyer and item data

### Seller

Seller identity is client/legal configuration. Do not seed or invent legal values such as:

- NTN/CNIC;
- legal business name;
- registered province/address;
- registration/software identifiers;
- Production token.

### Buyer

Buyer commercial identity comes from ERPNext `Customer` plus current Ledgix ERPNext extensions where required by the FBR payload.

### Item

ERPNext `Item` is product authority. Current FBR mapping uses the ERPNext-linked item mapping, not historical `Ledgix Item` as a new-business master.

Mappings may include HS code, FBR UOM, sale type, tax classification/rate basis, scenario identifiers and SRO fields where applicable.

---

## 10. Accounting relationship

ERPNext is the sole current monetary calculator and accounting authority.

The active Ledgix boundary may provide approved legal taxable-base inputs where ERPNext exposes a supported extension hook, but Ledgix does not calculate a competing invoice tax result.

ERPNext remains authoritative for:

- net total;
- native tax rows;
- grand total;
- GL impact;
- customer receivable;
- Payment Entry;
- stock/accounting effects;
- POS Closing consolidation.

Ledgix FBR snapshots must reconcile to those authoritative values. A mismatch is a readiness failure; it must never be "fixed" by rewriting submitted accounting.

Special local Phase-1 gates prove Third Schedule/notified retail, Extra Tax, Further Tax, FED and Sales Tax Withheld FBR evidence without restoring a second monetary engine.

Sales Tax Withheld buyer net-payment settlement accounting remains a separate unresolved accounting workflow and must not be inferred from the invoice-evidence gate.

## 11. Sandbox evidence

Real Sandbox proof must come from real network interactions and persisted evidence.

Depending on client profile, retain successful validation/POST evidence for:

- ERPNext `Sales Invoice`;
- ERPNext `POS Invoice` when POS is enabled;
- native return/Credit Note when required by the acceptance scope.

A mock payload, fabricated response, locally typed FBR number or fake token is not certification evidence.

Detailed go-live requirements are in `docs/fbr/FBR_PRODUCTION_CHECKLIST.md`.

---

## 12. Read-only activation evaluator

`apps/ledgix_saas/api/fbr_activation.py` is intentionally separated from transport.

It:

- does not read raw token values;
- does not send a network request;
- does not arm Production;
- evaluates client readiness, Sandbox proof, backup evidence, release identity and unresolved reconciliation state.

Key result concepts are:

- `sandbox_ready` — prerequisites to exercise Sandbox;
- `sandbox_proven` — required persisted real Sandbox network proof exists;
- `production_switch_ready` — Sandbox proof plus strict release/backup/Production prerequisites are green.

Even `production_switch_ready=true` is only a readiness result. The Production switch remains a separate explicit action.

---

## 13. Local operating dataset

The completed local acceptance dataset `LEDGIX-RETAIL-OPERATING-V1` deliberately keeps FBR transport disabled.

It may contain classification/configuration data needed to exercise UI and readiness logic, but it must not contain fabricated:

- Sandbox/Production success logs;
- official FBR invoice numbers;
- network responses;
- seller legal identity;
- Production credentials.

Do not casually rebuild/reset the dataset. See `docs/operations/LOCAL_DEMO_DATA.md`.

---

## 14. Current project state

As of 2026-09-24:

| Area | State |
|---|---|
| ERPNext-native monetary tax authority | **LOCAL CUTOVER COMPLETE** |
| Core Sales/POS/return parity | **PROVEN LOCALLY** |
| Third Schedule / Extra Tax / Further Tax / FED parity | **PROVEN LOCALLY** |
| Sales Tax Withheld invoice/FBR evidence treatment | **PROVEN LOCALLY; PAYMENT SETTLEMENT UNRESOLVED** |
| POS Closing accounting consolidation parity | **PROVEN LOCALLY** |
| Legacy Ledgix Sale/Return FBR execution | **FAIL-CLOSED / RETIRED AS CURRENT SOURCE** |
| Immutable native FBR snapshot foundation | IMPLEMENTED / exercised by local gates |
| FBR V2 model/reference/readiness foundations | IMPLEMENTED IN PART; FINAL CONSOLIDATION PENDING |
| Real client Sandbox credential/evidence | EXTERNAL / PENDING |
| Real Sandbox certification | **NOT YET COMPLETE** |
| Production activation | **NOT YET PRODUCTION-READY** |

Local accounting/parity evidence must not be represented as real FBR certification.

## 15. Current source map

```text
apps/ledgix_saas/services/erpnext_tax_authority.py
apps/ledgix_saas/services/erpnext_taxable_base.py
apps/ledgix_saas/services/erpnext_fbr_snapshot.py
apps/ledgix_saas/services/erpnext_selling.py
apps/ledgix_saas/services/erpnext_pos.py

apps/ledgix_saas/api/fbr_native.py
apps/ledgix_saas/api/fbr_native_ui.py
apps/ledgix_saas/api/fbr_client.py
apps/ledgix_saas/api/fbr_payload.py
apps/ledgix_saas/api/fbr_submission.py
apps/ledgix_saas/api/fbr_legacy_guard.py
apps/ledgix_saas/services/fbr_v2_readiness.py

apps/ledgix_saas/hooks.py
```

Important classification:

- `erpnext_tax_authority.py` / `erpnext_taxable_base.py` / ERPNext documents are current monetary runtime.
- `erpnext_fbr_snapshot.py` and `fbr_native.py` are current native FBR foundations.
- `fbr_payload.py` and `fbr_submission.py` are mixed compatibility modules: native code still consumes shared non-monetary helpers, while legacy exposed Sale/Return execution is isolated fail-closed.
- `erpnext_tax_foundation.py`, `api/taxation.py`, `services/tax.py` and old Ledgix tax/sale modules are not current monetary authority; retain/remove them only according to proven migration/history/dependency needs.

Historical migration rationale lives under `docs/archive/migration/`.
