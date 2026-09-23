# Ledgix FBR + ERPNext Native Tax Redesign Plan

**Status:** IMPLEMENTATION IN PROGRESS — ADDITIVE PHASES 0–4 STARTED; LOCAL RUNTIME CUTOVER PENDING  
**Date:** 2026-09-23  
**Repository:** mshahwaiz-ali/ledgix-pos  
**Branch / source of truth:** main  
**Baseline inspected:** 32ced967fc72578acd09312b32fdf82411dd7391  
**Production status:** FBR Production must remain NOT READY until the gates in this document are satisfied.

---

## Current implementation progress — 2026-09-23

- **Phase 0:** static dependency/retirement inventory complete.
- **Phase 1:** transaction tax authority isolated behind a temporary migration boundary; ERPNext-native runtime parity and final cutover remain pending on `ledgix-erpnext.local`.
- **Phase 2:** additive FBR V2 compliance schemas complete; no current FBR runtime has been switched to them yet.
- **Phase 3:** official v1.12 reference surface foundation implemented: core/static masters, contextual Rate/HS-UOM/SRO lookups, and live registration lookups; real authorized GET proof remains pending.
- **Phase 4:** non-persisting ERPNext-native per-line tax snapshot collector implemented against the pinned v15.121.3 engine; runtime reconciliation and transaction-lifecycle cutover remain pending.
- **Production:** remains fail-closed / not ready. No redesign work has armed Production or performed a Production invoice POST.
- **Old tax/FBR runtime:** not deleted yet. Physical retirement occurs only after native accounting parity, data migration, V2 payload cutover and regression proof.

Current phase documents:

```text
docs/fbr/FBR_PHASE0_BASELINE_INVENTORY.md
docs/fbr/FBR_PHASE1_ERPNEXT_NATIVE_TAX_CONTRACT.md
docs/fbr/FBR_PHASE2_FBR_V2_DATA_MODEL.md
docs/fbr/FBR_PHASE3_REFERENCE_SYNC_FOUNDATION.md
docs/fbr/FBR_PHASE4_ERPNEXT_NATIVE_SNAPSHOT_FOUNDATION.md
```

---

## 1. Purpose

This document is the implementation authority for redesigning the Ledgix tax and FBR integration.

The existing FBR work contains useful safety and audit concepts, but the current tax architecture still allows Ledgix to behave as a second tax engine beside ERPNext. That boundary is wrong for the current ERPNext-core product.

The redesign must establish one clear rule:

> ERPNext is the sole financial, accounting and tax-calculation authority. Ledgix is an FBR Digital Invoicing compliance, translation, certification, transport, audit and operator-workflow layer.

The objective is not to patch the existing Ledgix tax engine. The objective is to replace the active old tax/FBR model with a clean ERPNext-native design and then retire obsolete runtime code and DocTypes after migration and regression proof.

No ERPNext core code may be modified.

---

## 2. Non-negotiable architecture rules

### 2.1 One monetary authority

ERPNext must own:

- Items and Item Groups;
- Customers, Suppliers, Addresses and Contacts;
- Price Lists, Item Prices and Pricing Rules;
- Sales Invoice;
- POS Invoice;
- native returns / adjustment documents;
- Sales Taxes and Charges;
- Item Tax Templates;
- Tax Categories and Tax Rules;
- Purchase taxes;
- tax accounts;
- grand total and outstanding amount;
- GL Entry;
- Payment Entry;
- stock and Stock Ledger Entry;
- POS Opening and Closing.

Ledgix must not maintain a second monetary ledger or tax calculator.

### 2.2 Ledgix FBR responsibilities

Ledgix may own only the FBR-specific responsibilities that ERPNext does not natively provide:

- company FBR integration configuration;
- licensed-integrator configuration;
- FBR credentials;
- FBR reference-data synchronization/cache;
- ERPNext Item to FBR legal classification;
- mapping ERPNext-calculated tax components to FBR JSON fields;
- immutable compliance snapshots;
- FBR payload construction;
- FBR validation / submission transport;
- Sandbox scenario certification;
- submission logs and evidence;
- FBR invoice/reference/QR metadata;
- offline-upload workflow;
- ambiguous-POST reconciliation safeguards;
- correction workflow tracking;
- production activation/readiness controls;
- Desk UX around those functions.

### 2.3 No hidden hardcoded business setup

Client business configuration must be manageable from Desk wherever it is a business/legal choice.

Do not hardcode client:

- NTN/CNIC;
- business/legal name;
- province;
- legal address;
- HS code;
- FBR UOM;
- sale type;
- SRO schedule;
- SRO item serial;
- tax rate;
- tax account;
- Business Nature;
- Sector;
- scenario assignment;
- Production enablement.

Protocol-level defaults may be shipped by Ledgix only where they are product implementation details rather than client business choices. Sensitive endpoint overrides, if ever supported, must be System Manager only and must never expose tokens to arbitrary endpoints.

### 2.4 Never mutate accounting to make FBR pass

If ERPNext financial values do not reconcile with the FBR payload:

- stop the FBR operation;
- show the mismatch;
- correct the underlying configuration/document properly;
- never rewrite submitted accounting values or GL merely to satisfy the FBR adapter.

