# FBR Redesign — V2 Migration and Readiness Gate

**Status:** LOCAL-ONLY PREVIEW/APPLY DRIVER IMPLEMENTED — EXECUTION PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`

---

## 1. Purpose

This gate moves verified FBR compliance metadata from the old mixed tax/FBR model into the new V2 compliance model without carrying the old monetary tax engine forward.

The migration code is restricted to:

`ledgix-erpnext.local`

Production migration will be designed only after the local result is reviewed.

---

## 2. Source models

### Old global settings

`Ledgix FBR Settings`

The preview reads:

- enabled/mode/trigger state;
- Production arm state;
- preflight blocking preference;
- software registration number;
- whether Sandbox token exists;
- whether Production token exists;
- whether duplicated seller identity exists.

It never returns password values.

### Old item compliance/tax model

`Ledgix Item Tax Profile`

The old model mixes:

- FBR classification;
- Sandbox scenario;
- monetary tax rates/components.

V2 migration deliberately splits these concepts.

---

## 3. Destination models

### Integration Profile

`Ledgix FBR Integration Profile`

Destination is always forced to:

```text
Enabled = No
Mode = Disabled
Submit Trigger = Manual
Production Post Armed = No
Onboarding Status = Not Started
```

This happens regardless of the legacy state.

A legacy Production configuration can therefore never become active merely because migration runs.

### Item Mapping

`Ledgix FBR Item Mapping`

Migrated classification fields:

- ERPNext Item;
- HS Code;
- FBR UOM;
- Sale Type;
- FBR Rate description;
- Tax Basis;
- Notified Retail Price;
- SRO Schedule Number;
- SRO Item Serial Number.

Every created mapping is:

`Needs Review = Yes`

until verified against official FBR references.

---

## 4. Data intentionally NOT migrated

### Monetary tax authority

The following old fields are explicitly ignored:

- Default Tax Rate;
- Sales Tax Withheld at Source / Unit;
- Extra Tax / Unit;
- Further Tax / Unit;
- FED Payable / Unit.

Their replacement belongs to ERPNext native tax configuration, not V2 FBR Item Mapping.

The preview reports every old profile where ignored monetary fields contain non-zero values.

### Sandbox Scenario ID

Old Item-level `scenario_id` is not copied.

The preview reports it separately.

Scenario assignment belongs to V2 Sandbox Certification.

### Duplicated seller identity

The migration does not write old:

- Seller NTN/CNIC;
- Seller Business Name;
- Seller Province;
- Seller Address

into the new Integration Profile.

Seller legal identity should resolve from ERPNext Company/legal identity authorities plus only genuinely missing FBR-specific extensions.

---

## 5. Credentials

Sandbox and Production Password fields may be securely copied from old Settings into the new Company-scoped profile.

Rules:

- token values are decrypted only in memory;
- copied through Password-field handling;
- never returned by preview/apply result;
- migration result reports only boolean `*_token_copied`;
- destination profile remains Disabled;
- Production remains unarmed.

---

## 6. Preview

Module:

`apps/ledgix_saas/migration/fbr_redesign_v2_migration.py`

Function:

`preview_v2_migration(company)`

Properties:

- local integration site only;
- read only;
- no password decryption;
- no FBR network;
- no database write;
- no Production state change.

It reports:

- profile migration proposal;
- each old Item Tax Profile candidate;
- existing V2 mappings;
- blockers;
- duplicate legacy mappings;
- ignored monetary fields;
- ignored Sandbox scenarios.

Runner:

`scripts/run_fbr_redesign_v2_migration_preview.sh`

Usage after migrate:

```bash
cd ~/data_drive/pos
bash scripts/run_fbr_redesign_v2_migration_preview.sh \
  ledgix-erpnext.local \
  "YOUR ERPNext COMPANY"
```

---

## 7. Blockers

Apply refuses to run if preview contains blockers.

Examples:

- old profile has no ERPNext Item;
- referenced ERPNext Item does not exist;
- multiple old profiles target the same ERPNext Item.

Blockers must be reviewed and resolved rather than silently deduplicated.

---

## 8. Apply

Function:

`apply_v2_migration(company, confirmation)`

Required exact confirmation:

`APPLY FBR V2 LOCAL MIGRATION`

Additional safety:

- local integration site only;
- preview runs again immediately before apply;
- any blocker aborts;
- one database savepoint wraps migration;
- exception rolls back to savepoint;
- destination profile remains disabled/unarmed;
- old records are not deleted;
- existing active V2 Item Mappings are skipped for review rather than overwritten.

There is intentionally no convenience apply shell script yet.

Preview evidence must be reviewed first.

---

## 9. Static contract

Test:

`apps/ledgix_saas/setup/test_fbr_redesign_v2_migration_contract.py`

It locks:

- local-only restriction;
- preview read-only behavior;
- no preview password access;
- destination Disabled/Manual/unarmed state;
- token secrecy;
- monetary tax fields ignored;
- Item scenario ignored;
- review-required mappings;
- explicit apply confirmation;
- blocker stop;
- savepoint rollback;
- duplicated legacy seller identity not written.

The test is included in:

`scripts/run_fbr_redesign_static_gate.sh`

---

## 10. Local execution order

When the laptop becomes available:

1. pull `main`;
2. run the static redesign gate;
3. migrate `ledgix-erpnext.local`;
4. run Phase 1 native-tax inventory;
5. run this V2 migration preview;
6. inspect blockers and ignored monetary/scenario evidence;
7. do **not** apply migration until the preview is reviewed;
8. configure/prove ERPNext-native tax authority;
9. only then apply V2 metadata migration locally;
10. verify migrated mappings against official FBR reference data;
11. keep FBR Production disabled.

---

## 11. Production migration

This helper is intentionally not usable on production.

After local proof, the production migration procedure must separately define:

- fresh backup requirement;
- pre/post row counts;
- Company selection;
- old/new settings evidence;
- credential-preservation handling;
- idempotency;
- conflict handling;
- rollback;
- Production remains unarmed until Sandbox certification.

No production migration should be created by merely removing the local-site guard.
