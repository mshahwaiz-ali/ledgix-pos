# FBR V1 / Tier-1 Legacy POS — Canonical Redesign Plan

**Plan status:** REVIEW REQUIRED — no implementation authorized by this document  
**Baseline:** `main@17f81554a0eeea85e9a6868719a9b76c0dcf4e36`  
**Target app:** `apps/fbr_v1`  
**Accounting/tax authority:** ERPNext  
**Forbidden:** ERPNext/Frappe core edits, production access, real FBR calls during redesign, new git branches, guessed protocol fields/endpoints.

## 1. Canonical decision

The app name `fbr_v1` means **legacy/grandfathered Federal POS/SDC compatibility**, not “all Tier-1 retailers use V1”.

Current Chapter XIV contains a grandfathering proviso for persons already POS-integrated with FBR. Current registration/testing rollout is through a licensed integrator or PRAL. Therefore:

- `fbr_v1` may service an already-integrated legacy POS/SDC installation, or a taxpayer explicitly directed by FBR/PRAL to that interface.
- `fbr_v1` must **not** self-authorize a new taxpayer into the historical SDC protocol merely because the taxpayer is Tier-1.
- If the client is a new/current Chapter-XIV integration, use the current Digital Invoicing path (`fbr_v12`) instead.
- Until the client's regime and legacy technical packet are proven, V1 transport remains disabled and all protocol-specific fields are unresolved.

This gate is non-negotiable because it prevents us from building a technically correct implementation of the wrong legal integration regime.

## 2. Design invariants

1. **ERPNext owns accounting and tax.**
   - Sales Invoice / POS Invoice are the sale authority.
   - Sales Taxes and Charges / Item Tax Templates / ERPNext totals own tax calculation.
   - Payment Entry / POS Invoice payments own payment evidence.
   - Stock and GL remain native ERPNext.
   - FBR V1 never recalculates or posts financial amounts.

2. **FBR V1 is an adapter/evidence layer.**
   - classification metadata;
   - immutable fiscal snapshot;
   - transport;
   - FBR response/fiscal number;
   - QR/print metadata;
   - offline/reconciliation evidence;
   - event logs;
   - closing evidence.

3. **No external network call can alter submitted monetary data.**

4. **No guessed protocol.**
   Every machine field/enum/endpoint/auth rule needs authoritative evidence.

5. **No blind retry of ambiguous fiscalization.**
   If the SDC/FBR outcome may have succeeded but response is uncertain, enter reconciliation state.

6. **No production default.**
   Migration of an existing clone profile always lands in Disabled/Unresolved unless separately authorized.

7. **No destructive schema migration.**
   Old V2 fields/DocTypes may be deprecated and hidden but are not dropped as part of the cutover.

## 3. Regulatory behavior the software can already design around

### 3.1 Invoice / print
Current Chapter XIV requires:
- unique FBR invoice number, formatted `XXXXXX-DDMMYYHHMMSS-0001`;
- unique/verifiable QR at 7x7 mm;
- POS/e-invoicing software registration number;
- FBR digital-invoicing logo;
- seller name/address/registration number;
- recipient name/address/registration number;
- invoice date and tax period;
- line description and quantity;
- value exclusive of tax;
- sales-tax rate and amount;
- sales-tax withheld;
- extra tax;
- further tax;
- FED in sales-tax mode;
- total discount;
- invoice reference number;
- HS code;
- UOM;
- applicable SRO and serial.

The retail-to-general-public proviso for selected particulars must be implemented as a legal display rule, not as a tax calculation rule.

### 3.2 Real-time sales
Every taxable supply/service requires a real-time verifiable electronic invoice. Exempt-item invoices are also to pass through the integrated system.

### 3.3 Returns / corrections
Debit and credit notes are electronic and retained for six years. Adjustments, modifications and cancellations must be logged.

**ERPNext target:** use native submitted return Sales Invoice / POS Invoice linked to the original document. Do not mutate the original financial transaction to imitate an external correction.

Exact legacy SDC debit/credit/cancel machine requests remain unresolved.

### 3.4 Offline
- invoices during software/internet/power failure must be identified as offline;
- upload within 24 hours **after restoration**;
- operational/inoperative-system events must be reported within the current rule's 24-hour requirements.

The exact legacy-SDC method for issuing a fiscal number/QR while offline is unresolved. The app therefore must not invent a “temporary FBR number”.