### 2.5 Historical evidence is preserved until safe retirement

Old DocTypes/code must not remain active authorities, but physical deletion must happen only after:

- data migration is proven;
- no current code references remain;
- no active records depend on them;
- tests prove the new path;
- archived historical evidence remains readable where legally/audit operationally required.

---

## 3. Official FBR research basis

The redesign is based on current FBR Digital Invoicing material reviewed on 2026-09-23.

### 3.1 FBR Digital Invoicing Technical Specification v1.12

Primary technical specification:

https://download1.fbr.gov.pk/Docs/20257301172130815TechnicalDocumentationforDIAPIV1.12.pdf

Important current concepts include:

- Sandbox validation endpoint;
- Sandbox post endpoint;
- Production validation endpoint;
- Production post endpoint;
- Bearer-token authorization;
- Sale Invoice payload;
- official reference APIs;
- Province;
- Document Type;
- Transaction / Sale Type;
- UOM;
- Sale Type to Rate;
- HS Code to UOM;
- SRO Schedule;
- SRO Item;
- taxpayer registration/status services;
- scenarioId in Sandbox testing;
- FBR-generated invoice identity;
- QR requirements;
- validationResponse and line-level invoiceStatuses.

### 3.2 FBR Digital Invoicing onboarding / user manuals

Reviewed onboarding material includes:

https://download1.fbr.gov.pk/Docs/20256251162757102DIUserManualV1.4.pdf

and:

https://download1.fbr.gov.pk/Docs/20254171643756444DI-User-Manual.pdf

Important onboarding concepts include:

- licensed integrator;
- ERP/System Provider;
- software type/version;
- technical contact;
- Business Nature;
- Sector;
- Sandbox token;
- server/IP-whitelisting information where applicable;
- required scenario testing;
- successful completion of applicable scenarios before Production activation/token flow.

### 3.3 Current FBR FAQ

https://fbr.gov.pk/faqs/173967/173969

Important product implications include:

- ERP/POS integration is through the licensed-integrator framework;
- a single HS code can participate in different legal sale/purchase types and tax treatment;
- FBR legal classification cannot be reduced to a single numeric rate stored on an Item.

### 3.4 Offline invoice rule

Relevant Sales Tax rule material reviewed:

https://download1.fbr.gov.pk/SROs/2025129141598258SRO69%28I%292025.pdf

The architecture must distinguish genuine offline issuance from an ambiguous network POST outcome. Offline documents require a controlled upload lifecycle after connectivity restoration; they must not be treated as blind retries.

### 3.5 Correction workflow

Sales Tax General Order #01 of 2026:

https://download1.fbr.gov.pk/Docs/2026331133557466STGO01of2026.pdf

The current documented correction model includes a 72-hour Board-system window for bona fide mistakes and Commissioner approval after that window. Ledgix may track this workflow but must not invent an undocumented correction API.

### 3.6 Return/note terminology requires Sandbox confirmation

Current FBR material contains inconsistent terminology across technical/reference and broader Sales Tax material around Debit Notes and Credit Notes.

Therefore the redesign must not permanently encode:

    if return:
        invoiceType = "Credit Note"

The accepted outbound note contract must be proven against current FBR/PRAL Sandbox and the selected licensed integrator before Production.

---

## 4. Confirmed problems in the current repository

The current repository already moved transaction authority to ERPNext, which is good. However, the tax/FBR boundary still contains old architecture.

### 4.1 Custom Ledgix tax engine remains active

Current file:

    apps/ledgix_saas/api/taxation.py

This file explicitly implements a Ledgix tax engine, including:

- Ledgix Tax Profile;
- Ledgix Tax Category;
- Ledgix Tax Rate;
- Ledgix Item Tax Profile;
- effective rate resolution;
- inclusive/exclusive tax calculation;
- immutable tax snapshot generation.

This must not remain the active financial/tax authority after the redesign.

### 4.2 ERPNext tax rows are currently generated by Ledgix calculations

Current file:

    apps/ledgix_saas/setup/erpnext_tax_foundation.py

Although ERPNext ultimately owns the invoice and GL, the current adapter calculates tax components from Ledgix configuration and writes managed ERPNext tax rows.

That means the practical calculation flow is still:

    Ledgix tax configuration
        -> Ledgix calculation
        -> ERPNext tax rows
        -> ERPNext totals / GL

Target flow must become:

    ERPNext native tax configuration
        -> ERPNext calculation
        -> ERPNext totals / GL
        -> Ledgix read-only FBR translation/snapshot

### 4.3 Duplicate tax masters

Current active custom DocTypes include:

- Ledgix Tax Profile;
- Ledgix Tax Category;
- Ledgix Tax Rate;
- Ledgix Item Tax Profile.

These mix financial tax authority with FBR classification.

They must be replaced or retired from active new-business operation.

### 4.4 Item FBR classification is mixed with tax calculation

Current Ledgix Item Tax Profile stores both:

FBR/legal metadata:

- ERPNext Item;
- HS Code;
- FBR UOM;
- Sales Type;
- rate description;
- SRO fields;
- scenario ID;

