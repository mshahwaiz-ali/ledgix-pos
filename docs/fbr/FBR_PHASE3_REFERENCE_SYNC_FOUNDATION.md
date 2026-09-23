# FBR Redesign — Phase 3 Reference Sync Foundation

**Status:** FOUNDATION IMPLEMENTED — LIVE REFERENCE SYNC PROOF PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`  
**Parent plan:** `docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`  
**Phase 2:** `docs/fbr/FBR_PHASE2_FBR_V2_DATA_MODEL.md`

---

## 1. Purpose

Phase 3 replaces arbitrary free-text FBR legal/reference configuration with a controlled cache sourced from FBR Digital Invoicing reference APIs.

The first implementation is intentionally limited to parameter-free reference families that can be normalized against documented DI API v1.12 response shapes without guessing.

No invoice validation or invoice POST is performed by this service.

---

## 2. New service

File:

`apps/ledgix_saas/api/fbr_reference_v2.py`

This service uses:

- `Ledgix FBR Integration Profile`;
- encrypted Sandbox/Production Password token;
- official hardcoded FBR reference endpoints;
- `Ledgix FBR Reference Data`;
- authenticated HTTP GET only.

It does not depend on:

- `Ledgix FBR Settings`;
- `get_fbr_settings_internal`;
- `get_active_fbr_token`;
- old `fbr_reference.py`.

This separation is deliberate so the old global Settings model can later be retired.

---

## 3. Current synchronized families

### Province

Endpoint:

`https://gw.fbr.gov.pk/pdi/v1/provinces`

Documented fields:

- `stateProvinceCode`;
- `stateProvinceDesc`.

### Document Type

Endpoint:

`https://gw.fbr.gov.pk/pdi/v1/doctypecode`

Documented fields:

- `docTypeId`;
- `docDescription`.

### Transaction Type

Endpoint:

`https://gw.fbr.gov.pk/pdi/v1/transtypecode`

Documented fields:

- `transactiON_TYPE_ID`;
- `transactiON_DESC`.

The normalizer is case-insensitive to tolerate casing variation while still requiring the documented semantic fields.

### UOM

Endpoint:

`https://gw.fbr.gov.pk/pdi/v1/uom`

Documented fields:

- `uoM_ID`;
- `description`.

---

## 4. Why only these four are synced now

Other official reference endpoints require parameters or transactional/legal context.

Examples include:

- Sale Type to Rate;
- HS Code to UOM;
- SRO Schedule;
- SRO Item.

Those will be added as explicit parameterized lookup/cache services rather than pretending they are global static tables.

This prevents Ledgix from storing invalid universal mappings when the FBR result depends on:

- posting date;
- transaction type;
- supplier/origination context;
- HS code;
- rate ID;
- SRO ID.

---

## 5. Fail-closed response normalization

The sync does not accept arbitrary JSON.

For each family:

1. response must be a JSON list;
2. each row must be an object;
3. documented identifier must exist;
4. documented description must exist;
5. otherwise the family sync fails.

Unknown response shapes are not silently saved.

---

## 6. Non-destructive cache behavior

For one reference family + protocol version:

1. existing rows are marked stale;
2. current response rows are upserted;
3. returned rows become active and non-stale;
4. rows no longer returned remain stale;
5. no historical cached row is automatically deleted.

This provides change evidence and protects against accidental destructive sync behavior.

---

## 7. Multi-family transaction safety

`sync_core_reference_data()` uses a database savepoint per family.

If one family fails:

- writes from that family are rolled back to its savepoint;
- other successfully synchronized families may remain valid;
- the final profile sync status becomes `Failed`;
- an error summary is returned without exposing tokens.

This service never changes:

- Production arming;
- accounting;
- invoices;
- FBR invoice status.

---

## 8. Security

Reference synchronization:

- requires System Manager or Ledgix Admin;
- reads token through Frappe Password decryption;
- never returns token;
- redacts Bearer credentials from exception text;
- uses fixed official endpoint constants;
- does not accept a user-entered target URL.

Cached reference viewing is allowed to:

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

---

## 9. Public methods

### `sync_reference_family(profile_name, reference_type)`

Synchronizes one supported parameter-free family.

### `sync_core_reference_data(profile_name)`

Synchronizes:

- Province;
- Document Type;
- Transaction Type;
- UOM.

It explicitly reports:

- no invoice network call;
- Production arm unchanged;
- no secrets in result.

### `get_cached_reference_data(reference_type, protocol_version=None)`

Returns only active, non-stale cached values.

---

## 10. Static safety contract

File:

`apps/ledgix_saas/setup/test_fbr_redesign_phase3_reference_contract.py`

The contract verifies:

- official GET endpoint constants;
- no invoice POST/validate calls;
- no dependency on old FBR Settings;
- documented v1.12 response keys;
- fail-closed shape validation;
- no Production arming;
- no secret output;
- savepoint isolation;
- non-destructive stale-cache behavior.

---

## 11. What remains pending

Phase 3 is not closed until the local integration site is available.

Required proof on `ledgix-erpnext.local`:

1. pull current `main`;
2. run migrate to install Phase 2 schemas;
3. run static contracts;
4. create or migrate a non-Production V2 FBR Integration Profile;
5. use real authorized Sandbox reference credentials;
6. execute each reference GET;
7. confirm response shapes;
8. inspect stored cache values;
9. run the same sync twice and prove idempotent upsert behavior;
10. simulate/observe one failed family and prove no partial family writes survive;
11. verify no token appears in logs/output;
12. verify no invoice/FBR submission state changes.

Do not use a Production invoice POST for Phase 3 proof.

---

## 12. Next safe implementation work

After local proof, Phase 3 should add parameterized caches/lookups for:

- Sale Type to Rate;
- HS-UOM;
- SRO Schedule;
- SRO Item;

using explicit query context and cache keys.

The next major phase after reference-data proof is Payload Builder V2, but monetary payload work must wait until Phase 1 ERPNext-native tax parity is proven locally.
