# Ledgix POS — FBR Architecture

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Software Ready for Client Certification:** YES  
**Sandbox Certified:** NO  
**Production Ready:** NO  
**Production Active:** NO  
**General V2 network cutover:** DISABLED

## 1. Purpose

This document defines the current FBR architecture of Ledgix POS.

It consolidates the final implementation after the ERPNext-native tax redesign and FBR V2 hardening.

The governing boundary is:

> **ERPNext owns the commercial/accounting transaction. Ledgix owns FBR-specific classification, immutable compliance evidence, readiness, transport safety, submission evidence, Known Offline, reconciliation and operator workflow around that same ERPNext invoice.**

No current FBR workflow may revive the historical Ledgix Sale/Return monetary engine.

---

## 2. Current status model

Do not collapse the following labels.

| State | Current meaning |
|---|---|
| Software Ready for Client Certification | Software-side architecture, local regression and fail-closed controls are sufficiently closed to begin real client certification |
| Sandbox Certified | Requires genuine authorized Sandbox evidence; currently NO |
| Production Ready | Requires genuine certification, client/provider/legal evidence, release/backup readiness and explicit go-live prerequisites; currently NO |
| Production Active | Requires explicit approved activation; currently NO |

Local mocks, test fixtures and runtime gates are not legal/certification evidence.

---

## 3. Commercial source authority

Supported current FBR source DocTypes are:

- Sales Invoice;
- POS Invoice.

A source must be submitted.

Historical Ledgix Sale / Ledgix Sales Return are not current submission sources.

ERPNext POS consolidated accounting Sales Invoices are excluded as duplicate commercial FBR sources.

The original POS Invoice remains the retail source transaction.

---

## 4. High-level flow

    ERPNext Sales/POS Invoice
      -> native pricing / monetary tax / accounting
      -> before-submit immutable FBR V2 snapshot
      -> submit
      -> readiness
      -> payload builder
      -> transport policy
      -> validate / POST
      -> Submission Log
      -> official FBR status/reference on same ERPNext invoice
      -> print / reconciliation / correction workflow

There is no parallel FBR sales ledger.

---

## 5. Primary implementation map

| Concern | Current source |
|---|---|
| Native orchestration/status | api/fbr_native.py |
| FBR V2 transport policy | api/fbr_v2_transport.py |
| Readiness | services/fbr_v2_readiness.py |
| Payload | services/fbr_v2_payload_builder.py |
| Immutable snapshot | services/fbr_v2_snapshot_persistence.py |
| Seller/buyer identity | services/erpnext_fbr_identity.py |
| Native snapshot construction | services/erpnext_fbr_snapshot.py |
| Submission log helpers/locking | services/fbr_submission_support.py |
| Activation readiness | api/fbr_activation.py |
| Official references | api/fbr_reference_v2.py |
| Known Offline | api/fbr_offline.py |
| Tax component semantics | services/erpnext_tax_authority.py + FBR component mappings |
| Desk Center | api/fbr_v2_center.py + ledgix_tax_center Page |
| Print context | api/printing.py |
| Legacy protection | api/fbr_legacy_guard.py + hooks.py |

---

## 6. Company-scoped Integration Profile

Ledgix FBR Integration Profile is the company-scoped configuration authority.

The Company field is unique.

Important fields include:

- enabled;
- mode;
- submit trigger;
- provider type;
- licensed integrator/provider name;
- protocol version;
- Business Nature;
- sector;
- onboarding status;
- IP whitelist status;
- software/POS registration;
- authoritative Digital Invoicing logo attachment;
- technical contact;
- Sandbox token;
- Production token;
- Production posting arm;
- block-on-preflight policy;
- Known Offline policy;
- offline upload window;
- reference sync state.

Do not use one global FBR profile across multiple ERPNext Companies.

---

## 7. Operating modes

Supported profile modes are:

- Disabled;
- Sandbox;
- Production;
- Paused.

Transport requires the requested mode to match the configured profile mode.