### 3.5 Closing
Daily, weekly and monthly closing is required. We can build deterministic internal closing evidence from ERPNext and FBR logs. Any external closing call remains disabled until an authoritative request/response contract exists.

### 3.6 Retention/audit
Electronic records are retained for six years and must permit recreation of the information at original transmission. This justifies immutable snapshot/hash storage and append-only event logs.

## 4. Target architecture

```text
ERPNext Sales Invoice / POS Invoice
        |
        | before_validate
        v
ERPNext-native taxable-base inputs (only where legally/configurationally required)
        |
        | before_submit
        v
Immutable Fiscal Snapshot
  - seller/buyer identity
  - POS device identity
  - ERPNext line values
  - ERPNext tax components
  - discounts
  - payments evidence
  - source/return references
  - canonical hash
        |
        | submit commits ERPNext transaction
        v
Fiscalization Orchestrator
        |
        +--> Mock Adapter (default / tests / no network)
        |
        +--> Legacy SDC Adapter (HARD DISABLED until official contract)
                  |
                  +--> SDC/local bridge topology chosen from proven client spec
                  +--> immutable request/response audit
                  +--> FBR fiscal invoice number
        |
        v
FBR metadata on ERPNext document + append-only logs
        |
        v
Print gate / receipt
```

### 4.1 Browser vs server topology problem

Historical FBR material places the SDC on the POS computer or within the local network. A cloud-hosted Frappe server cannot assume that `localhost` refers to the cashier workstation.

Therefore Phase 3 must explicitly prove one of these topologies from the client's current FBR/PRAL package:

- **Server-reachable SDC:** Frappe backend can securely reach an authorized local/network SDC.
- **Workstation bridge:** browser/POS workstation communicates with locally installed SDC and returns signed/verified result to Frappe.
- **Other FBR/PRAL topology:** if their current package specifies it.

We will not design a browser localhost bridge, CORS bypass or agent until the official deployment topology is known.

## 5. Target Python/module layout

After approval, refactor toward:

```text
fbr_v1/
  api/
    fiscalization.py
    readiness.py
    printing.py
    operations.py
    center.py

  services/
    erpnext_identity.py
    erpnext_tax_snapshot.py
    erpnext_taxable_base.py
    fiscal_snapshot.py
    pos_identity.py
    payment_snapshot.py
    return_mapping.py
    offline.py
    closing.py
    submission_support.py

  protocol/
    __init__.py
    base.py
    mock.py
    schemas.py
    legacy_sdc.py

  setup/
    erpnext_schema.py
    component_mappings.py
    migrations.py
    install.py
    print_formats.py
```

`legacy_sdc.py` starts as a fail-closed stub. It may contain no URL, auth scheme or request body until the authoritative packet is attached to the source register.

## 6. DocType design

### 6.1 Ledgix FBR Integration Profile — MODIFY

Purpose: company-level compliance/regime and safety settings, not an API dumping ground.

Canonical fields:

**Identity**
- `company` — Link Company, unique
- `enabled`
- `integration_regime`:
  - Disabled
  - Unresolved
  - Legacy POS/SDC - Grandfathered
  - Current Chapter XIV / DI (informational; handled by fbr_v12)
- `mode`: Disabled / Test / Production / Paused
- `pause_reason`

**Authority evidence**
- `legacy_authority_status`: Unverified / Grandfathered Evidence / FBR-PRAL Directed
- `legacy_authority_reference`
- `legacy_authority_evidence` Attach
- `authority_verified_at`
- `authority_verified_by`

**Safety**
- `transport_enabled` default 0
- `production_post_armed` default 0
- `block_print_without_fiscal_result` default 1
- no configurable offline deadline

**Deprecated clone fields**
DI protocol version, business nature, sector, DI reference sync and sandbox tokens remain read-only/deprecated during migration and are removed from active UI. They are not silently repurposed.

Validation:
- Production cannot be selected without `legacy_authority_status` proven.
- `transport_enabled` cannot be set while legacy protocol contract gate is unresolved.
- Current Chapter XIV / DI regime must direct operator to `fbr_v12` and keep V1 transport off.

### 6.2 New: Ledgix FBR POS Device

Purpose: one record per registered/integrated POS/e-invoicing device/counter.

