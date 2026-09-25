# Ledgix FBR Architecture and Operations

**Status:** CURRENT — 2026-09-25
**Software status:** READY FOR CLIENT CERTIFICATION
**ERPNext monetary tax authority:** LOCAL CUTOVER COMPLETE
**FBR Production:** NOT YET PRODUCTION-READY

## Purpose

ERPNext owns the commercial/accounting transaction. Ledgix owns FBR classification, immutable compliance evidence, guarded transport, reconciliation, Known Offline and operator workflows around the same ERPNext invoice.

## 1. Authority model

ERPNext owns Items, Customers, Company/Address, pricing, Sales/POS Invoice, native returns, native tax rows/totals, GL/payment/stock and POS closing.

Ledgix owns Company-scoped FBR profile, official reference cache, Item->FBR classification, immutable snapshots, guarded transport, Submission Log, Known Offline, reconciliation safeguards, correction tracking, print-compliance metadata and activation/readiness UX.

## 2. Native flow

```text
ERPNext native transaction/tax
 -> immutable FBR V2 snapshot
 -> readiness
 -> guarded allowed operation
 -> Submission Log
 -> official FBR metadata on the SAME ERPNext invoice
```

## 3. Returns / note protocol

ERPNext return documents remain authoritative and must reference the real original invoice. Ledgix preserves the original accepted FBR reference, but outbound Debit/Credit Note semantics remain fail-closed until real Sandbox/provider proof. Print remains neutral `RETURN / ADJUSTMENT`.

## 4. Operating modes

Disabled, Sandbox, Production and Paused remain profile modes. `Manual` trigger never bypasses token, readiness, reconciliation or Production-arming rules.

## 5. Production safety

Production cannot be armed by install/migrate/restore. Tokens remain secret Password fields. Current global V2 Production cutover remains fail-closed until the approved activation phase.

## 6. Known Offline vs ambiguous POST

Known Offline is explicit and valid only before any Production POST attempt:

```text
declare -> Offline Pending -> due evidence -> controlled upload -> terminal result
```

There is no automatic uploader.

Ambiguous POST is always `Reconciliation Required`; never reclassify it as Known Offline.

## 7. Print compliance

Print uses ERPNext seller identity, configured software/POS registration, accepted FBR number/QR and the client/provider-supplied authoritative DI-logo attachment. Ledgix ships no fabricated DI artwork. Final QR physical presentation remains certification evidence.

## 8. Correction workflow

New correction timing uses official FBR generation time. The 72-hour Board path and Commissioner-after-window path remain tracked; completion requires external evidence.

## 9. Data authority

Seller = ERPNext Company + linked/default Address. Buyer = ERPNext Customer/Address. Item = ERPNext Item + FBR classification mapping. Submission Log is audit evidence, not accounting.

## 10. Activation readiness

Readiness distinguishes Sandbox configuration, real Sandbox proof and Production-switch prerequisites. Production readiness additionally blocks missing authoritative DI-logo configuration, missing strict release/backup evidence and unresolved reconciliation.

## 11. Current state

Target software label after final handoff closure: **READY FOR CLIENT CERTIFICATION**.
Sandbox Certified: **NO**.
Production Ready: **NO**.

External blockers: seller legal values, onboarding data, official reference/mapping review, credentials, real Sandbox proof, return/note confirmation, provider Known Offline rule/window, authoritative DI logo/final print confirmation, backup/release approval and explicit Production activation.