A caller cannot request Production while the profile remains Sandbox.

Mode alone is not authorization.

Production POST has additional gates.

---

## 8. Submit trigger

The profile supports:

- Manual;
- On Submit;
- Validate Only.

Submit trigger controls intended orchestration behavior.

It does not bypass:

- token requirement;
- payload readiness;
- Sandbox certification;
- Production arm;
- general network cutover;
- reconciliation state;
- Known Offline restrictions.

---

## 9. Credentials

Sandbox and Production tokens are stored as Password fields on the Integration Profile.

Transport retrieves the appropriate credential server-side.

Returned transport/readiness payloads are designed to expose only presence/state, not token values.

Current evidence/result structures explicitly mark:

    contains_secrets = false

where applicable.

Do not log, commit, print or send raw token values to the browser.

---

## 10. Seller identity

Seller identity is derived from ERPNext Company and Company Address.

The FBR layer does not maintain a second seller legal master as commercial authority.

Activation readiness expects genuine legal fields such as:

- Company legal/business name;
- NTN/CNIC / tax ID;
- Company Address;
- State/Province.

Missing legal identity blocks readiness.

---

## 11. Buyer identity

Buyer identity derives from the ERPNext Customer/address context captured for the invoice.

Payload identity must come from current invoice-time evidence.

Where required values are missing or ambiguous, readiness fails instead of inventing data.

---

## 12. Item classification

Ledgix FBR Item Mapping links:

    ERPNext Company + ERPNext Item
      -> FBR classification

Typical mapping fields include:

- HS Code;
- FBR UOM;
- Sale / Transaction Type;
- FBR rate/reference description;
- tax basis;
- Notified Retail Price;
- SRO schedule/item references;
- effective dates;
- Needs Review;
- source/review metadata.

This mapping does not own monetary tax amount.

---

## 13. Effective mapping rules

Mappings are date-sensitive.

The compliance/taxable-base layer evaluates effective_from/effective_to.

Overlapping active mappings for the same Item/context fail closed.

A mapping marked Needs Review must not be silently treated as approved evidence in safety-sensitive paths.

---

## 14. FBR tax component mapping

Ledgix FBR Tax Component Mapping classifies ERPNext tax-account evidence into FBR concepts.

Current components include:

- Sales Tax Applicable;
- Sales Tax Withheld At Source;
- Extra Tax;
- Further Tax;
- FED Payable.

Amounts originate from ERPNext-native tax evidence.

The mapping never becomes a second tax calculator.

---

## 15. Official FBR Reference Data

Ledgix FBR Reference Data is a controlled cache/evidence layer for official FBR reference values.

Reference families include concepts such as:

- Province;
- Document Type;
- Item Code;
- SRO Item Code;
- Transaction Type;
- UOM;
- Rate;
- HS-UOM;
- SRO Schedule;
- SRO Item;
- Registration Type.

Rows preserve:

- FBR ID/code;
- description;
- deterministic context key;
- canonical query context;
- protocol/source version;
- source endpoint;
- fetched time;
- source payload;
- effective dates;
- active/stale state.

Credentials must never be stored in query context.

---

## 16. Reference sync

sync_core_reference_data performs only parameter-free official reference-family synchronization.

It:

- requires administrative access;
- uses per-family savepoints;
- records failed families separately;
- updates profile reference-sync status;
- does not validate/POST invoices;
- does not arm Production.

Official reference sync and invoice transport are separate capabilities.

---

## 17. Monetary tax authority

ERPNext is the sole monetary tax authority.

FBR mapping/classification adds compliance meaning around the native transaction.

See ACCOUNTING_AND_TAX.md.

Important distinction:

    ERPNext tax rows / totals / GL
        !=
    FBR classification / payload semantics

Ledgix must reconcile payload amounts to native ERPNext transaction evidence.

---

## 18. Immutable snapshot purpose

FBR payload generation must not reconstruct a historical legal invoice from mutable master data after submission.

Therefore Ledgix captures immutable invoice-time compliance evidence before submission.

