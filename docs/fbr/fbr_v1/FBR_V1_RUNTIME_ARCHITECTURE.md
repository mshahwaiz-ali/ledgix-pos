# Federal Tier-1 POS / IMS V1 Runtime Architecture

**Status:** current operating authority; local corrective evidence is in the [verification report](../../production/final_corrective_verification.md).

## Authority boundary

ERPNext owns Sales Invoice, POS Invoice, native returns/Credit Notes, tax rows, GL, stock, payments, receivables, currency, and totals. `fbr_v1` never creates a second business authority. It owns fiscal classification, immutable evidence, documented V1 serialization, guarded transport, response/reconciliation evidence, offline/compliance and correction tracking, internal closings, print/QR metadata, and readiness evidence.

## Evidence and submission

Before submission, the app captures an immutable header/line snapshot from the submitted ERPNext source, including stable POS-device identity and native payment/tax evidence. SHA-256 hashes and a line manifest detect inconsistency; existing snapshots are verified rather than overwritten.

The serializer reconstructs the documented V1 request. Unsupported conditions fail before transport. Each possible send first commits durable intent with attempt, idempotency, snapshot, and request hashes. Success requires HTTP success, `Code == "100"`, and a returned fiscal number. A possibly sent request with no certain response becomes `Reconciliation Required`; blind retry is prohibited and no retry scheduler exists.

## Transport and gates

- Local IMS health: `GET http://localhost:8524/api/IMSFiscal/Get`
- Local IMS fiscalization: `POST http://localhost:8524/api/IMSFiscal/GetInvoiceNumberByModel`
- Cloud Sandbox: `POST https://esp.fbr.gov.pk:8244/FBR/v1/api/Live/PostData`
- Cloud Production: `POST https://gw.fbr.gov.pk/imsp/v1/api/Live/PostData`
- Cloud authentication: Bearer token.

Endpoints are code-owned constants; TLS verification stays enabled. `fbr_v1_network_cutover_active` defaults off. Production additionally requires `fbr_v1_production_cutover_active`, its distinct credential, `production_post_armed`, and complete profile, authority, retention, device, topology, onboarding, documented QR acceptance, and explicit external Production approval evidence. Unsupported signature algorithms remain unresolved.

## Operational evidence

- The current number-only QR remains 7 mm; external verification changes its label, not its encoding.
- Outage/restoration evidence creates a fixed 24-hour deadline. Operators may record authoritative upload confirmation; no batch endpoint is guessed.
- Controlled correction APIs track Board/PRAL evidence without changing ERPNext accounting or calling a guessed Board API.
- Fiscal events are append-only. Daily/weekly/monthly closings are immutable internal evidence whose external status remains `Unresolved`.
- The read-only audit bundle reconstructs non-secret snapshots, requests, hashes, attempts, events, corrections, closings, return links, and reconciliation/offline state.

Digital Invoicing V1.2 transport, reference-sync, readiness, snapshot, payload, and provisioning entry points are retired stubs. Historical schema/data remain preserved, but no V2 module is an alternate runtime path.

See the [protocol contract](FBR_V1_DOCUMENTED_PROTOCOL_CONTRACT.md) and [unresolved contract register](FBR_V1_UNRESOLVED_EXTERNAL_CONTRACTS.md).

Sandbox transport acceptance, external Production approval, configuration readiness, both cutovers and the posting arm are independent release requirements. Retired profile values are preserved in immutable audit evidence before schema sync; fresh V1 schema excludes DI-only fields and DocTypes. Existing historical metadata is retained through rejecting controllers. Only System Manager may verify Production approval or arm posting.
