# FBR Redesign — Phase 3 Reference Sync Foundation

**Status:** CODE FOUNDATION COMPLETE — LIVE FBR GET PROOF PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`  
**Parent plan:** `docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`  
**Phase 2:** `docs/fbr/FBR_PHASE2_FBR_V2_DATA_MODEL.md`

---

## 1. Purpose

Phase 3 replaces arbitrary free-text FBR protocol/reference configuration with controlled values obtained from official Digital Invoicing reference APIs.

The implementation is additive and does not submit invoices.

It now covers:

- parameter-free master references;
- parameterized contextual references;
- live taxpayer registration lookups;
- deterministic context-aware caching;
- non-destructive stale handling;
- credential-agnostic HTTP GET transport.

---

## 2. Transport boundary

New file:

`apps/ledgix_saas/api/fbr_transport.py`

This transport:

- performs authenticated GET only;
- knows nothing about old `Ledgix FBR Settings`;
- knows nothing about the new Integration Profile;
- knows nothing about Sandbox/Production policy;
- knows nothing about invoice submission;
- never arms Production;
- never stores credentials;
- redacts Bearer credentials from transport errors.

The V2 reference service resolves the correct profile/token first and then calls this neutral transport.

This removes the earlier architecture leak where reference V2 depended indirectly on `fbr_client.py`, which itself imports the old global FBR Settings model.

---

## 3. Reference service

File:

`apps/ledgix_saas/api/fbr_reference_v2.py`

Authority:

- `Ledgix FBR Integration Profile`;
- encrypted Password token from the selected Company profile;
- official fixed FBR endpoint constants;
- `Ledgix FBR Reference Data`.

It never accepts an arbitrary remote URL.

---

## 4. Parameter-free reference families

### Core sync

`sync_core_reference_data()` intentionally synchronizes the smaller operational masters:

- Province;
- Document Type;
- Transaction Type;
- UOM.

### Additional manual/static catalog sync

`sync_reference_family()` also supports:

- Item Code / HS Code catalog;
- SRO Item Code catalog.

These can be larger datasets and therefore are not forced into every core sync.

Current official endpoint set:

```text
Province:
https://gw.fbr.gov.pk/pdi/v1/provinces

Document Type:
https://gw.fbr.gov.pk/pdi/v1/doctypecode

Transaction Type:
https://gw.fbr.gov.pk/pdi/v1/transtypecode

UOM:
https://gw.fbr.gov.pk/pdi/v1/uom

Item Code:
https://gw.fbr.gov.pk/pdi/v1/itemdesccode

SRO Item Code:
https://gw.fbr.gov.pk/pdi/v1/sroitemcode
```

The response normalizer requires the documented semantic ID + description fields and fails closed on an unknown JSON shape.

---

## 5. Parameterized contextual reference families

These FBR values are not global masters.

Their result depends on the query context.

### 5.1 Sale Type to Rate

Endpoint:

`https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate`

Query contract:

```text
date
transTypeId
originationSupplier
```

Public service:

`sync_rates(profile_name, posting_date, transaction_type_id, origination_supplier)`

Documented response values include:

- Rate ID;
- Rate description;
- Rate value.

The V2 cache stores the ID, description and raw official source row.

It does not use Rate Value as an ERPNext accounting authority.

### 5.2 HS Code to UOM

Endpoint:

`https://gw.fbr.gov.pk/pdi/v2/HS_UOM`

Query contract:

```text
hs_code
annexure_id
```

Public service:

`sync_hs_uoms(profile_name, hs_code, annexure_id=3)`

This is the correct place to verify allowed FBR UOM choices for an HS Code.

### 5.3 SRO Schedule

Endpoint:

`https://gw.fbr.gov.pk/pdi/v1/SroSchedule`

Query contract:

```text
rate_id
date
origination_supplier_csv
```

Public service:

`sync_sro_schedules(profile_name, rate_id, posting_date, origination_supplier_csv)`

### 5.4 SRO Item

Endpoint:

`https://gw.fbr.gov.pk/pdi/v2/SROItem`

Query contract:

```text
date
sro_id
```

Public service:

`sync_sro_items(profile_name, posting_date, sro_id)`

---

## 6. Context-aware cache identity

`Ledgix FBR Reference Data` now contains:

- `context_key`;
- `context_json`.

Static parameter-free references use:

`GLOBAL`

Parameterized references use a SHA-256 key derived from canonical JSON query context.

Example conceptual contexts:

```json
{"date":"2026-09-23","originationSupplier":"8","transTypeId":"18"}
```

or:

```json
{"annexure_id":"3","hs_code":"5904.9000"}
```

This prevents an FBR Rate/SRO/UOM row returned for one date, province, transaction type or HS Code from colliding with the same FBR ID returned under another legal context.

Credentials are never included in context JSON.

---

## 7. Non-destructive cache behavior

For one:

```text
reference type
+ protocol version
+ context key
```

the sync process:

1. marks prior rows for that exact context stale;
2. calls the official GET endpoint;
3. rejects unknown response shape;
4. upserts returned rows;
5. marks returned rows active/non-stale;
6. leaves disappeared rows as historical stale evidence;
7. never automatically deletes historical cache rows.

The original global uniqueness rule was updated accordingly:

```text
reference_type
+ fbr_id
+ protocol_version
+ context_key
```

---

## 8. Live taxpayer-specific lookups

These are deliberately **not** stored as static master reference records.

### Sales Tax registration status

Endpoint:

`https://gw.fbr.gov.pk/dist/v1/statl`

Service:

`lookup_sales_tax_registration_status(profile_name, registration_no, posting_date)`

Request context:

- registration number;
- date.

### Registration Type

Endpoint:

`https://gw.fbr.gov.pk/dist/v1/Get_Reg_Type`

Service:

`lookup_registration_type(profile_name, registration_no)`

These values concern a specific taxpayer and can change.

Treating them as timeless master data would be incorrect.

---

## 9. Security and network policy

Reference synchronization:

- requires System Manager or Ledgix Admin;
- decrypts only the active profile token in memory;
- returns no token;
- uses fixed official FBR URLs;
- makes GET requests only;
- cannot validate an invoice;
- cannot POST an invoice;
- cannot arm Production;
- cannot alter ERPNext accounting.

Read-only cached-reference viewing is available to the intended FBR view roles.

Live taxpayer lookups are also read-only network calls.

---

## 10. Core sync transaction safety

`sync_core_reference_data()` uses a database savepoint for each family.

If one family fails:

- that family is rolled back;
- successful families are retained;
- profile reference status becomes Failed;
- errors are returned without credentials.

This prevents half-written data inside a failed family while allowing already-successful independent reference families to remain useful.

---

## 11. Desk usage direction

The future Desk FBR setup flow should consume these services rather than accept arbitrary free text.

Examples:

```text
Seller Province
    -> Province reference

Buyer Province
    -> Province reference

Sale Type
    -> Transaction Type reference

Rate description
    -> SaleTypeToRate for date + transaction type + supplier province

HS Code
    -> Item Code catalog

FBR UOM
    -> HS_UOM result for selected HS code

SRO Schedule
    -> SroSchedule for selected rate/date/province

SRO Item Serial
    -> SROItem for selected date/SRO
```

This UI wiring is a later phase.

The reference service itself is now ready for that wiring.

---

## 12. Static contract

File:

`apps/ledgix_saas/setup/test_fbr_redesign_phase3_reference_contract.py`

It locks:

- official v1.12 endpoint constants;
- documented response keys;
- exact parameter names;
- context hashing;
- reference-data context schema;
- GET-only transport;
- no old Settings dependency;
- no invoice POST/validate;
- no Production arming;
- non-destructive cache behavior;
- static Item Code/SRO Item Code support;
- live STATL/Registration Type behavior.

---

## 13. Runtime proof still required

Phase 3 is not operationally closed until `ledgix-erpnext.local` is available.

Required proof:

1. pull current main;
2. migrate V2 schemas;
3. run redesign static gate;
4. create/migrate a Sandbox V2 Integration Profile;
5. sync Province/Document Type/Transaction Type/UOM;
6. inspect actual returned values;
7. manually sync Item Code and SRO Item Code where practical;
8. exercise SaleTypeToRate with real context;
9. exercise HS_UOM with a real client HS Code;
10. exercise SRO Schedule/Item only if the actual client flow requires SRO treatment;
11. run STATL and Registration Type against authorized test/client identities;
12. repeat the same contextual sync and prove idempotent update;
13. change context and prove separate cache keys;
14. deliberately fail one family and prove savepoint rollback;
15. confirm no secrets appear in output/logs;
16. confirm no FBR invoice submission state changes.

No Production invoice POST is part of this proof.

---

## 14. Phase 3 definition of done

### Code foundation

Complete.

### Runtime evidence

Pending.

Physical production readiness remains blocked until:

- Phase 1 ERPNext-native monetary tax parity passes;
- Phase 3 reference calls are proven with real authorized credentials;
- later Sandbox scenario certification passes.