Implementation:

    services/fbr_v2_snapshot_persistence.py

Snapshot version at this baseline:

    2

---

## 19. Snapshot capture point

hooks.py registers snapshot capture on:

- Sales Invoice before_submit;
- POS Invoice before_submit.

Snapshot capture is active when the Company has an enabled/non-Disabled FBR profile.

The commercial document is still ERPNext.

The snapshot is compliance evidence attached to the same transaction.

---

## 20. Snapshot structure

The snapshot stores header and per-line evidence.

It includes a canonical JSON representation and SHA-256 hash.

Header fields include version/hash/captured-at/JSON.

Line fields include version/hash/JSON.

The header also contains a manifest of line hashes.

---

## 21. Snapshot verification

Reading persisted V2 snapshot verifies:

- expected snapshot version;
- header JSON exists;
- header hash matches canonical content;
- each line has expected version;
- each line hash matches its canonical JSON;
- actual line-hash manifest matches header manifest;
- line count matches invoice rows.

Failure blocks payload readiness.

---

## 22. Existing snapshot mismatch

If an invoice already contains a snapshot and current capture inputs differ, the service rejects the mismatch rather than silently replacing historical evidence.

The snapshot is intended to be immutable legal/compliance evidence.

---

## 23. Readiness service

evaluate_invoice_readiness is read-only.

It checks:

- source DocType/name;
- Company FBR profile;
- immutable snapshot;
- identity evidence;
- official reference consistency;
- line references;
- tax classification;
- Sandbox certification state;
- transport prerequisites.

It returns errors/warnings and booleans such as:

- payload_input_ready;
- sandbox_transport_ready;
- production_transport_ready.

It does not:

- write the database;
- build/POST a network request;
- expose secrets.

---

## 24. Diagnostic live identity fallback

If persisted snapshot cannot be read, readiness may resolve live identity only for diagnostics.

That fallback is explicitly not payload authority.

Payload building remains blocked because the persisted snapshot error is still a readiness error.

This prevents mutable current master data from masquerading as invoice-time legal evidence.

---

## 25. Payload builder

The canonical V2 payload builder requires:

- Sales Invoice or POS Invoice;
- existing source;
- supported transaction semantics;
- readiness with no blocking errors;
- persisted V2 snapshot;
- verified snapshot hash;
- invoice-time identity evidence;
- non-empty snapshot lines;
- reconciled native monetary totals;
- supported FBR classification.

It does not use the historical Ledgix monetary engine.

---

## 26. Return / electronic note behavior

Native ERPNext returns remain authoritative commercial documents.

However, outbound FBR Debit/Credit Note semantics remain fail-closed until genuine Sandbox/provider proof establishes the exact contract required for the client's path.

The software should not claim certified note semantics based only on local mapping assumptions.

---

## 27. SRO and special semantic fail-closed behavior

The payload builder contains deliberate fail-closed checks for FBR semantic areas that require explicit proof.

Where exact regulatory payload meaning is not certified, the system should block rather than guess.

This is intentional.

---

## 28. Sandbox transport

Sandbox uses the configured Sandbox profile/token and Sandbox endpoint.

At the forensic baseline, the global V2 network cutover is false.

There is a narrow explicit local Sandbox certification exercise exception gated by a specific environment confirmation.

That exception is not Production authorization.

---

## 29. General network cutover

Current constant:

    V2_NETWORK_CUTOVER_ACTIVE = False

This blocks general invoice Validate/POST traffic.

The final forensic audit made zero real FBR/PRAL calls.

Do not change this flag casually as part of documentation, installation or ordinary migration.

---

## 30. Production transport policy

For Production POST, transport requires at least:

- Company Integration Profile exists;
- profile enabled;
- profile mode = Production;
- completed Sandbox Certification with derived complete evidence;
- production_post_armed = true;
- Production token available;
- requests transport available;
- payload/network operation valid.

Higher-level orchestration/readiness imposes additional conditions.

---