Proposed fields:
- company;
- outlet/address;
- ERPNext POS Profile;
- display label;
- FBR/POS software registration number;
- legacy POS registration number if present in official/client evidence;
- POS identification number if present in official/client evidence;
- mode Test/Production;
- transport topology enum (Unresolved / Server Reachable / Workstation Local / Other Authorized);
- onboarding/integration date;
- evidence attachment/reference;
- active flag;
- last successful fiscalization;
- last closing timestamps by period;
- current operational state.

Do **not** add MAC address, machine fingerprint, port, access code or SDC installation ID unless the authoritative machine contract requires it.

### 6.3 Ledgix FBR Submission Log — MODIFY

Make each attempt durable and audit-oriented.

Add:
- protocol/regime;
- POS device;
- attempt UUID/idempotency key;
- source snapshot hash;
- request hash;
- sanitized request JSON;
- response hash;
- sanitized response JSON;
- transport start/end;
- transport outcome: Not Attempted / Accepted / Rejected / Ambiguous / Offline Deferred;
- official FBR invoice number;
- error category/code/message;
- original/return FBR invoice reference;
- reconciliation required;
- operator/user.

Rules:
- application UI never edits completed attempt evidence;
- credentials/authorization headers never enter logs;
- request bodies are exactly reconstructable from snapshot + protocol version;
- ambiguous outcome blocks automatic retransmission.

### 6.4 New: Ledgix FBR Fiscal Event Log

Append-only system evidence:
- POS device;
- event type:
  - Startup
  - Shutdown
  - Connectivity Failure
  - Software Failure
  - Power Failure
  - Restoration
  - Offline Invoice Issued
  - Offline Upload
  - Adjustment
  - Modification
  - Cancellation Attempt
  - Debit Note
  - Credit Note
  - Closing
  - Reconciliation
  - Alert
- occurred_at;
- reference DocType/name;
- external/FBR reference;
- event JSON/hash;
- severity;
- created by.

This supports Chapter-XIV system-event and adjustment logging without touching GL.

### 6.5 New: Ledgix FBR Fiscal Closing

Fields:
- POS device;
- period type Daily / Weekly / Monthly;
- period start/end;
- count of ERPNext submitted invoices;
- count fiscalized;
- count offline pending;
- count reconciliation required;
- net/tax/grand totals derived from ERPNext;
- snapshot hash;
- status Draft / Ready / Closed Internally / External Pending / External Accepted / External Failed;
- external request/response fields reserved but inaccessible until protocol proven.

Important: an internal closing is compliance evidence, **not a claim that FBR received a machine-level closing message**.

### 6.6 Ledgix FBR Item Mapping — MODIFY

Keep:
- company/item/effective dates;
- HS code;
- UOM;
- tax basis;
- notified retail price where ERPNext tax setup requires it;
- SRO/serial where applicable.

Quarantine until proven:
- DI sale/transaction type;
- DI rate-description/reference version;
- DI reference cache relationships.

Validation remains informational/classification-only; it does not calculate tax.

### 6.7 Ledgix FBR Tax Component Mapping — KEEP/MODIFY

Map ERPNext Accounts to:
- Sales Tax
- Sales Tax Withheld at Source
- Extra Tax
- Further Tax
- FED payable in sales tax mode

All amounts come from ERPNext's calculation result.

### 6.8 Retired active DocTypes

Deprecate from V1 UI/runtime:
- Ledgix FBR Reference Data
- Ledgix FBR Sandbox Certification
- Ledgix FBR Sandbox Scenario
- Ledgix FBR Business Nature
- inherited Ledgix FBR Correction Request workflow

If data exists, preserve records and mark them legacy/deprecated. No destructive table deletion in normal migration.

## 7. ERPNext field plan

### 7.1 Sales Invoice / POS Invoice header

Preserve usable generic fields:
- `custom_ledgix_fbr_status`
- `custom_ledgix_fbr_invoice_number`
- `custom_ledgix_fbr_submitted_at`
- `custom_ledgix_fbr_error_code`
- `custom_ledgix_fbr_error_message`
- `custom_ledgix_fbr_reconciliation_required`
- `custom_ledgix_fbr_qr_code` only if its exact meaning is defined
- `custom_ledgix_fbr_generated_at`
- `custom_ledgix_fbr_submission_log`
- offline issue fields where semantics are corrected

Add neutral V1 fields:
- `custom_ledgix_fbr_pos_device`
- `custom_ledgix_fbr_regime`
- `custom_ledgix_fbr_snapshot_version`
- `custom_ledgix_fbr_snapshot_hash`
- `custom_ledgix_fbr_snapshot_json`
- `custom_ledgix_fbr_offline_mode`
- `custom_ledgix_fbr_restored_at`
- `custom_ledgix_fbr_offline_uploaded_at`
- optional latest attempt/log link.

