# FBR Redesign — Phase 5 Identity and Payload-Input Readiness

**Status:** READ-ONLY FOUNDATION IMPLEMENTED — LOCAL RUNTIME PROOF PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`  
**Official protocol target:** FBR DI API v1.12

---

## 1. Purpose

Phase 5 prepares the inputs required by the future FBR Payload Builder V2 without constructing or submitting an invoice payload yet.

The phase answers four questions:

1. Is seller/buyer legal identity coming from the correct ERPNext masters?
2. Does every invoice line have reviewed FBR classification backed by official reference data?
3. Are ERPNext tax/charge rows explicitly classified for FBR treatment?
4. Is the Company profile operationally ready for Sandbox or Production transport?

This separation prevents a payload builder from becoming another place where missing legal/accounting data is guessed.

---

## 2. ERPNext-authoritative identity

New service:

`apps/ledgix_saas/services/erpnext_fbr_identity.py`

### Seller authority

Seller fields resolve from:

```text
sellerNTNCNIC
    <- Company.tax_id

sellerBusinessName
    <- Company.company_name

sellerProvince
    <- linked Company Address.state

sellerAddress
    <- linked Company Address components
```

Address selection:

1. transaction `company_address`;
2. otherwise standard Company default Address link.

No new duplicated seller identity fields are introduced.

### Buyer authority

Buyer fields resolve from:

```text
buyerNTNCNIC
    <- Customer.tax_id

buyerBusinessName
    <- Customer.customer_name

buyerProvince
    <- transaction billing / Customer primary Address.state

buyerAddress
    <- transaction billing / Customer primary Address

buyerRegistrationType
    <- FBR-specific Customer registration-type extension
```

The current legacy Buyer NTN/CNIC field is allowed only as a transition fallback when native `Customer.tax_id` is empty.

If native Tax ID and legacy Buyer NTN/CNIC disagree, V2 fails readiness.

Legacy Buyer Province/Address values are no longer authoritative. Differences are reported as migration warnings.

---

## 3. Identity validation

Seller requires:

- Company Tax ID;
- Company Name;
- linked/default Company Address;
- Address State/Province;
- address value.

Buyer requires:

- Customer Name;
- billing/primary Address;
- Address State/Province;
- address value;
- explicit Registered/Unregistered registration type;
- Tax ID when registration type is Registered.

Unregistered buyer NTN/CNIC can be empty in accordance with the current FBR v1.12 contract.

---

## 4. Identity probe

Runner:

`scripts/run_fbr_redesign_v2_identity_probe.sh`

Example:

```bash
cd ~/data_drive/pos

bash scripts/run_fbr_redesign_v2_identity_probe.sh \
  ledgix-erpnext.local \
  "Sales Invoice" \
  "YOUR-INVOICE"