## 31. Sandbox Certification

Ledgix FBR Sandbox Certification is company/profile-scoped.

A certification includes required scenarios.

Scenario proof fields are read-only and re-derived from persisted Submission Logs.

Current evidence includes:

- representative source DocType/name;
- Validate status/log;
- POST status/log;
- Sandbox FBR invoice number;
- completion time;
- last error.

---

## 32. Certification cannot be manually faked

When a certification is saved:

1. Integration Profile is validated;
2. Company is forced to match profile Company;
3. evidence is re-derived;
4. scenario Validate/POST fields are populated from real matching logs;
5. evidence_complete is derived;
6. status Complete is rejected unless required scenarios have matching proof.

A checkbox alone cannot certify the system.

---

## 33. Derived certification state

Production transport does not trust only the stored evidence_complete field.

Current readiness re-derives evidence from the certification/scenario/log relationship.

Certification is complete only when:

- stored status is Complete;
- derived required evidence is complete.

---

## 34. Submission Log

Ledgix FBR Submission Log records compliance transport evidence.

Statuses include:

- Pending;
- Validated;
- Submitted;
- Failed;
- Offline Pending;
- Reconciliation Required;
- Skipped;
- Paused;
- Not Required.

Evidence can include:

- source DocType/name;
- invoice type;
- FBR status;
- FBR invoice number;
- attempt count;
- Known Offline timestamps/reason;
- error code/message;
- submitter/time;
- redacted request/response JSON.

It is not an accounting ledger.

---

## 35. Submission locking

fbr_submission_support provides a submission lock keyed to the FBR reference.

This prevents concurrent submissions for the same reference from racing through the same transport path.

Locking is a concurrency safety control, not a substitute for idempotent status checks.

---

## 36. Transport result safety

The V2 transport layer is intentionally narrow.

It is responsible for:

- profile/mode/token policy;
- endpoint selection;
- HTTP call;
- FBR response shape interpretation;
- Production ambiguity classification.

It does not own:

- accounting;
- retry scheduling;
- profile-state mutation;
- submission-log lifecycle;
- payload monetary calculation.

---

## 37. Production crash-window guard

Production POST has an explicit durability boundary.

Before the external POST network call:

1. create a Pending Submission Log;
2. mark invoice Reconciliation Required;
3. record pending attempt/error context;
4. commit this state;
5. only then enter the external Production POST network window.

This is deliberate.

The pre-network committed state means a process crash cannot leave the system believing there was definitely no attempt.

---

## 38. Why Reconciliation Required is set before POST

The dangerous failure mode is:

    POST may reach FBR
      -> local process crashes
      -> local transaction rolls back
      -> operator retries blindly
      -> duplicate legal submission risk

Ledgix prevents this by making the "possible attempt" state durable before the external call.

If finalization later succeeds, the same attempt log/status is finalized.

---

## 39. Ambiguous Production POST classification

A Production POST can be considered ambiguous when a real network call occurred and, for example:

- network error;
- HTTP 408;
- HTTP 5xx;
- successful HTTP response with uncertain invoice body;
- valid-looking success without required FBR invoice number.

Ambiguous outcome sets:

    requires_reconciliation = true

It must not be blindly retransmitted.

---

## 40. Reconciliation Required

When invoice status is Reconciliation Required:

- generic submit path blocks;
- Known Offline is not allowed;
- operator must reconcile externally with FBR/PRAL/provider.

This state protects against duplicate Production posting.

---

## 41. Release after reconciliation

Current manual release requires:

- administrative submit role;
- invoice currently Reconciliation Required;
- exact confirmation text:

    CONFIRMED NOT RECEIVED BY FBR

The release action:

- records a new Pending log;
- changes status back to Pending;
- makes no network call.

It means external reconciliation confirmed the invoice was not received and a manual retry may now be evaluated.

It does not itself resubmit.

---

## 42. No blind retry scheduler

hooks.py defines:

    scheduler_events = {}

for this FBR retransmission architecture.

