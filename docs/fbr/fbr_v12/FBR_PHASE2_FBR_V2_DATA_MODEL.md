# FBR Redesign — Phase 2 FBR-Only Data Model

**Status:** ADDITIVE SCHEMA COMPLETE — RUNTIME CUTOVER / MIGRATION NOT YET PERFORMED  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`  
**Parent plan:** `docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`  
**Phase 0:** `docs/fbr/FBR_PHASE0_BASELINE_INVENTORY.md`  
**Phase 1:** `docs/fbr/FBR_PHASE1_ERPNEXT_NATIVE_TAX_CONTRACT.md`

---

## 1. Purpose

Phase 2 introduces the clean FBR compliance data model that will replace the old mixed tax/FBR model.

The model is deliberately additive and currently inactive.

It does **not**:

- switch FBR runtime away from `Ledgix FBR Settings`;
- migrate tokens;
- migrate old item mappings;
- change invoice tax calculation;
- enable FBR Production;
- submit anything to FBR;
- delete old DocTypes;
- change existing historical invoices.

This makes it safe to add before the Phase 1 local accounting parity gate is executed.

---

## 2. Boundary

Phase 2 follows one strict separation:

```text
ERPNext
  = monetary tax calculation + tax accounts + totals + GL

Ledgix FBR V2
  = legal classification + provider/onboarding config
    + protocol/reference data + certification evidence
    + mapping authoritative ERPNext tax rows to FBR fields
```

The new FBR model must never become another financial tax engine.

---

## 3. New DocTypes

### 3.1 Ledgix FBR Integration Profile

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_integration_profile/`

Purpose:

One FBR integration profile per ERPNext Company.

Key fields:

- ERPNext Company;
- Enabled;
- Mode;
- Submit Trigger;
- provider type;
- licensed-integrator/provider name;
- DI protocol version;
- Business Nature(s);
- Sector;
- onboarding status;
- IP/server whitelist status;
- ERP/System Provider;
- software name/version;
- software/POS registration number;
- technical contact;
- Sandbox token;
- Production token;
- Production arming interlock;
- preflight blocking policy;
- pause reason;
- reference-data sync state.

Important decisions:

- `company` is unique;
- tokens are Password fields;
- seller business name/address/province are **not duplicated** in this profile;
- legal seller identity should later resolve from ERPNext Company + legal address/tax identity extensions;
- leaving Production automatically clears the Production arm.

This DocType will eventually replace the global Single `Ledgix FBR Settings`.

It does not replace it yet.

---

### 3.2 Ledgix FBR Business Nature

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_business_nature/`

Child rows for the Integration Profile.

Fields:

- Business Nature;
- FBR reference code;
- active.

Business Nature is onboarding/certification context, not an Item tax setting.

---

### 3.3 Ledgix FBR Item Mapping

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_item_mapping/`

Purpose:

Map a current ERPNext Item to FBR legal/protocol classification.

Fields include:

- Company;
- ERPNext Item;
- active/review state;
- effective dates;
- HS Code;
- FBR UOM;
- FBR Sale/Transaction Type;
- FBR rate/reference description;
- Tax Basis;
- Notified Retail Price / MRP where applicable;
- SRO Schedule Number;
- SRO Item Serial Number;
- reference-data version;
- review/source notes.

The controller prevents multiple active mappings for the same Company + ERPNext Item.

For Notified Retail Price basis, a positive notified value is required.

### Explicitly absent

The V2 Item Mapping intentionally contains no:

- Ledgix Tax Category;
- taxable flag as monetary authority;
- default tax rate;
- monetary sales-tax rate;
- Extra Tax per-unit calculation;
- Further Tax per-unit calculation;
- FED per-unit calculation;
- sales-tax-withheld per-unit calculation;
- Sandbox scenario ID.

This is the key architectural correction from `Ledgix Item Tax Profile`.

---

### 3.4 Ledgix FBR Tax Component Mapping

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_tax_component_mapping/`

Purpose:

Label an authoritative ERPNext tax Account for FBR payload translation.

Current component labels:

- Sales Tax Applicable;
- Sales Tax Withheld At Source;
- Extra Tax;
- Further Tax;
- FED Payable.

The DocType contains:

- Company;
- ERPNext tax Account;
- FBR component;
- active;
- notes.

It contains **no rate and no amount**.

The amount must always come from the native ERPNext invoice tax result.

Controller rules:

- Account must exist;
- Account must belong to the selected Company;
- Account must be an enabled ledger account;
- only one active mapping per Company + Account.

---

### 3.5 Ledgix FBR Reference Data

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_reference_data/`

Purpose:

Persist official FBR reference API values with source/freshness evidence.

Initial reference families:

- Province;
- Document Type;
- Transaction Type;
- UOM;
- Rate;
- HS-UOM;
- SRO Schedule;
- SRO Item;
- Registration Type.

Stored metadata includes:

- FBR ID/code;
- description;
- protocol/source version;
- active/stale state;
- source endpoint;
- fetched timestamp;
- effective dates;
- raw source payload JSON.

