# FBR V1 Bootstrap Clone — Forensic Audit

> **HISTORICAL IMPLEMENTATION RECORD — not current operating/setup authority. See [README.md](README.md). Implementation closed at `e6f9b8f9986841584904a500f356e746ad1b415e`.**

**Audit baseline:** `main@17f81554a0eeea85e9a6868719a9b76c0dcf4e36`  
**Scope:** `apps/fbr_v1` only  
**Mode:** source inspection only; no site mutation; no FBR network call; no production access.

## 1. Executive finding

`apps/fbr_v1` is not a Federal Tier-1/V1 implementation yet. It is a bootstrap extraction of `fbr_v12` with package/module labels changed to FBR V1 while substantial DI/V1.2 protocol behavior remains intact.

The inherited code is useful in three areas:

1. Frappe/ERPNext app scaffolding;
2. ERPNext-native accounting/tax snapshot mechanics;
3. generic audit/logging/printing patterns.

The inherited code is **not evidence** for:
- legacy SDC endpoint/authentication;
- legacy payload/response;
- legacy onboarding;
- legacy test/production configuration;
- payment enums;
- returns/corrections;
- offline transport;
- closing/reporting;
- DI reference-data APIs.

## 2. Clone evidence

The `fbr_v1` tree mirrors `fbr_v12` one-for-one at the component level. Several files are byte-identical and many others differ only by package/page/workspace names.

The V1 app still contains:
- `api/fbr_reference_v2.py`;
- `api/fbr_v2_transport.py`;
- `api/fbr_v2_center.py`;
- `services/fbr_v2_payload_builder.py`;
- `services/fbr_v2_readiness.py`;
- `services/fbr_v2_snapshot_persistence.py`;
- `setup/fbr_v2_component_mappings.py`;
- Integration Profile protocol default `DI API V1.12`;
- DI-style sandbox tokens, production token, production arming and sandbox certification;
- DI reference-data cache and scenario certification;
- V2 snapshot field names.

That is sufficient to reject “rename = V1 compatibility”.

## 3. Runtime hooks

Current hooks on both `Sales Invoice` and `POS Invoice`:

- `before_validate -> erpnext_taxable_base.stamp_fbr_taxable_base_inputs`
- `before_submit -> fbr_v2_snapshot_persistence.before_submit_capture`
- `on_submit -> fbr_native.on_native_invoice_submit`
- `before_cancel -> fbr_native.block_cancel_after_fbr_submission`

Findings:
- The ERPNext transaction choice is correct: native Sales Invoice/POS Invoice remain transaction authority.
- The `before_submit` snapshot pattern is reusable, but is V2-named and coupled to the V2 readiness model.
- The `on_submit` path ultimately invokes V2 transport/readiness.
- The cancellation policy is based on inherited FBR semantics and must be replaced by a current-rule debit/credit-note lifecycle.
- No scheduler event is registered, despite inherited offline/retry structures.

## 4. API layer findings

### `api/fbr_native.py`
Current orchestration is explicitly V2-oriented:
- imports V2 transport/readiness/payload;
- has `V2_NETWORK_CUTOVER_ACTIVE = False`;
- includes special sandbox-network escape controls;
- implements V2 submit/validate/reconcile and inherited offline statuses.

**Disposition:** REPLACE. Preserve only generic orchestration patterns such as locking, deterministic request identity and “do not blind-retry ambiguous outcome”.

### `api/fbr_v2_transport.py`
Contains DI V1.2 gateway URLs for validate/post operations, bearer-token handling, sandbox/production tokens, production arming and certification checks.

**Disposition:** DELETE from V1 runtime / REPLACE with a legacy-SDC adapter only after the exact SDC contract is authoritative. These endpoints belong to the current DI/V1.2 app.

### `api/fbr_transport.py`
Small generic HTTP JSON helper.

**Disposition:** MODIFY. The concept can remain behind a protocol adapter, but no Bearer assumption or arbitrary URL configuration is allowed in V1 until the SDC contract is established.

### `api/fbr_offline.py`
Implements inherited policy and configurable upload-window assumptions.

**Disposition:** REPLACE. Current rule 150XC fixes the deadline at 24 hours after restoration, not an arbitrary configured N-hour window. Exact legacy SDC offline machine behavior is unresolved.

### `api/fbr_activation.py`
Built around V2 sandbox certification, tokens and production activation.

**Disposition:** REPLACE with a regime/readiness gate. Legacy V1 must require proof of grandfathered/currently authorized SDC use before any transport can be enabled.