There is no generic automatic retry worker for ambiguous Production outcomes.

This is intentional.

---

## 43. Known Offline is a different state

Known Offline is not an ambiguous POST recovery mode.

Known Offline is valid only before any Production POST attempt.

Lifecycle:

    explicit operator declaration
      -> Offline Pending
      -> controlled queue
      -> controlled upload
      -> Submitted / Failed / Reconciliation Required

It has separate policy and evidence.

---

## 44. Known Offline prerequisites

Current Known Offline policy requires:

- global Production network cutover active;
- Integration Profile exists;
- profile enabled;
- profile mode = Production;
- Production token configured;
- Production posting armed;
- completed Sandbox certification;
- offline_policy = Operator Confirmed;
- positive client/provider-specific upload window.

The upload window is not hardcoded as law by Ledgix.

It must come from the current client/provider rule.

---

## 45. Known Offline declaration

Declaration requires:

- System Manager or Ledgix Admin;
- exact confirmation:

    DECLARE KNOWN OFFLINE

- submitted native FBR source;
- non-return source under current certified scope;
- reason;
- no official FBR number;
- not Reconciliation Required;
- no prior Production POST attempt;
- Known Offline policy ready;
- payload readiness.

Declaration itself makes no FBR network call.

---

## 46. Offline evidence

Declaration records:

- issued time;
- upload due time;
- reason;
- configured upload window;
- explicit no-network-call evidence;
- Production mode context;
- Submission Log;
- Offline Pending state on the ERPNext source invoice.

---

## 47. Offline queue

Managers can view the queue.

It reports:

- source DocType/name;
- Company;
- posting date;
- Customer;
- grand total;
- offline issued time;
- upload due time;
- reason;
- linked Submission Log;
- overdue flag.

Queue read makes no network call and no write.

---

## 48. Controlled offline upload

Upload requires:

- System Manager or Ledgix Admin;
- exact confirmation:

    UPLOAD OFFLINE INVOICE

- current Offline Pending status;
- no FBR invoice number;
- not Reconciliation Required;
- no prior Production POST attempt;
- policy still ready.

It then enters the normal guarded submission pipeline with explicit offline-upload context.

---

## 49. Offline upload failure behavior

If no network call occurs:

- Offline Pending must remain preserved.

If a network call occurs, supported terminal states include:

- Submitted;
- Failed;
- Reconciliation Required.

An unsupported state is rejected.

---

## 50. FBR status on ERPNext invoice

The current architecture stores compliance state on the authoritative ERPNext invoice through Ledgix custom fields.

Examples include:

- FBR status;
- FBR reference/invoice number;
- QR/status evidence;
- error code/message;
- linked Submission Log;
- Known Offline timestamps/reason;
- reconciliation-required state;
- upload due time.

This keeps compliance attached to the real commercial source.

---

## 51. On-submit behavior

hooks.py registers on_native_invoice_submit for Sales Invoice and POS Invoice.

After submission, eligible invoices are queued/handled according to current FBR policy.

Consolidated POS accounting invoices are excluded.

The hook must not bypass readiness or transport interlocks.

---

## 52. Cancellation protection

Before cancel of Sales Invoice/POS Invoice, Ledgix blocks cancellation when the invoice has FBR history that requires controlled handling.

Cancellation is blocked when, for example:

- official FBR invoice number exists;
- status is Reconciliation Required;
- status is Offline Pending.

The operator must use the appropriate return/note/correction/offline/reconciliation workflow.

---

## 53. Activation readiness

api/fbr_activation.py is read-only.

It:

- never reads token values;
- never sends network traffic;
- never arms Production.

It evaluates Sandbox and Production-switch readiness from persisted configuration/evidence.

---

## 54. Sandbox readiness checks

Current Sandbox readiness includes checks such as:

- client onboarding ready;
- Business Profile enables FBR;
- seller identity complete;
- FBR profile appropriately configured;
- Sandbox token configured;
- Production unarmed;
- no Reconciliation Required invoice.

