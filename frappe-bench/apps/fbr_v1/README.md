# Federal Tier-1 POS / IMS V1

`fbr_v1` is the current Ledgix application for the Federal FBR Tier-1 POS / IMS V1 contract on Frappe 15 and ERPNext 15.

ERPNext remains authoritative for Sales Invoice, POS Invoice, native returns/Credit Notes, taxes, GL, stock, payments, receivables, and totals. This app owns fiscal classification, immutable evidence snapshots, exact V1 serialization, guarded transport, fiscal-result metadata, reconciliation, offline/compliance and correction evidence, internal closing evidence, print/QR presentation, and readiness evidence.

Supported transports are the software-owned Local IMS and Cloud Sandbox/Production endpoints. Cloud authentication uses a Bearer token. Success requires `Code == "100"` and a non-empty `FBRInvoiceNumber` or `InvoiceNumber`.

Real transport has two independent site-config gates: `fbr_v1_network_cutover_active` and `fbr_v1_production_cutover_active`, both default `0`. Production also requires its distinct credential, `production_post_armed`, and complete profile/device/authority evidence. General cutover alone cannot authorize Production. Ambiguous sends enter reconciliation; blind retry and fiscal retransmission scheduling are absent.

Software implementation was verified locally at `e6f9b8f9986841584904a500f356e746ad1b415e`: 46/46 V1 tests, existing-site migration, database acceptance, first-attempt reinstall, and post-reinstall migration/idempotency passed while both gates remained off. Real client evidence, credentials, Sandbox acceptance, and Production approval/activation remain external and pending.

Unsupported contracts remain fail-closed. See the [current documentation router](../../docs/fbr/README.md), [V1 authority](../../docs/fbr/fbr_v1/README.md), [setup guide](../../docs/fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md), and [Production checklist](../../docs/fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md).

Fresh installation and normal migration are supported. Install ERPNext before `fbr_v1`; do not install frozen `fbr_v12` alongside it as a second active integration. Historical V1.2 ancestry only supplied safe Frappe structure; dormant V2/DI entry points are retired stubs, not active runtime authority.