### `api/client_readiness.py`
Contains useful Company/Address/POS Profile/backup readiness checks mixed with V2 activation/certification assumptions.

**Disposition:** MODIFY. Keep generic ERPNext/environment checks; replace protocol assertions.

### `api/fbr_reference_v2.py`
Implements current DI reference APIs and DI classification cache.

**Disposition:** DELETE from V1 runtime. It belongs to `fbr_v12` unless an authoritative legacy SDC document separately requires the same APIs.

### `api/fbr_v2_center.py`
Desk API is explicitly “ERPNext Native + FBR V2”, reference-data and sandbox-certification based.

**Disposition:** REPLACE.

### `api/printing.py`
Strong point: print context derives money/tax/payment from ERPNext and persisted FBR metadata. Weak point: V2 snapshot/profile assumptions and locally generated QR semantics are not fully source-bound.

**Disposition:** MODIFY. Keep ERPNext rendering authority. Enforce current Chapter-XIV particulars, 7x7 mm QR, FBR number format validation and POS/software registration number. QR payload must remain gated until verified.

## 5. Service layer findings

### `services/erpnext_fbr_identity.py`
Uses Company `tax_id` and linked/default Address; uses Customer `tax_id` and Address with legacy fallbacks.

**Disposition:** MODIFY, mostly reusable. Prefer ERPNext native identity and keep legacy custom fields transitional only.

### `services/erpnext_fbr_snapshot.py`
Instruments ERPNext's native `taxes_and_totals` engine and captures line-level tax evidence. It does not create a second tax calculator.

**Disposition:** KEEP architecture / MODIFY protocol mapping. This is aligned with the requirement that ERPNext remains tax/accounting authority.

### `services/erpnext_taxable_base.py`
Supplies notified retail price as a taxable-base resolver so ERPNext still computes tax.

**Disposition:** KEEP concept / MODIFY. A bootstrap defect is present: `MAPPING_DOCTYPE = "FBR V1 FBR Item Mapping"` does not match the existing DocType name `Ledgix FBR Item Mapping`. Do not fix until implementation phase; record it as a known defect.

### `services/fbr_submission_support.py`
Contains useful serialization, status normalization, log creation and Redis locking. The parser expects DI fields such as `validationResponse`, `invoiceStatuses` and `invoiceNumber`.

**Disposition:** MODIFY: keep lock/log concepts; replace parser/status protocol.

### `services/fbr_v2_payload_builder.py`
DI V1.2 payload, scenario ID and DI mapping assumptions.

**Disposition:** REPLACE entirely.

### `services/fbr_v2_readiness.py`
V2 tokens, current DI reference rows and sandbox certification.

**Disposition:** REPLACE.

### `services/fbr_v2_snapshot_persistence.py`
Good immutable/hash-verified snapshot pattern, but V2-specific field names/version/profile semantics.

**Disposition:** MODIFY into protocol-neutral V1 snapshot persistence. Existing V2 fields must be migrated non-destructively, not silently reinterpreted.

## 6. Schema / setup findings

### `setup/erpnext_fbr_schema.py`
Creates Customer, invoice and invoice-item FBR fields plus the notified-retail-price charge-type extension.

Findings:
- many field names are generic enough to preserve;
- V2 snapshot field names must not become legacy V1 truth;
- old Customer FBR address/province/NTN fields conflict with the intended ERPNext Address/Customer authority and should become transition-only;
- migration must preserve any existing data.

### `setup/erpnext_phase9_extensions.py`
Adds QR, generated-at, submission-log and offline fields/statuses.

**Disposition:** MODIFY. Offline fields are useful but deadline semantics must be corrected to “restoration + 24h”.

### `setup/fbr_v2_component_mappings.py`
Maps ERPNext tax Accounts to FBR components.

**Disposition:** KEEP concept / MODIFY names and validation to current invoice particulars. No monetary calculation belongs here.

### `setup/install.py`
No-network schema/print sync pattern.

**Disposition:** KEEP with new schema modules.

### `setup/print_formats.py`
Force-reloads standard print formats.

**Disposition:** KEEP mechanism, replace template contracts.

## 7. DocType findings

### Ledgix FBR Integration Profile
Currently stores DI protocol version, business nature/sector, sandbox/production tokens, reference sync, sandbox-style onboarding, `production_post_armed`, and configurable offline window.

**Disposition:** REPLACE/MODIFY into a regime-aware profile. It must never auto-upgrade an inherited profile to enabled V1.

