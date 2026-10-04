# Federal Tier-1 POS / IMS V1

`fbr_v1` is the current Ledgix application for the Federal FBR Tier-1 POS / IMS V1 contract on Frappe 15 and ERPNext 15.

ERPNext remains authoritative for Sales Invoice, POS Invoice, native returns/Credit Notes, taxes, GL, stock, payments, receivables, and totals. This app owns fiscal classification, immutable evidence snapshots, exact V1 serialization, guarded transport, fiscal-result metadata, reconciliation, offline/compliance and correction evidence, internal closing evidence, print/QR presentation, and readiness evidence.

Supported transports are the software-owned Local IMS and Cloud Sandbox/Production endpoints. Cloud authentication uses a Bearer token. Success requires `Code == "100"` and a non-empty `FBRInvoiceNumber` or `InvoiceNumber`.

Real transport has two independent site-config gates: `fbr_v1_network_cutover_active` and `fbr_v1_production_cutover_active`, both default `0`. Production also requires its distinct credential, `production_post_armed`, and complete profile/device/authority evidence. General cutover alone cannot authorize Production. Ambiguous sends enter reconciliation; blind retry and fiscal retransmission scheduling are absent.

Local corrective validation is recorded in `docs/production/final_corrective_verification.md` at the repository root. Real client evidence, credentials, Sandbox acceptance, and Production approval/activation remain external and pending.

Unsupported contracts remain fail-closed. See the [current documentation router](../../docs/fbr/README.md), [V1 authority](../../docs/fbr/fbr_v1/README.md), [setup guide](../../docs/fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md), and [Production checklist](../../docs/fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md).

Fresh installation and normal migration are supported. Install ERPNext before `fbr_v1`; new installation of retired `fbr_v12` is prohibited. Historical V1.2 ancestry only supplied safe Frappe structure; dormant V2/DI entry points are retired stubs, not active runtime authority.

Fresh Federal V1 schema excludes retired Business Nature, Reference Data, Sandbox Certification and Sandbox Scenario DocTypes and DI-only Integration Profile fields. Existing historical metadata remains resolvable through read-only controllers. A pre-model-sync patch captures exact old profile values and child rows into immutable Ledgix FBR Legacy Evidence; old encrypted credential storage is preserved without decryption and is never promoted to V1. Payload storage has no ordinary API/Desk read permission; audit roles can read only metadata/hash. No historical tables or records are dropped.

Sandbox transport acceptance is distinct from external Production approval. Readiness exposes `sandbox_transport_acceptance_complete`, `external_production_approval_complete`, and `production_configuration_ready`. A System Manager must verify an explicit approval reference and readable uploaded File; verification user/time are stamped by the server. Only System Manager can arm posting from 0 to 1; authorized profile writers can disarm. Site cutovers remain independent.

Legacy Sale formats are non-fiscal archival views. Missing or reconstructed historical identity is not verified fiscal evidence. Pending historical identity backfills are no-ops; current native V1 prints still require strict immutable snapshots and authoritative fiscal results.