Actual code should be treated as authority for the complete check set.

---

## 55. Sandbox proof

Sandbox proof is derived from persisted FBR Submission Logs.

Current proof requires real successful Validate/POST evidence for Sales Invoice.

If POS is enabled, POS Invoice proof is also required.

If return proof is explicitly required for the client's scope, native return/note Validate/POST proof is required.

Mocks do not count.

---

## 56. Production-switch readiness

Production-switch readiness includes, among other checks:

- Sandbox proof complete;
- Sandbox Certification complete;
- Production token configured;
- authoritative Digital Invoicing logo configured;
- Production still unarmed during review;
- not already in Production mode;
- strict client operational/release evidence green;
- fresh verified backup;
- exact approved 40-character release SHA recorded;
- zero unresolved Reconciliation Required invoices.

The gate itself does not arm Production.

---

## 57. Backup/release evidence is part of Production readiness

Production activation is not purely an API credential switch.

The current readiness model expects operational evidence including:

- strict client release/provisioning readiness;
- verified backup;
- approved exact release SHA.

This prevents compliance go-live from being detached from recoverable deployment state.

---

## 58. Digital Invoicing logo

Ledgix does not ship fabricated official Digital Invoicing artwork as legal evidence.

The Integration Profile has an attachment field for the authoritative logo confirmed for the client/provider.

Production readiness requires the actual configured evidence where applicable.

---

## 59. Print / QR

Current print architecture can use:

- ERPNext seller identity;
- accepted FBR invoice number;
- QR evidence;
- software/POS registration;
- configured authoritative DI logo;
- appropriate status wording.

Final physical/legal presentation remains part of genuine client/provider certification.

A local mock QR is not certification evidence.

---

## 60. Correction workflow

Post-FBR correction/cancellation is conservative.

Current software tracks correction evidence, but external rules/workflow must be genuinely confirmed.

Do not invent a correction completion merely because an internal record exists.

Where timing rules or Commissioner approval apply, completion requires external evidence.

---

## 61. Return print terminology

Until outbound note semantics are genuinely proven, return presentation must remain conservative and not imply an unproven FBR note protocol.

The historical/current operational documentation uses neutral return/adjustment framing where appropriate.

---

## 62. Role model for FBR APIs

Current native FBR role gate generally allows:

### View / preview-type actions

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

### Submission / release-sensitive actions

- System Manager;
- Ledgix Admin.

Individual endpoints can impose stricter subsystem-specific rules.

Do not treat Ledgix Manager as a Production activation role.

---

## 63. Tax & FBR Center

The current Desk Page is:

    ledgix-tax-center

It exposes areas such as:

- Overview;
- ERPNext Tax Setup;
- FBR Integration;
- Product Compliance;
- Certification & Readiness.

The page explicitly states that ERPNext owns monetary tax/accounting.

It provides operator controls for supported configuration/readiness/reference/offline workflows.

It intentionally does not provide an unguarded generic Production-submit button.

---

## 64. Legacy FBR API protection

hooks.py redirects historical Ledgix Sale/Return FBR APIs into fail-closed legacy guards.

Examples include old:

- preview;
- readiness;
- payload;
- validate;
- submit;
- reconciliation release

contracts tied to Ledgix Sale/Return.

The presence of old source files does not authorize direct use.

---

## 65. Legacy tax-master retirement

Old mixed Ledgix tax configuration masters were physically retired from current source/schema authority.

This is distinct from frozen historical business ledgers.

Current FBR V2 uses:

- ERPNext monetary tax;
- company-scoped Integration Profile;
- current mapping/reference/certification/evidence DocTypes.

Do not recreate the old Tax Profile / Tax Category / Tax Rate / Item Tax Profile / global FBR Settings engine.

---

## 66. Submission Log permission intent

The final forensic hardening changed the Submission Log DocType schema so normal System Manager/Ledgix Admin/Ledgix Manager Desk permissions are read-only evidence.

This is intended to prevent ordinary Desk users from creating, editing or deleting submission history.

