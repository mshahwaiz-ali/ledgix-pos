# FBR Redesign — Phase 6 Desk Compliance Center Cutover

**Status:** GITHUB CUTOVER IMPLEMENTED — LOCAL DESK QA PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`

---

## 1. Purpose

Phase 6 removes the old custom tax/FBR architecture from the normal Desk operator surface.

The existing route is preserved:

`/app/ledgix-tax-center`

so bookmarks, Workspace links and role access do not break.

The page itself is now a V2 compliance center built around one rule:

> ERPNext owns monetary tax and accounting. Ledgix owns FBR-specific classification, reference data, certification, readiness, audit and controlled integration workflow.

The page no longer exposes the old Ledgix monetary tax engine as an operator setup path.

---

## 2. What was removed from the active Desk surface

The Tax & FBR Center no longer exposes:

- Ledgix Tax Profile;
- Ledgix Tax Category;
- Ledgix Tax Rate;
- Ledgix Item Tax Profile;
- legacy category tax rollout;
- legacy FBR Settings;
- legacy FBR sale preview;
- Production Validate button;
- Production Submit button;
- Sandbox invoice Validate button from the old runtime;
- old tax-engine readiness score.

These source files/DocTypes may still physically exist during the migration window, but they are no longer the active Desk configuration authority.

---

## 3. New Desk areas

### Overview

Shows:

- architecture state;
- V2 Company profile count;
- mappings requiring review;
- official FBR reference-cache count;
- completed Sandbox certifications;
- Production-arm count.

It explicitly states that the center has no Production invoice-submit action.

### ERPNext Tax Setup

Links directly to native ERPNext:

- Tax Category;
- Tax Rule;
- Sales Taxes and Charges Template;
- Item Tax Template;
- Account.

This is now the only normal Desk path shown for monetary tax setup.

### FBR Integration

Uses:

- Ledgix FBR Integration Profile;
- official reference-data cache.

From this area an authorized admin can run the existing V2 **core reference GET sync** for:

- Province;
- Document Type;
- Transaction Type;
- UOM.

The action cannot:

- validate an invoice;
- submit an invoice;
- arm Production;
- change accounting.

### Product Compliance

Uses only:

- Ledgix FBR Item Mapping;
- Ledgix FBR Tax Component Mapping.

The UI describes Item Mapping as FBR classification only.

No monetary tax rate/amount controls are presented.

### Certification & Readiness

Uses:

- Ledgix FBR Sandbox Certification;
- Phase 5 invoice readiness;
- FBR Submission Log;
- FBR Correction Request.

Invoice readiness is read-only.

It combines:

- ERPNext identity;
- native tax evidence;
- V2 product mapping;
- tax component classification;
- official reference evidence.

It does not build or send an FBR payload.

---

## 4. New Desk API

File:

`apps/ledgix_saas/api/fbr_v2_center.py`

### `get_v2_center_boot()`

Returns V2 operator status:

- Company Integration Profiles;
- native ERPNext tax-master counts;
- V2 mapping coverage;
- official FBR reference cache summary;
- Sandbox certification summary;
- Production safety state.

It also reports legacy record counts for migration visibility only.

Legacy counts are not treated as configuration authority.

### `get_v2_item_mappings()`

Provides paginated/searchable V2 Item Mapping rows.

It does not expose old Item Tax Profiles.

### `evaluate_v2_invoice_readiness()`

Desk wrapper around the read-only Phase 5 readiness service.

### `get_fbr_readiness()`

Compatibility replacement for the old Tax Center readiness RPC.

Old callers of:

`ledgix_saas.api.tax_center.get_fbr_readiness`

are routed to this V2 summary instead of the old tax-engine preflight.

---

## 5. Old Phase 9 JavaScript patch retired from loading

The following asset is no longer loaded through `hooks.py`:

`/assets/ledgix_saas/js/ledgix_fbr_native_center.js`

That patch previously reintroduced:

- current native invoice preview;
- Sandbox/Production validation;
- live Production submission controls

into the old Tax Center.

The source file can remain temporarily as historical migration evidence, but it is not an active Desk asset.

---

## 6. Production safety

Phase 6 introduces no Production submission path.

The V2 Desk Center has no button/action that calls:

- Production invoice validate;
- FBR invoice POST;
- native Production submit.

Reference sync remains GET-only.

The V2 profile may still contain the Production interlock because it is part of the future integration model, but Phase 6 does not operate that interlock for invoice submission.

---

## 7. Why physical legacy deletion waits

The user-facing cutover can safely happen before physical code deletion.

Physical retirement still waits for:

1. local static gate;
2. bench migrate;
3. ERPNext-native tax parity;
4. V2 metadata migration preview/apply;
5. V2 reference sync proof;
6. V2 identity proof;
7. native line-snapshot proof;
8. V2 readiness proof;
9. final payload V2 implementation;
10. Sandbox certification;
11. regression proof.

Only then should old tax/FBR runtime modules and old monetary DocTypes be deleted or archived from active application code.

This avoids losing historical/migration evidence while preventing them from conflicting with normal new setup.

---

## 8. Static contract

File:

`apps/ledgix_saas/setup/test_fbr_redesign_phase6_desk_contract.py`

The contract verifies:

- V2 Desk APIs only;
- no old FBR Settings call;
- no old Tax Profile/Category/Rate/Item Tax Profile in the active page;
- native ERPNext tax masters are exposed;
- V2 FBR DocTypes are exposed;
- no Production invoice-submit action;
- no monetary tax formula in the V2 center API;
- old Phase 9 patch asset is not loaded;
- old Tax Center readiness compatibility RPC routes to V2.

It is included in:

`scripts/run_fbr_redesign_static_gate.sh`

---

## 9. Local Desk QA

After laptop pull/migrate:

1. open `/app/ledgix-tax-center`;
2. verify all five tabs load;
3. verify no old monetary Ledgix tax master is offered;
4. open each ERPNext native tax master from the Tax Setup tab;
5. open V2 Integration Profile;
6. open V2 Item Mapping;
7. open V2 Tax Component Mapping;
8. open V2 Sandbox Certification;
9. verify Manager cannot perform admin-only reference sync;
10. verify Admin can run core reference sync with an authorized profile;
11. select a Sales Invoice and run readiness;
12. select a POS Invoice and run readiness;
13. confirm readiness performs no FBR network call;
14. confirm no Production Submit button exists;
15. inspect browser console for page JavaScript errors;
16. verify mobile/narrow layout.

---

## 10. Definition of done

### GitHub code cutover

Implemented.

### Local Desk render/behavior proof

Pending.

### Legacy source deletion

Pending until later retirement gate.

### Final FBR submission runtime

Not implemented in V2 yet.