Do not reuse `custom_ledgix_fbr_v2_snapshot_*` as if it were V1 evidence.

### 7.2 Invoice item rows

Neutral immutable line snapshot:
- snapshot version/hash/JSON as needed;
- HS/UOM/SRO evidence snapshot;
- ERPNext-derived taxable base;
- ERPNext-derived tax components.

No duplicate tax amounts calculated independently.

### 7.3 Customer

Authority order:
1. native `Customer.tax_id`;
2. linked/default billing Address;
3. customer name.

Legacy custom buyer NTN/province/address fields become migration fallbacks only and should be clearly labelled deprecated after data reconciliation.

### 7.4 Company

Authority:
- Company name;
- Company `tax_id`;
- default/linked Address;
- company logo where used.

FBR/POS software registration belongs to the FBR POS Device/profile, not Company tax accounting fields.

### 7.5 Payments

For POS Invoice use native `payments` rows.  
For Sales Invoice use native payment/accounting references.

No payment-mode enum is sent externally until the legacy SDC enum is authoritative.

## 8. Hook lifecycle

### `before_validate`
Only:
- stamp ERPNext taxable-base input for supported special tax basis;
- no FBR call;
- no external status mutation.

### `before_submit`
- validate selected POS device/profile/regime;
- capture canonical identity/tax/payment snapshot;
- hash snapshot;
- fail if internal fiscal prerequisites are inconsistent;
- no network call.

### `on_submit`
- create fiscalization intent;
- schedule/register an after-commit action or UI continuation;
- never allow an external HTTP call to corrupt/rollback ERPNext accounting transaction.

### after-commit fiscalization
For proven Test/Production legacy adapter only:
- acquire idempotency lock;
- build exact request from immutable snapshot;
- send once;
- persist exact attempt/result;
- on accepted result, stamp FBR metadata on the source doc without monetary changes;
- on definite rejection, record failure;
- on uncertain transport result, mark Reconciliation Required and block blind retry.

### `before_cancel`
- if official fiscalization exists, block destructive native cancellation by default;
- direct operator to ERPNext return / debit-credit-note flow;
- record attempted adjustment event.
- exceptions only if the authoritative legacy protocol explicitly defines and authorizes cancellation.

## 9. Returns / refund design

ERPNext path:
1. create native return Sales Invoice/POS Invoice against original;
2. preserve original row/FBR reference in snapshot;
3. ERPNext posts reversal/credit accounting;
4. V1 adapter maps to FBR debit/credit-note operation only when its schema is proven;
5. store external result as a separate attempt/log.

No 72-hour rule is coded.

Acceptance needs:
- full return;
- partial return;
- quantity/rate tax preservation;
- Third Schedule notified retail price preservation;
- original FBR invoice reference;
- exact external note type from authoritative spec.

## 10. Offline / failure / reconciliation design

State model:
- `Online Ready`
- `Offline Confirmed`
- `Offline Issued`
- `Restored - Upload Due`
- `Upload Attempted`
- `Uploaded`
- `Reconciliation Required`

Rules:
- operator/system records outage cause and start;
- offline invoice is visibly marked;
- restoration event records `restored_at`;
- due time is derived as `restored_at + 24h`;
- never derive deadline from invoice issue time;
- transport retry is allowed only where exact SDC idempotency semantics are known;
- ambiguous responses are reconciled, not resent blindly;
- failure-report evidence is stored for the legal 24-hour reporting obligation.

Unresolved:
- how legacy SDC assigns/prints FBR fiscal number while isolated;
- how batch/offline upload is invoked;
- how FBR acknowledges upload.

## 11. Printing plan

### 80mm POS receipt
Rebuild the existing format around:
- seller identity;
- recipient details where legally applicable;
- POS/software registration number;
- ERPNext item/tax/discount values;
- FBR invoice number;
- exact 7x7 mm QR;
- FBR logo;
- invoice date/time and tax period;
- HS/UOM/SRO as required;
- clear OFFLINE state if legally issued offline;
- original invoice reference for notes/returns.

The receipt must not present “Submitted” unless an authoritative success response was stored.

### A4 Sales Invoice
Same legal particulars with fuller tax-component display.