This schema is ready for Phase 3 reference synchronization.

No sync worker/API has been wired yet.

---

### 3.6 Ledgix FBR Sandbox Scenario

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_sandbox_scenario/`

Child evidence rows for Sandbox certification.

Fields include:

- Scenario ID;
- description;
- required;
- representative ERPNext DocType;
- representative ERPNext invoice;
- Validate status;
- validation Submission Log;
- POST status;
- POST Submission Log;
- Sandbox FBR invoice number;
- completed timestamp;
- last error.

This moves `scenario_id` to its correct conceptual location: certification.

---

### 3.7 Ledgix FBR Sandbox Certification

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_sandbox_certification/`

Purpose:

Represent certification for one Company / Integration Profile and its required scenarios.

Fields include:

- FBR Integration Profile;
- Company;
- status;
- Business Nature snapshot;
- Sector snapshot;
- start/completion timestamps;
- real-evidence-complete state;
- scenario rows;
- notes.

Controller rules:

- Company must match the Integration Profile;
- certification cannot be marked Complete without at least one required scenario;
- every required scenario must have both:
  - `Validated`;
  - `Submitted`.

The future service layer will control evidence timestamps/snapshots and ensure mock/test evidence cannot satisfy Production readiness.

---

## 4. What remains authoritative today

Even after these schema files are installed by migrate, current runtime still uses:

- `Ledgix FBR Settings`;
- current `fbr_settings.py`;
- current `fbr_native.py`;
- current FBR payload/snapshot path;
- the temporary Phase 1 tax authority boundary.

That is intentional.

The new DocTypes are not wired into hooks or FBR submission yet.

This avoids a half-migrated state.

---

## 5. Static schema guard

New test:

`apps/ledgix_saas/setup/test_fbr_redesign_phase2_schema_contract.py`

It enforces:

- Integration Profile is Company-scoped;
- tokens remain Password fields;
- duplicated seller identity is absent;
- Item Mapping is classification-only;
- Item Mapping contains no `scenario_id`;
- Item Mapping contains no old monetary tax-rate/per-unit-tax fields;
- Tax Component Mapping contains no rate/amount authority;
- reference-data families remain modeled;
- Sandbox scenario lives under certification;
- V2 DocTypes are not prematurely wired into current runtime.

---

## 6. Migration policy

Do not copy old records blindly.

### Old Ledgix FBR Settings -> FBR Integration Profile

Future migration may carry:

- actual configured credentials securely;
- software registration number;
- legitimate control state where safe;
- verified provider/onboarding details.

Do not blindly migrate duplicated seller identity if ERPNext Company/legal masters should own it.

Production must not become armed merely because migration runs.

### Old Ledgix Item Tax Profile -> FBR Item Mapping

Carry only verified compliance/classification data:

- ERPNext Item;
- HS Code;
- FBR UOM;
- Sale Type;
- SRO data;
- notified retail price / tax basis where legally required;
- reference description.

Do not migrate the old monetary tax fields as a new calculator.

Do not migrate `scenario_id` into Item Mapping.

### Old tax masters

Do not map Ledgix Tax Category/Tax Rate into V2 FBR masters.

Their financial replacement is ERPNext-native tax configuration from Phase 1.

---

## 7. Runtime activation order

V2 runtime cutover must occur in this order:

1. finish Phase 1 native ERPNext tax parity locally;
2. capture old FBR/tax runtime data inventory;
3. migrate FBR Integration Profile and Item Mapping data;
4. implement official reference sync;
5. build FBR Payload Builder V2 from ERPNext-native tax result + V2 FBR mappings;
6. migrate settings API behind a compatibility facade;
7. rewrite readiness/certification against V2;
8. switch native FBR runtime to V2;
9. prove Sandbox;
10. freeze old Settings/Item Tax Profile;
11. remove old runtime references;
12. only then physically retire obsolete schemas/code where safe.

---

## 8. Phase 2 definition of done

The additive schema portion of Phase 2 is complete when:

- all V2 DocType files exist;
- schema static contract exists;
- there is no monetary calculator in V2 models;
- Sandbox Scenario is not stored on Item Mapping;
- credentials are company-scoped and secret fields;
- tax-component mapping reads ERPNext authority conceptually;
- current runtime remains unchanged until migration/cutover.

Full Phase 2 will close only after the local site is available and:

- migrate succeeds;
- schema contract tests pass;
- old data counts are captured;
- controlled migration code is proven;
- migrated records are reviewed;
- current FBR runtime has a safe compatibility path to the new Company profile.

---

## 9. Next GitHub-safe work

While the local runtime gate is pending, the next safe additive work is Phase 3 foundation:

- refactor `fbr_reference.py` behind a V2 reference service;
- add safe sync/persist logic for official FBR reference endpoints;
- keep it non-destructive and non-Production;
- do not yet replace current FBR submission payload behavior.

The local site remains required before Phase 1 monetary cutover or destructive old-tax retirement.