```

The probe:

- writes nothing;
- performs no FBR network request;
- reports identity sources, errors and transition warnings.

---

## 5. Readiness aggregator

New service:

`apps/ledgix_saas/services/fbr_v2_readiness.py`

Function:

`evaluate_invoice_readiness(reference_doctype, reference_name)`

It combines:

- V2 Company Integration Profile;
- ERPNext-authoritative identity;
- Phase 4 native tax snapshot candidate;
- V2 Item Mapping;
- V2 Tax Component Mapping;
- cached official FBR reference evidence;
- Sandbox certification state;
- token-configured booleans.

It never returns a token value.

---

## 6. Official reference evidence

A mapped invoice line cannot become payload-input ready merely because free-text fields are populated.

Phase 5 requires cached FBR evidence.

### Province

Seller and buyer Address State/Province must match active FBR Province reference data.

### HS Code

Mapped HS Code must match active FBR Item Code reference data.

### UOM

Mapped FBR UOM must:

- exist in the FBR UOM master;
- have contextual HS-UOM proof for the selected HS Code.

Current HS-UOM context uses the current DI Sales Annexure ID contract used by the integration foundation.

### Sale Type

Mapped Sale Type must match active FBR Transaction Type reference data.

### Rate description

The exact FBR Rate Description must have contextual `SaleTypeToRate` evidence for:

- invoice date;
- FBR Transaction Type ID;
- seller Province ID.

This follows FBR v1.12, where `originationSupplier` is the Province ID.

---

## 7. SRO fail-closed state

The v1.12 APIs for SRO Schedule and SRO Item are implemented in Phase 3.

However final field semantics between:

- SRO Schedule API ID/description;
- payload `sroScheduleNo`;
- SRO Item ID/description;
- payload `sroItemSerialNo`

still require real-client Sandbox evidence before V2 payload cutover.

Therefore any current Item Mapping containing SRO fields intentionally blocks `payload_input_ready`.

Do not guess this mapping.

---

## 8. Tax/charge-row classification

Phase 5 inspects every non-zero ERPNext Sales Taxes and Charges row.

A row must have explicit V2 classification through:

`Ledgix FBR Tax Component Mapping`

If a non-zero tax/charge row has no classification, readiness fails.

This prevents:

- shipping/handling rows;
- tax rows;
- special charges;
- unexpected accounts

from silently disappearing or being mislabelled in the eventual FBR payload.

Phase 4 still performs the authoritative monetary reconciliation for mapped FBR tax Accounts.

---

## 9. Readiness levels

The service deliberately separates three states.

### Payload input ready

Requires no identity, native-tax, mapping, classification or reference-data errors.

It does **not** mean a network submission is allowed.

### Sandbox transport ready

Requires:

- payload inputs ready;
- V2 Company profile enabled;
- Mode = Sandbox;
- Sandbox token configured.

### Production transport ready

Requires all payload-input conditions plus:

- V2 Company profile enabled;
- Mode = Production;
- Production token configured;
- Production posting explicitly armed;
- completed Sandbox certification with real evidence.

The migration driver creates a Disabled profile, so migration alone can never satisfy transport readiness.

---

## 10. Readiness runner

`scripts/run_fbr_redesign_v2_readiness.sh`

Example:

```bash
cd ~/data_drive/pos

bash scripts/run_fbr_redesign_v2_readiness.sh \
  ledgix-erpnext.local \
  "Sales Invoice" \
  "YOUR-INVOICE"
```

It is read-only and makes no FBR network request.

---

## 11. Static contracts

Identity:

`apps/ledgix_saas/setup/test_fbr_redesign_identity_v2_contract.py`

Readiness:

`apps/ledgix_saas/setup/test_fbr_redesign_v2_readiness_contract.py`

Both are included in:

`scripts/run_fbr_redesign_static_gate.sh`

The contracts enforce:

- seller authority = Company + Address;
- buyer authority = Customer + Address;
- no duplicated seller settings authority;
- legacy buyer fields only as transition evidence/fallback;
- no payload creation;
- no DB writes;
- no FBR network;
- reviewed mappings required;
- official cached references required;
- unclassified ERPNext charge rows block readiness;
- Production readiness is stricter than payload readiness.

---

## 12. What Phase 5 does NOT do

It does not:

- build final FBR JSON;
- decide unresolved SRO semantics;
- calculate tax;
- calculate `totalValues`;
- decide final discount mapping;
- submit or validate an invoice;
- change FBR status;
- persist an immutable V2 snapshot;
- alter any ERPNext invoice;
- arm Production.

Those remain later gates.

---

## 13. Why final payload building still waits

FBR v1.12 defines monetary line fields including:

- `totalValues`;
- `valueSalesExcludingST`;
- `salesTaxApplicable`;
- `salesTaxWithheldAtSource`;
- `extraTax`;
- `furtherTax`;
- `fedPayable`;
- `discount`.

Phase 4 provides ERPNext-native tax evidence, but local runtime parity must prove how the pinned ERPNext invoice representation maps to these FBR fields for:

- inclusive tax;
- distributed additional discount;
- mixed rates;
- returns;
- special taxable bases;
- rounding.

The final builder must consume proven immutable values, not invent formulas from assumptions.

---

## 14. Local gate order

When the laptop is available:

1. run static redesign gate;
2. migrate the integration site;
3. run Phase 1 native tax inventory;
4. run V2 migration preview;
5. inspect identity probe;
6. sync official FBR references with authorized Sandbox credentials;
7. configure/review V2 Item and Tax Component mappings;
8. run Phase 4 native snapshot probe;
9. run Phase 5 readiness;
10. resolve every blocker;
11. only after parity is proven, wire immutable V2 snapshot lifecycle;
12. then build FBR Payload Builder V2.

Production remains unarmed through this entire sequence.