### Ledgix FBR Item Mapping
Contains HS, UOM, sale type, rate description, tax basis, notified retail price and SRO fields.

**Disposition:** MODIFY. Keep only fields supported by current invoice/tax requirements or the proven legacy SDC contract. DI-specific sale-type/rate-reference semantics cannot be assumed.

### Ledgix FBR Tax Component Mapping
ERPNext Account -> FBR sales-tax/withheld/extra/further/FED semantics.

**Disposition:** KEEP/MODIFY.

### Ledgix FBR Submission Log
Generic reference/status/error/request/response/offline fields.

**Disposition:** KEEP/MODIFY. Make append-only/audit-safe, add protocol/POS identity/body hash and redact secrets.

### Ledgix FBR Reference Data
DI API reference cache.

**Disposition:** DELETE from active V1 design; preserve existing records read-only if installed.

### Ledgix FBR Sandbox Certification / Scenario
DI scenario certification model.

**Disposition:** DELETE from active V1 design. Legacy test registration is documented historically, but no authoritative scenario catalogue was found.

### Ledgix FBR Business Nature
V2/DI onboarding metadata.

**Disposition:** DELETE from active V1 legacy design unless a legacy source proves it is required.

### Ledgix FBR Correction Request
Enforces a 72-hour correction window and “Commissioner Approval Required” after it.

**Critical finding:** no authoritative current Chapter-XIV source recovered by this audit supports this 72-hour model. Current Chapter XIV instead requires electronic debit/credit notes and logs of adjustments/modifications/cancellations.

**Disposition:** REPLACE. Do not carry the 72-hour rule into V1.

## 8. Desk UI / workspace

The FBR V1 Center still calls:
- `fbr_v2_center.get_v2_center_boot`;
- V2 item mappings;
- V2 reference sync;
- V2 invoice readiness;
- inherited offline endpoints.

The Overview even defaults to “ERPNext Native + FBR V2”.

**Disposition:** REPLACE the JS/API contract. CSS/page shell can be reused.

Workspace links expose Reference Data, Sandbox Certifications and Correction Requests as primary objects.

**Disposition:** MODIFY workspace after the new model is stable.

## 9. Print-format audit

### POS receipt
Good:
- ERPNext totals/payments;
- FBR status and number;
- QR/logical print block;
- software-registration number;
- return reference.

Problems:
- QR is currently 25.4 mm, while current Chapter XIV says 7x7 mm.
- mandatory Chapter-XIV fields are incomplete.
- inherited `sales_type` / rate-display assumptions are DI oriented.
- offline message says upload after restoration, but the runtime model must enforce the exact 24-hour rule.

**Disposition:** REPLACE template contract, preserving clean 80mm layout.

### A4 Sales Invoice
Same general findings. Keep ERPNext money/tax authority, rebuild mandatory FBR particulars and audit states.

## 10. Test audit

Inherited runtime tests:
- `test_fbr_v1_offline_runtime.py`
- `test_fbr_v1_payload_runtime.py`
- `test_fbr_v1_snapshot_runtime.py`
- `test_fbr_v1_transport_runtime.py`
- Correction Request tests
- Submission Log tests

These currently prove clone behavior, not a Tier-1 legacy SDC contract.

**Disposition:** REPLACE protocol expectations. Reuse only harness patterns such as no-network fakes, hash checks and ERPNext fixture construction.

## 11. Security and integrity observations

Required redesign invariants:
- no credentials in request/response logs;
- no arbitrary endpoint URL accepted from operator configuration;
- no production transport without explicit authority + reviewed contract + armed gate;
- no blind retry after ambiguous external success;
- idempotency key derived from ERPNext document + fiscal attempt;
- immutable request snapshot and hashes;
- FBR response stored without changing ERPNext monetary values;
- no database mutation during source/readiness audit;
- no direct ERPNext/Frappe core patch.

## 12. Immediate blockers before protocol implementation

The following evidence is still required:

1. Client's actual FBR integration status: already-integrated/grandfathered POS versus a new/current Chapter-XIV integration.
2. Current FBR/PRAL legacy SDC technical package for that client, if legacy SDC is still the instructed route.
3. Exact current test and production machine contract.
4. Authentication/access-code scheme.
5. Request/response schemas and enums.
6. Return/credit/debit-note machine schema.
7. Offline numbering/upload behavior.
8. Closing/reporting machine schema.

Until those exist, the correct implementation is a disabled adapter + mocks, not guessed network code.
