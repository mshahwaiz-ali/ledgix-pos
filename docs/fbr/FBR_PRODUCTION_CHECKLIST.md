# Ledgix FBR Sandbox and Production Checklist

**Status:** CURRENT — 2026-09-25
**Software status:** READY FOR CLIENT CERTIFICATION
**Sandbox certification:** PENDING REAL CLIENT EVIDENCE
**Production readiness:** NOT YET PRODUCTION-READY
**Current transaction sources:** ERPNext `Sales Invoice` / `POS Invoice`

## 1. Safety rule

Production is a separate compliance/go-live decision. Local tests and migrate do not authorize live posting.

- `scheduler_events = {}`;
- no blind Production retry/offline scheduler;
- ambiguous POST -> `Reconciliation Required`;
- return/note outbound protocol blocked until real Sandbox/provider proof;
- Production interlock is separate from mode;
- readiness never arms Production.

## 2. Before Sandbox traffic

Confirm client readiness, ERPNext Company legal identity/address, Business Nature/Sector/provider data, software/POS registration where applicable, buyer identity, reviewed mappings, native ERPNext tax setup, Sandbox mode/token, Production unarmed and zero reconciliation-required invoices.

## 3. Official reference and mapping review

Sync official reference families and verify HS Code, FBR UOM, Sale/Transaction Type, contextual HS-UOM, contextual Rate and SRO evidence where applicable. Clear `needs_review` only after real evidence/review.

## 4. Read-only activation readiness

- `sandbox_ready=true`: prerequisites exist.
- `sandbox_proven=true`: persisted real Sandbox validate/POST proof exists.
- `production_switch_ready=true`: Sandbox proof plus strict Production prerequisites are green.

Mock/fake evidence never counts.

## 5. Required Sandbox proof

Retain real validate + POST evidence for Sales Invoice and POS Invoice when POS is enabled. Include native return/note only after the actual FBR/provider note contract is proven and returns are in scope.

## 6. Known Offline acceptance

If permitted by current provider/legal rule, configure `Known Offline Policy = Operator Confirmed` and the approved upload window. Declare only before any Production POST attempt. Preserve Offline Pending evidence and upload only through the explicit controlled action. Never add an automatic uploader.

## 7. Print and correction certification

Before Production confirm the authoritative FBR Digital Invoicing System logo attachment, software/POS registration where required, accepted FBR number/QR, final QR physical presentation, Offline Pending marker, proven return/note terminology, official generation-time correction basis, external completion evidence and Commissioner reference where required.

Ledgix ships no fabricated official DI artwork.

## 8. Production pre-switch gate

Require real Sandbox proof, client UAT, seller identity, reviewed mappings/reference evidence, authoritative DI logo, final print/QR sign-off, Production token, approved release SHA, strict release evidence, fresh verified backup, zero reconciliation-required invoices and Production still unarmed during review.

## 9. Production activation

Activate only through the explicit supported workflow after approval. Keep first live submissions manual/observed and retain go-live evidence. Never activate by direct DB manipulation.

## 10. Failure handling

Known rejection: preserve response and correct real configuration/data.
Ambiguous POST: keep `Reconciliation Required` and reconcile externally before retransmission.

## 11. Current project state

As of 2026-09-25 the client-independent software is ready for client certification after the final handoff patch/migrate/gate closes. Real seller identity/reference evidence, Sandbox certification, note protocol, provider offline rule/window and Production activation remain external/pending.