and monetary configuration:

- tax category;
- taxable flag;
- default tax rate;
- extra tax per unit;
- further tax per unit;
- FED per unit;
- sales-tax-withheld per unit.

These responsibilities must be separated.

### 4.5 Sandbox scenario is modeled at the wrong level

Current scenario_id is stored on item/category mapping.

FBR Sandbox certification is driven by the taxpayer's Business Nature/Sector and required test scenarios. Scenario execution/evidence belongs to certification, not as a permanent production Item attribute.

### 4.6 Seller legal identity is duplicated

Current Ledgix FBR Settings stores separate seller identity fields such as:

- seller NTN/CNIC;
- seller business name;
- seller province;
- seller address.

The redesign must prefer ERPNext Company / legal address / tax identity wherever standard ERPNext fields can represent the information, with FBR-only extensions only where ERPNext lacks the required legal field.

### 4.7 Current integration configuration is global

Ledgix FBR Settings is a Single DocType.

ERPNext transactions are Company-specific. The new FBR profile must therefore be Company-scoped so multiple legal companies cannot accidentally share FBR identity or credentials.

### 4.8 Production-readiness proof is too generic

Current activation logic mainly proves successful Sandbox validate/post examples for Sales Invoice, POS Invoice and optionally returns.

The redesigned gate must prove the actual required FBR Sandbox scenarios for the configured Business Nature/Sector, not merely one generic invoice.

### 4.9 Offline and ambiguous network outcomes are not fully separated

Current code correctly avoids blind Production retransmission after an ambiguous POST, but true offline issuance/upload is not implemented as a complete separate workflow.

These states must be modeled separately.

### 4.10 Return payload is currently hardcoded as Credit Note

Current native payload code uses Credit Note for ERPNext returns.

That must be replaced with a current, Sandbox-proven FBR note mapping before Production.

---

## 5. Existing concepts that should be preserved

The redesign is not a rewrite of the entire POS.

Keep and improve these existing ideas:

### 5.1 ERPNext native source authority

New FBR activity must continue to originate from:

- ERPNext Sales Invoice;
- ERPNext POS Invoice;
- supported native ERPNext return/adjustment document.

Frozen Ledgix Sale / Ledgix Sales Return must never regain new-business authority.

### 5.2 Consolidated POS duplicate protection

ERPNext POS Closing can generate accounting consolidation Sales Invoices.

The source POS Invoices must remain the FBR legal sources. The consolidation invoice must never become a second FBR submission.

### 5.3 Immutable compliance snapshots

Keep the concept, but rebuild the source.

Snapshot values must come from:

- the authoritative submitted/draft ERPNext invoice;
- its native taxes;
- the FBR classification/reference values that were effective at that time.

The snapshot must not become a second calculator.

### 5.4 Submission logs

Keep Ledgix FBR Submission Log or evolve it without losing history.

Every validation/submission attempt should retain:

- source doctype/name;
- environment;
- operation;
- safe request snapshot;
- safe response;
- FBR status;
- error code/message;
- official reference;
- timestamps;
- operator;
- reconciliation/offline context.

Secrets must never be logged.

### 5.5 Production arming interlock

Keep the explicit Production safety interlock.

Production must never become active just because a site was installed, migrated, restored or copied.

### 5.6 Ambiguous POST reconciliation

Keep the fail-closed Reconciliation Required concept.

If Ledgix cannot prove whether FBR received a Production POST:

- do not retransmit automatically;
- do not treat it as ordinary Failed;
- require explicit reconciliation before any retry decision.

---

## 6. Target architecture

Final authority model:

    ERPNext Items / Customers / Addresses / Company
                        |
                        v
    ERPNext Tax Category / Tax Rule / Templates
                        |
                        v
           ERPNext Sales / POS Invoice
                        |
             ERPNext taxes + totals + GL
                        |
                        v
        Ledgix immutable FBR snapshot
                        |
          +-------------+-------------+
          |                           |
          v                           v
    FBR Item Classification     FBR Integration Profile
          |                           |
          +-------------+-------------+
                        |
                        v
              FBR Payload Adapter
                        |
                        v
                FBR / PRAL / LI
                        |
                        v
       response + official reference + audit

There must be:

- one invoice;
- one tax calculation;
- one accounting result;
- one stock result;
- one FBR adapter.

---

## 7. ERPNext-native tax design

### 7.1 Native masters

Use ERPNext native configuration for financial tax behavior:

- Account;
- Tax Category;
- Sales Taxes and Charges Template;
- Purchase Taxes and Charges Template;
- Tax Rule;
- Item Tax Template;
- Item / Item Group assignments;
- Customer / Address tax classification where relevant.

### 7.2 Tax accounts

Tax accounts must be selected in native ERPNext tax templates or other supported native tax configuration.

Ledgix must not maintain a parallel company account mapping solely to calculate invoice tax.

Examples that may be required for a client include:

- Output Sales Tax;
- Input Sales Tax;
- Further Tax;
- Extra Tax;
- FED;
- any legally verified withholding account treatment.

Exact accounts are client/company configuration, not global Ledgix constants.