### Current source caveat

At the 2026-09-26 documentation baseline, setup/permissions.py still contains an older broader policy row for Ledgix FBR Submission Log, and fast_permissions.py uses that centralized policy during migrate.

Therefore the repository currently contains a **permission-policy/schema inconsistency**:

- DocType JSON says Submission Log is read-only;
- centralized post-migrate permission policy still describes broader System Manager/Ledgix Admin rights.

Until that source mismatch is corrected and post-migrate behavior is re-verified, developers must not claim that Submission Log Desk immutability is guaranteed across every migrate solely from the DocType JSON.

This is a current code-maintenance defect, not a reason to weaken the intended control.

---

## 67. Secret redaction

Submission support uses transport evidence redaction before storing/logging request/response data.

Error/message helpers also sanitize evidence.

Transport results are designed not to return raw token values.

Security review should continue to treat logs/screenshots/tickets as potentially sensitive even with application redaction.

---

## 68. Company isolation

FBR data is company-sensitive.

Important Company scoping includes:

- Integration Profile;
- Item Mapping;
- Tax Component Mapping;
- seller identity;
- Sandbox Certification;
- transport token/mode;
- source invoice;
- activation readiness.

Cross-company proof must never satisfy another Company's Production gate.

---

## 69. Current FBR external blockers

The final forensic baseline still requires genuine client/provider evidence such as:

- seller legal identity;
- complete registered/default Company Address;
- province;
- required buyer legal data;
- reviewed Item mappings;
- official current reference evidence;
- genuine Sandbox token;
- genuine Production token when appropriate;
- provider/LI details;
- Business Nature/Sector;
- software/POS registration where required;
- authoritative DI logo;
- whitelist/onboarding proof;
- genuine Sandbox Validate/POST evidence;
- final print/QR confirmation;
- return/note proof if in scope;
- confirmed Known Offline rule/window if required;
- verified release/backup evidence;
- explicit Production authorization.

These must not be fabricated.

---

## 70. Current final status

At this baseline:

- Software Ready for Client Certification: YES;
- Sandbox Certified: NO;
- Production Ready: NO;
- Production Active: NO;
- general V2 network cutover: false;
- final forensic audit real FBR/PRAL calls: zero.

The next legitimate FBR phase is genuine client certification/onboarding, not Production activation.

---

## 71. Development checklist

Before modifying FBR code, confirm:

- [ ] Commercial source remains ERPNext Sales/POS Invoice.
- [ ] Consolidated POS accounting invoice cannot duplicate submission.
- [ ] ERPNext remains monetary tax authority.
- [ ] Company scoping is explicit.
- [ ] Credentials remain server-side Password fields.
- [ ] Snapshot remains invoice-time immutable evidence.
- [ ] Payload requires verified persisted snapshot.
- [ ] Unsupported semantics fail closed.
- [ ] Sandbox certification is derived from persisted real evidence.
- [ ] Production POST still requires certification + arm + token + cutover/readiness.
- [ ] Production crash-window guard is not weakened.
- [ ] Ambiguous POST remains Reconciliation Required.
- [ ] No blind retry scheduler is introduced.
- [ ] Known Offline remains separate from ambiguous POST.
- [ ] Offline deadline is not invented.
- [ ] Return/note claims match genuinely proven scope.
- [ ] Logs/results do not expose secrets.
- [ ] Submission evidence cannot be casually mutated by normal Desk workflows.
- [ ] Current permission-policy inconsistency is resolved before claiming durable post-migrate immutability.
- [ ] Local tests are not described as real certification.

---

## 72. Summary

The FBR architecture in one sentence is:

> **Ledgix attaches a company-scoped, hash-verified and fail-closed compliance pipeline to ERPNext-native Sales/POS Invoices, preserving real FBR evidence and preventing unsafe Production retransmission while keeping monetary tax/accounting in ERPNext and refusing to treat local tests, mutable masters or ambiguous network outcomes as certification truth.**