### QR
Current law states that QR is generated on the basis of the unique FBR invoice number. Exact encoded text/URI/binary payload is still unresolved. Until verified:
- keep QR generation behind a protocol function;
- test dimensions independently;
- do not declare it FBR-verifiable merely because a QR renders.

## 12. Closing plan

Create deterministic close snapshots for:
- Daily
- Weekly
- Monthly

For each POS device:
- time window;
- invoice counts;
- fiscalized/offline/reconciliation counts;
- ERPNext totals and tax components;
- hash of included source documents/attempts;
- operator/system timestamp.

When a current SDC closing endpoint/schema is supplied, the protocol adapter may add an external close operation without changing the underlying aggregate.

## 13. Migration plan

All migrations are local/test first and no-network.

### Migration A — inventory
Read-only report:
- installed V1/V12 apps;
- existing custom fields;
- existing V1 DocType rows;
- active profiles;
- any V2 snapshot hashes;
- print formats/workspace state.

### Migration B — new schema
Create:
- POS Device;
- Fiscal Event Log;
- Fiscal Closing;
- neutral V1 snapshot fields;
- profile regime/evidence fields.

### Migration C — inherited profile quarantine
For every inherited V1 profile:
- force `enabled = 0`;
- `integration_regime = Unresolved`;
- `transport_enabled = 0`;
- `production_post_armed = 0`;
- preserve old tokens/fields but remove them from active V1 behavior.

Never convert a DI token into a legacy access credential.

### Migration D — snapshot preservation
If old V2 snapshot exists:
- verify old hash;
- retain exact old JSON/hash;
- optionally copy to an explicit “legacy imported evidence” area;
- do not label it a V1 protocol snapshot;
- flag hash mismatch for manual review.

### Migration E — deprecated DocTypes
Do not drop DB tables. Remove from active workspace and block new writes where appropriate.

### Migration F — print formats
Replace only after all required context fields and test fixtures are ready.

## 14. Test strategy

### 14.1 Global no-network gate
During install/migrate/unit/integration tests:
- patch `requests`, socket and adapter transport;
- fail if any non-mock external call occurs;
- explicitly fail if known DI gateway URLs appear in V1 runtime.

### 14.2 Static contract tests
Assert:
- no `fbr_v2_*` imports in active V1 modules;
- no DI validate/post endpoints;
- no DI reference-data URL;
- no default protocol `DI API V1.12`;
- no 72-hour correction rule;
- no configurable offline upload window.

### 14.3 ERPNext integration tests
Cover:
- Sales Invoice normal;
- POS Invoice normal;
- exempt item invoice;
- registered buyer;
- general-public/unregistered buyer handling according to current law;
- mixed items/tax rows;
- extra/further/FED components;
- non-posting sales-tax-withheld evidence if configured;
- Third Schedule taxable base;
- discounts;
- cash/card/mixed ERPNext payments without inventing external enums;
- full/partial return;
- consolidated POS behavior if ERPNext creates consolidation entries;
- immutable snapshot after submit.

### 14.4 Idempotency/reconciliation tests
- duplicate UI click -> one fiscal attempt;
- worker retry while lock held;
- connection reset after request send -> Reconciliation Required;
- definite reject -> no auto-success;
- accepted response -> stable FBR number;
- same document cannot be fiscalized under two POS devices without explicit recovery path.

### 14.5 Offline tests
- outage start;
- offline invoice mark;
- restoration timestamp;
- due = restoration + 24h;
- overdue calculation;
- no blind retry;
- event log completeness.

### 14.6 Closing tests
- daily/week/month boundaries;
- counts/totals reconcile exactly to ERPNext;
- offline/unresolved attempts reported separately;
- repeat close is idempotent by POS + period.

### 14.7 Print tests
- QR CSS physical size 7x7 mm;
- FBR number format;
- mandatory fields;
- offline banner;
- return/reference fields;
- no “FBR submitted” claim without accepted response.

### 14.8 Migration tests
Start from the exact bootstrap-clone schema and prove:
- no data deletion;
- inherited profiles disabled;
- V2 tokens not reused;
- old snapshot evidence preserved;
- new DocTypes/fields idempotently created;
- repeated migrate is safe.

## 15. Acceptance gates

### Gate 0 — regime proof
**Required before protocol implementation.**
- client is confirmed as grandfathered legacy POS/SDC, or
- FBR/PRAL provides current written direction to legacy SDC.

Failure => stop V1 network work and use/review `fbr_v12`.