### 7.3 Standard / zero / exempt / reduced / special treatment

The final client setup must support, where applicable:

- standard-rate taxable items;
- zero-rated items;
- exempt items;
- reduced-rate items;
- Third Schedule / notified retail value cases;
- Further Tax;
- Extra Tax;
- FED;
- tax-inclusive prices;
- tax-exclusive prices.

Native ERPNext behavior must be proven first.

If a special legal case cannot be represented safely through native ERPNext tax mechanisms, stop and document the gap before adding any custom calculation. Do not silently restore the old Ledgix tax engine.

---

## 8. New FBR data model

Names below are working names; implementation may use equivalent maintainable names, but the separation of responsibility is mandatory.

### 8.1 FBR Integration Profile

Company-scoped configuration.

Suggested fields / sections:

#### Identity

- ERPNext Company;
- enabled;
- provider / licensed integrator;
- integration protocol/version;
- taxpayer registration identifiers not already canonical in Company;
- software registration number;
- ERP/System Provider;
- software name/version;
- technical contact.

#### Onboarding

- Business Nature child rows;
- Sector;
- onboarding status;
- IP/server/whitelist status;
- activation notes/evidence.

#### Credentials

- Sandbox token — Password field;
- Production token — Password field;
- token configured booleans;
- credentials must never be returned to normal browser APIs/logs.

#### Controls

- mode: Disabled / Sandbox / Production / Paused;
- submission policy;
- Production armed;
- offline mode policy;
- reconciliation safety controls.

The design should avoid arbitrary client-editable transport URLs unless a legitimate multi-integrator architecture requires them.

### 8.2 FBR Item Mapping

One current ERPNext Item to FBR classification mapping.

It should contain only compliance/classification fields, for example:

- ERPNext Item;
- HS Code;
- FBR UOM;
- FBR Sale/Transaction Type;
- FBR rate/reference identifier if required for compliance translation;
- SRO Schedule;
- SRO Item Serial;
- Third Schedule / notified-value metadata where required;
- effective dates/version;
- needs review;
- source/reference-data version;
- active.

It must not be a tax-rate calculator.

Remove from the new model:

- Ledgix Tax Category as financial authority;
- default tax rate calculation;
- Extra Tax per unit calculation;
- Further Tax per unit calculation;
- FED per unit calculation;
- tax-inclusive calculation.

### 8.3 FBR Tax Component Mapping

Purpose:

Map amounts already calculated by ERPNext into FBR payload component names.

Example concept:

    ERPNext tax/account/template component
        -> FBR field

Possible FBR fields include:

- salesTaxApplicable;
- salesTaxWithheldAtSource;
- extraTax;
- furtherTax;
- fedPayable.

This mapping must not calculate the amount.

It reads/reconciles the authoritative ERPNext amount.

### 8.4 FBR Reference Data

Create controlled cache/master data for official FBR reference APIs where practical.

Reference families include:

- Province;
- Document Type;
- Transaction/Sale Type;
- UOM;
- Rate;
- HS-UOM relationship;
- SRO Schedule;
- SRO Item;
- Registration Type/status metadata where appropriate.

Each synchronized record should retain:

- FBR identifier;
- description;
- effective/source metadata where available;
- fetched timestamp;
- source endpoint/version;
- active/stale state.

Operators should select official values rather than freely typing legal strings whenever an FBR reference API exists.

### 8.5 FBR Sandbox Certification

Certification should be a first-class workflow.

Suggested parent:

    FBR Sandbox Certification

Linked to:

- Company;
- FBR Integration Profile;
- Business Nature(s);
- Sector;
- certification start/completion;
- status.

Child rows:

- Scenario ID;
- description;
- required;
- source rule/profile;
- representative ERPNext document;
- validate result;
- post result;
- FBR response/reference;
- evidence log;
- completed at.

Scenario ID must be certification context, not permanent production Item tax configuration.

### 8.6 FBR Submission Log

Retain/evolve the existing DocType.

New log design must distinguish:

- Validate;
- Submit/Post;
- Offline upload;
- reconciliation action;
- correction evidence where relevant.

Environment:

- Sandbox;
- Production.

Outcome:

- Pending;
- Validated;
- Submitted/Accepted;
- Known Rejected/Failed;
- Offline Pending;
- Reconciliation Required;
- Paused / Not Required where appropriate.

---

## 9. Desk-first configuration

Normal client setup must be possible from Desk.

### 9.1 Tax setup surface

Do not create duplicate custom CRUD for native tax masters.

Provide links/readiness diagnostics to:

- Chart of Accounts;
- Tax Category;
- Sales Taxes and Charges Template;
- Purchase Taxes and Charges Template;
- Tax Rule;
- Item Tax Template;
- Item;
- Customer/Address where applicable.

### 9.2 FBR integration surface

Desk must support:

- Company selection;
- licensed integrator/provider;
- onboarding identity;
- Business Nature;
- Sector;
- software details;
- server/IP-whitelist status;
- Sandbox credential;
- Production credential;
- environment controls;
- Production arming.

### 9.3 Product compliance surface

Desk must support:

- unmapped Items;
- missing HS code;
- invalid/missing UOM;
- missing Sale Type;
- SRO requirements;
- Third Schedule requirements;
- stale reference data;
- bulk review where safe;
- direct link to ERPNext Item.

### 9.4 Sandbox certification surface

Desk should show:

- required scenarios;
- pending/successful scenarios;
- selected representative invoice;
- payload preview;
- Validate action;
- Sandbox POST action;
- persisted FBR response evidence;
- certification completion state.

### 9.5 Live FBR operations

Operators should see:

- Not Submitted / Not Required;
- Ready;
- Submitted/Accepted;
- Failed;
- Offline Pending;
- Reconciliation Required;
- correction required;
- latest FBR log/reference.

---

## 10. Payload Builder V2

The current payload code must be replaced/refactored so it is a translator, not a tax engine.

### 10.1 Input authority

Payload input must come from:

- ERPNext source invoice;
- authoritative ERPNext invoice items;
- authoritative ERPNext tax rows/totals;
- Customer and Address;
- Company / legal seller identity;
- immutable FBR classification snapshot;
- FBR Integration Profile;
- relevant FBR reference values.

### 10.2 No monetary re-calculation

The payload adapter may:

- normalize;
- map;
- aggregate ERPNext-authoritative amounts where the FBR schema requires a different grouping;
- round according to a documented transport rule only if reconciliation remains exact/within approved tolerance.

It must not independently derive the official invoice tax from a custom rate table.

### 10.3 Mandatory reconciliation

Before FBR network traffic:

- FBR item totals must reconcile to ERPNext;
- FBR tax component totals must reconcile to ERPNext;
- FBR invoice total must reconcile to ERPNext;
- no unclassified authoritative ERPNext tax amount may disappear;
- no FBR tax amount may be invented without an ERPNext financial source unless the field is explicitly non-financial metadata.

Mismatch must fail closed with a clear diagnostic.

### 10.4 Snapshot timing

FBR classification and mapped tax meaning must be frozen before/at submission so later master-data changes cannot silently rewrite historical payloads.

The snapshot must record source/version provenance.

---

## 11. FBR transport

### 11.1 Keep guarded endpoint behavior

The existing v1.12 endpoint direction currently aligns with FBR technical material and should not be changed casually.

Sandbox and Production must remain clearly separated.

### 11.2 Token handling

Tokens must:

- use Frappe Password handling;
- never appear in logs;
- never be returned to browser APIs;
- never be stored in fixtures;
- never be committed;
- never be written into generated evidence.

### 11.3 Provider abstraction

If Ledgix must support multiple licensed integrators, transport should be adapter-based.

Example boundary:

    FBRTransportProvider
        -> PRAL / direct-current-FBR-compatible adapter
        -> future licensed-integrator adapter

Do not spread provider-specific endpoint logic across UI and business code.

---

## 12. Sandbox certification redesign

Production readiness must be scenario-based.

Flow:

    Company FBR profile
        -> Business Nature(s)
        -> Sector
        -> required Sandbox scenarios
        -> representative ERPNext docs
        -> Validate
        -> Sandbox POST
        -> persisted successful evidence
        -> all required scenarios green
        -> Production credential/activation prerequisites

A generic single Sales Invoice success must not be treated as full certification if FBR requires multiple scenarios.

No mock result can satisfy the real client certification gate.

---

## 13. Offline invoicing vs ambiguous POST

These must be separate state machines.

### 13.1 Known offline state

Condition:

Connectivity/FBR transport is known unavailable before attempting the live POST.

Required model:

    Known Offline
        -> issue/mark allowed offline invoice according to current rule
        -> Offline Pending
        -> record issued-at / connectivity state
        -> connectivity restored
        -> controlled upload
        -> accepted or known rejected
        -> deadline monitoring/evidence

The implementation must use the current official upload window/rule confirmed for the client's integration.

Offline upload must be durable and auditable.

### 13.2 Ambiguous Production POST

Condition:

A Production request may have left Ledgix, but the response is lost/unknown.

Required model:

    POST attempted
        -> unknown outcome
        -> Reconciliation Required
        -> no automatic retransmission
        -> external FBR/PRAL/LI reconciliation
        -> explicit evidence
        -> only then determine next legal action

This existing safety principle must be preserved.

---

## 14. Returns / Debit Notes / Credit Notes

ERPNext remains the commercial/accounting authority for the return/adjustment.

The FBR adapter must determine the current legally accepted FBR note contract from:

- current FBR reference/document-type behavior;
- current FBR technical rules;
- actual Sandbox response;
- selected licensed integrator/PRAL confirmation where material.

Do not keep a hardcoded Credit Note assumption.

Requirements to preserve/prove include:

- link to original ERPNext document;
- link/reference to original official FBR invoice number where required;
- reason;
- applicable time-window validation, including the current documented 180-day rule where legally applicable;
- no destructive cancellation of an already accepted official invoice where the correct legal flow is a note/correction.

---

## 15. Correction workflow

The existing Ledgix FBR Correction Request concept can be retained but must be reviewed and aligned with current official procedure.

It is a tracking/evidence workflow, not an invented API.

Track:

- source ERPNext invoice;
- FBR invoice number;
- FBR generation/submission time;
- requested correction type;
- bona fide reason;
- 72-hour deadline;
- Board/PRAL/LI reference;
- Commissioner approval reference when required;
- final result/evidence.

Do not mark a correction complete without external evidence.

---

## 16. Print compliance redesign

Printing must be reviewed after real Sandbox/provider confirmation.

Keep the good existing design principle:

- print from the same ERPNext invoice;
- show the official FBR invoice/reference only after accepted response;
- generate QR from the accepted official reference/data;
- do not fabricate QR/invoice identity.

Review and finalize:

- official Digital Invoicing logo/image;
- QR data/content;
- QR physical size;
- software/POS registration number;
- seller legal identity;
- buyer legal identity;
- HS/Sale Type display if required;
- note/return presentation;
- original invoice reference;
- offline invoice marking;
- correction/reprint behavior.

If official FBR documents conflict on presentation details, Production print format must follow the current requirement confirmed through FBR/PRAL/licensed-integrator certification.

---

## 17. Old code / DocType retirement policy

The desired final state is that old conflicting tax/FBR runtime does not remain active.

However, removal must be controlled.

### 17.1 Retire from active runtime

The following current components are redesign targets and must no longer be active new-business tax authorities:

#### Python

- apps/ledgix_saas/api/taxation.py
- calculation portions of apps/ledgix_saas/setup/erpnext_tax_foundation.py
- old tax CRUD/calculation portions of apps/ledgix_saas/api/tax_center.py
- legacy sale/return payload builders in apps/ledgix_saas/api/fbr_payload.py
- legacy submission paths in apps/ledgix_saas/api/fbr_submission.py after all compatibility dependencies are removed.

#### Old tax masters

- Ledgix Tax Profile;
- Ledgix Tax Category;
- Ledgix Tax Rate;
- current mixed-responsibility Ledgix Item Tax Profile.

### 17.2 Replace rather than blindly delete

Replacement must happen in this order:

1. build/prove native ERPNext tax configuration;
2. create new FBR-only mappings/profile/reference model;
3. migrate needed FBR classification from old mapping;
4. switch runtime reads to new model;
5. prove payload/accounting parity;
6. freeze old records;
7. remove UI links and write permissions;
8. remove runtime imports/hooks;
9. run full regression/search for references;
10. only then decide physical DocType/source deletion.

### 17.3 Historical compatibility

If old tables contain historical legal/audit information that cannot safely be discarded:

- retain them read-only under legacy/archive naming/boundary;
- ensure current runtime cannot use them for new invoices;
- document why they remain.

The target is zero conflict, not reckless data loss.

---

## 18. File-level implementation direction

### 18.1 Files expected to be heavily rewritten/refactored

- apps/ledgix_saas/api/fbr_native.py
- apps/ledgix_saas/api/fbr_payload.py
- apps/ledgix_saas/api/fbr_settings.py
- apps/ledgix_saas/api/fbr_activation.py
- apps/ledgix_saas/api/fbr_reference.py
- apps/ledgix_saas/api/tax_center.py
- apps/ledgix_saas/public/js/ledgix_fbr_native_center.js
- apps/ledgix_saas/ledgix/page/ledgix_tax_center/ledgix_tax_center.js
- FBR print helpers/formats as required.

### 18.2 Files/components to retire from active tax authority

- apps/ledgix_saas/api/taxation.py
- current calculation authority in apps/ledgix_saas/setup/erpnext_tax_foundation.py
- current Ledgix tax category/rate/profile runtime.

### 18.3 Concepts to preserve

- ERPNext native invoice authority;
- ERPNext-native FBR source hooks;
- duplicate POS consolidation exclusion;
- FBR Submission Log;
- immutable snapshot concept;
- Production arming;
- Reconciliation Required;
- token secrecy;
- external correction tracking.

---

## 19. Implementation phases

Implementation must be done in coherent phases with a gate after each phase.

Do not delete the old path at the start.

### Phase 0 — Baseline and freeze

Goal:

Capture the exact current FBR/tax dependency graph and prevent accidental Production activation during redesign.

Work:

- inventory all imports/hooks/JS RPCs/DocTypes/custom fields/fixtures/tests related to FBR and tax;
- document current data counts;
- identify legacy historical data that must survive;
- identify all current Ledgix Tax Profile/Category/Rate/Item Profile consumers;
- keep Production FBR disabled/unarmed.

Gate:

- dependency map complete;
- no unknown runtime consumer of old tax model;
- baseline regression recorded.

### Phase 1 — ERPNext-native tax authority

Goal:

Prove that normal financial tax calculation is entirely native ERPNext.

Work:

- configure/standardize native tax accounts;
- native Tax Categories;
- Sales Taxes and Charges Templates;
- Purchase Taxes and Charges Templates;
- Tax Rules;
- Item Tax Templates;
- prove standard, inclusive/exclusive, zero/exempt/reduced and applicable special cases;
- prove Sales Invoice and POS Invoice totals/GL without Ledgix tax calculations.

Gate:

- ERPNext totals/GL correct;
- old Ledgix tax calculator not required for proven cases;
- no ERPNext core edit.

### Phase 2 — FBR model V2

Goal:

Introduce clean FBR-only masters/config.

Work:

- Company-scoped FBR Integration Profile;
- FBR Item Mapping;
- FBR Tax Component Mapping;
- FBR Reference Data;
- FBR Sandbox Certification;
- evolve Submission Log if required;
- add roles/permissions;
- Desk forms/lists.

Gate:

- no new monetary tax authority introduced;
- secrets protected;
- company separation proven.

### Phase 3 — Reference API synchronization

Goal:

Replace free-text legal/reference values with official controlled values where APIs exist.

Work:

- Province;
- Document Type;
- Transaction/Sale Type;
- UOM;
- Sale Type to Rate;
- HS-UOM;
- SRO Schedule;
- SRO Item;
- relevant registration/status references.

Gate:

- sync is authenticated and safe;
- stale/reference failure behavior defined;
- FBR item mapping can be completed from official reference data.

### Phase 4 — Payload Builder V2

Goal:

FBR payload is a translation of the ERPNext invoice, not a second tax calculation.

Work:

- new snapshot builder from ERPNext-native values;
- tax-component mapping;
- strict amount reconciliation;
- Sale Invoice payload;
- POS Invoice payload;
- supported note/return payload after current contract confirmation;
- remove new-business dependency on old Ledgix tax snapshots.

Gate:

- same ERPNext invoice produces deterministic immutable payload;
- no independent tax calculation;
- mismatches fail closed.

### Phase 5 — Desk FBR onboarding + setup

Goal:

Normal client setup is Desk-first.

Work:

- integration profile UX;
- tax-readiness links/diagnostics;
- product-compliance mapping;
- token entry;
- onboarding fields;
- provider/LI;
- Business Nature/Sector;
- reference sync status;
- Sandbox certification workspace.

Gate:

A competent operator can configure the client without editing source code or using an internal shell setup script for normal product configuration.

### Phase 6 — Real Sandbox certification

Goal:

Prove the actual client integration using real assigned credentials and scenarios.

Work:

- configure actual legal identity;
- configure actual provider/LI;
- confirm IP-whitelist/server requirements;
- sync references;
- map real representative Items;
- execute every required Sandbox scenario;
- persist real validate/post evidence;
- prove note/return behavior where required.

Gate:

- all required scenarios green;
- no fabricated evidence;
- unresolved protocol ambiguity documented/closed before Production.

### Phase 7 — Offline + reconciliation lifecycle

Goal:

Implement legally safe failure handling.

Work:

- known-offline detection/state;
- offline invoice marking;
- durable offline queue;
- restore/connectivity workflow;
- deadline monitoring;
- controlled upload;
- preserve ambiguous POST -> Reconciliation Required path;
- prevent blind retry.

Gate:

Test known rejection, known offline, timeout-before-send where detectable, ambiguous-after-send, recovery, and duplicate prevention.

### Phase 8 — Printing + corrections + note flow

Goal:

Finalize legal output/workflows.

Work:

- official logo;
- QR;
- registration number;
- accepted FBR reference;
- note/return print;
- offline print marker;
- correction tracking;
- 72-hour / Commissioner path;
- reprint behavior.

Gate:

Print artifacts and correction workflow match current confirmed requirements.

### Phase 9 — Old runtime retirement

Goal:

Remove conflicts.

Work:

- migrate remaining necessary FBR classification;
- freeze/deprecate old custom tax DocTypes;
- remove old UI;
- remove old imports/hooks/RPCs;
- remove calculation code;
- remove compatibility code that is no longer required;
- physical source/DocType deletion only after a separate explicit dependency/data proof.

Gate:

Repository search and runtime tests prove current invoices/FBR cannot use the old tax engine.

### Phase 10 — Production activation

Goal:

Controlled real Production switch.

Required prerequisites:

- native ERPNext tax tests green;
- FBR mappings green;
- official reference sync green;
- all required Sandbox scenarios proven;
- real Sandbox responses/evidence retained;
- Production credential present;
- print compliance verified;
- offline lifecycle verified;
- reconciliation lifecycle verified;
- no unresolved Reconciliation Required;
- fresh verified backup;
- exact approved release SHA;
- explicit authorized Production arm.

First live Production submission must be observed and evidenced.

---

## 20. Required test matrix

The final implementation must include automated/runtime coverage for at least:

### Native tax/accounting

- standard taxable sale;
- tax-inclusive sale;
- tax-exclusive sale;
- zero-rated item;
- exempt item;
- reduced-rate case where configured;
- mixed item tax treatment;
- applicable Third Schedule/notified value;
- applicable Further Tax;
- applicable Extra Tax;
- applicable FED;
- purchase-side tax where in client scope;
- GL balance;
- POS Invoice;
- Sales Invoice;
- return/adjustment accounting.

### FBR classification/reference

- missing HS code;
- invalid HS/UOM pairing;
- missing Sale Type;
- stale/missing reference data;
- required SRO missing;
- mapping version frozen on invoice;
- Company A cannot use Company B credentials/profile.

### Payload

- ERPNext tax -> FBR component reconciliation;
- totals reconciliation;
- deterministic immutable payload;
- registered buyer;
- unregistered buyer;
- POS source;
- Sales Invoice source;
- consolidated POS Sales Invoice excluded;
- return/note source;
- original FBR reference.

### Transport

- Sandbox validate success;
- Sandbox known rejection;
- Sandbox post success;
- Production not armed;
- Production armed;
- token missing;
- HTTP known rejection;
- network failure before known acceptance;
- ambiguous Production response;
- duplicate-submit prevention.

### Offline

- known offline issuance;
- Offline Pending persistence;
- restore/upload;
- deadline tracking;
- duplicate prevention;
- offline queue survives worker/restart as designed;
- offline flow never reuses ambiguous-POST retry logic.

### Certification

- required scenarios derived from profile;
- incomplete scenario set blocks Production readiness;
- complete real evidence permits next gate;
- mock evidence cannot satisfy real Production gate.

### Security

- token not logged;
- token not returned to browser;
- token not in evidence;
- permissions enforced;
- Production enablement not granted to normal cashier.

---

## 21. Migration strategy for existing sites

Existing sites may already contain Ledgix tax mappings/snapshots.

Migration must be additive and auditable.

### 21.1 Read-only inventory first

Before writes, capture:

- old tax profiles;
- categories;
- rates;
- item mappings;
- Company tax account links;
- FBR Settings;
- current invoice FBR snapshots;
- Submission Logs;
- correction records.

### 21.2 Classification migration

Where old Ledgix Item Tax Profile contains useful FBR legal metadata:

- map to ERPNext Item;
- carry forward only verified FBR classification values;
- do not automatically treat the old monetary rate as new ERPNext tax configuration;
- mark uncertain mappings Needs Review.

### 21.3 Financial configuration migration

ERPNext-native tax templates/rules/accounts must be configured/proven explicitly.

Do not silently recreate every old Ledgix Tax Rate as an ERPNext rule without review.

### 21.4 Historical submitted invoices

Do not rewrite historical submitted invoices or their existing legal snapshots merely because the new architecture exists.

New architecture applies to new/approved future transactions after cutover.

Historical FBR evidence remains immutable/read-only.

---

## 22. Documentation work during implementation

This plan becomes the redesign authority until implementation is complete.

During implementation update or replace:

- docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md
- docs/fbr/FBR_PRODUCTION_CHECKLIST.md
- docs/production/fbr_sandbox_production_activation.md
- docs/architecture/CURRENT_ARCHITECTURE.md
- root README.md FBR status/index

Deprecated compatibility documents should remain clearly historical or be removed only when references no longer require them:

- docs/fbr/FBR_TAX_LAYER.md
- docs/fbr/FBR_TAX_MODULE.md

Historical migration documents under docs/archive/migration remain historical evidence and must not be rewritten as if they were current instructions.

---

## 23. Definition of done

The redesign is complete only when all of the following are true:

### Authority

- ERPNext is the only monetary tax calculation authority.
- Ledgix cannot independently determine official invoice tax from Ledgix tax-rate masters.
- No duplicate financial tax master is required for normal operation.

### FBR model

- Company-scoped FBR profile exists.
- official/reference data is controlled and synchronized where supported.
- FBR Item Mapping contains compliance classification, not a shadow tax engine.
- Sandbox scenario certification is modeled separately from Items.

### Runtime

- Sales Invoice and POS Invoice payloads are built from ERPNext-authoritative documents.
- payload totals reconcile to ERPNext.
- immutable compliance snapshots remain available.
- Production duplicate/reconciliation safety remains intact.
- true offline workflow is implemented separately.
- note/return protocol is Sandbox-proven.

### Desk UX

- normal business setup can be completed in Desk.
- no source-code edit is needed for client tax/FBR configuration.
- shell scripts are optional operator/diagnostic tools, not the normal product configuration path.

### Retirement

- old Ledgix tax engine is not used by current invoices.
- old Ledgix tax UI is removed from active product flow.
- obsolete code/imports/hooks are removed after proof.
- historical data required for audit remains safe/read-only.
- no conflicting old and new tax engines run together.

### Release

- full regression is green;
- real required Sandbox scenarios are green;
- Production remains fail-closed until explicit approved activation.

---

## 24. Immediate next step

Do not start by deleting old tax/FBR files.

The next implementation task is **Phase 0 — Baseline and Freeze**:

1. inspect every current FBR/tax dependency in main;
2. produce a precise keep / rewrite / migrate / retire / delete-later inventory;
3. inspect current ERPNext-native tax configuration hooks and transaction creation paths;
4. identify historical data dependencies;
5. add a regression gate that proves the current baseline before replacement begins.

Only after that baseline is complete should Phase 1 replace the financial tax authority with native ERPNext configuration.

---

## 25. Final target statement

Ledgix must finish with this boundary:

> ERPNext calculates and accounts. Ledgix classifies for FBR, translates the authoritative ERPNext invoice, certifies it, transmits it safely, and preserves the legal/audit evidence.

No old Ledgix tax engine should remain capable of conflicting with that model after cutover.