### Gate 1 — authoritative machine contract
Must have:
- official/current endpoint/topology;
- test/production configuration;
- auth;
- request/response schema;
- enums;
- error behavior;
- return/note behavior;
- offline behavior;
- closing behavior.

Anything missing stays unresolved and blocked.

### Gate 2 — structural cutover
- V2 DI network/reference/certification code removed from active V1;
- no network in install/migrate;
- ERPNext-native snapshot and new DocTypes pass tests;
- old data preserved.

### Gate 3 — mock protocol
- exact adapter interface;
- deterministic fixtures;
- idempotency;
- ambiguous-result handling;
- zero real network.

### Gate 4 — official test environment
Future, separately authorized by user:
- use only FBR/PRAL-issued Test credentials/config;
- capture test evidence;
- no Production traffic;
- validate FBR invoice number and QR verification behavior.

### Gate 5 — business lifecycle
- sale;
- exempt sale;
- registered/unregistered recipient cases;
- return/debit/credit note;
- offline/recovery;
- daily/weekly/monthly closing;
- six-year evidence model;
- logs.

### Gate 6 — production readiness
Separate review/change control:
- production credentials/evidence;
- production arming;
- rollback/disable plan;
- monitoring;
- operator SOP;
- backup;
- explicit user authorization.

This redesign task does **not** authorize Gate 4+ network traffic or production.

## 16. Phased implementation sequence

### Phase 0 — source and regime closure
Deliver:
- client regime evidence;
- authoritative legacy technical pack;
- final machine contract appendix.

No code if Gate 0/1 fails.

### Phase 1 — remove V2 protocol authority from V1
Code:
- retire active `fbr_v2_transport`, `fbr_reference_v2`, V2 builder/readiness/center contracts;
- add adapter interface + mock;
- retain no-network install.

Acceptance:
- V1 runtime contains no DI gateway/reference endpoint;
- tests prove no network.

### Phase 2 — ERPNext-native fiscal model
Code:
- neutral identity/tax/payment/snapshot services;
- POS Device;
- updated Integration Profile;
- Submission Log hardening;
- Fiscal Event Log;
- Fiscal Closing;
- migrations.

Acceptance:
- full ERPNext fixtures reconcile monetary values exactly;
- immutable hashes;
- no GL/stock mutation outside ERPNext.

### Phase 3 — legacy SDC adapter
Only after Gate 1:
- exact request/response models;
- exact auth;
- exact topology;
- exact test/prod configuration;
- deterministic parser;
- idempotency/reconciliation.

Acceptance:
- official fixtures pass;
- mock transport reproduces official examples;
- still no real FBR call in automated suite.

### Phase 4 — print / QR
- Chapter-XIV particulars;
- 7x7 mm QR;
- FBR number;
- POS registration;
- offline/return state.

Acceptance:
- print contract tests and manual layout proof.

### Phase 5 — offline / recovery / closing
- event state machine;
- restoration+24h deadline;
- worker/reconciliation;
- daily/week/month close snapshots;
- external close only if documented.

### Phase 6 — returns / debit-credit notes
- native ERPNext return mapping;
- authoritative SDC note request;
- original FBR reference;
- no original financial mutation.

### Phase 7 — controlled FBR Test certification
Only after explicit user approval for real Test traffic.

### Phase 8 — production deployment
Separate project step; not part of this plan approval.

## 17. Explicitly unresolved backlog

Do not code assumptions for:

1. current legacy SDC download/package/version;
2. legacy endpoint host/port/routes;
3. auth/access-code exchange;
4. exact sale request body;
5. exact response body;
6. external USIN/reference semantics;
7. payment-mode enum;
8. invoice/note-type enum;
9. return/refund/cancellation API;
10. duplicate/idempotency response behavior;
11. offline invoice fiscal-number behavior;
12. offline upload call/schema;
13. closing call/schema;
14. alert/report API;
15. exact QR encoded payload;
16. browser/server/SDC network topology for this client;
17. whether the client's new deployment is legally eligible to use legacy SDC at all.

## 18. Implementation authorization boundary

Review and approve this plan first.

Until approval:
- do not modify `apps/fbr_v1` runtime code;
- do not install/migrate the V1 app on a site;
- do not call any FBR endpoint;
- do not touch production;
- do not add a branch.

The next implementation action after approval is **Phase 0 / Gate 0 evidence closure**, not endpoint coding.
