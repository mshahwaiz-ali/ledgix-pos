# FBR Redesign — Phase 4 ERPNext-Native Snapshot Foundation

**Status:** ADDITIVE COLLECTOR IMPLEMENTED — LOCAL RUNTIME PROOF / CUTOVER PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`  
**Parent plan:** `docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`  
**Phase 1 tax authority:** `docs/fbr/FBR_PHASE1_ERPNEXT_NATIVE_TAX_CONTRACT.md`  
**Phase 3 references:** `docs/fbr/FBR_PHASE3_REFERENCE_SYNC_FOUNDATION.md`  
**ERPNext pin inspected:** `15.121.3`

---

## 1. Purpose

Phase 4 establishes a safe way to obtain per-invoice-line tax evidence from ERPNext without rebuilding the tax calculation in Ledgix.

The core rule remains:

> ERPNext calculates tax. Ledgix may capture and classify ERPNext's result, but must not reproduce the formula as a second monetary authority.

This phase is currently a non-persisting, non-networked foundation.

It is not yet wired into invoice submission or FBR payload production.

---

## 2. Why this phase is necessary

FBR Digital Invoicing payloads require per-item values such as:

- value of sales excluding sales tax;
- sales tax applicable;
- sales tax withheld at source;
- Extra Tax;
- Further Tax;
- FED payable.

ERPNext maintains authoritative invoice tax rows and totals.

However the exact pinned ERPNext version has an important limitation.

### ERPNext 15.121.3 item-wise tax JSON

The native `Sales Taxes and Charges.item_wise_tax_detail` structure is keyed by:

```text
item_code or item_name
```

not by the unique invoice child-row name.

Therefore:

```text
Invoice Row 1 -> ITEM-A
Invoice Row 2 -> ITEM-A
```

can be aggregated into one item-code entry.

That is not sufficient evidence for a legal per-line FBR snapshot.

A later ERPNext v15 implementation contains a newer row-level item-wise tax detail model, but Ledgix cannot assume a feature that does not exist in its pinned version.

No ERPNext core backport or modification is used.

---

## 3. Rejected approaches

### 3.1 Recalculate tax in Ledgix

Rejected.

Examples of prohibited reconstruction:

```text
line net amount * tax rate / 100
per-unit custom tax formulas
inclusive-tax reverse formulas
manual previous-row tax formulas
```

Those would recreate the shadow tax engine being retired.

### 3.2 Divide invoice tax total across lines

Rejected.

This fails for:

- mixed rates;
- per-quantity tax;
- previous-row tax;
- inclusive tax;
- custom taxable bases;
- line discounts;
- additional discount;
- rounding.

### 3.3 Trust item-code aggregated `item_wise_tax_detail`

Rejected for immutable FBR line evidence.

Duplicate invoice rows can share an item code.

### 3.4 Reconstruct submitted returns later

Rejected.

Return discount and lifecycle logic can depend on already-submitted return documents.

Final return evidence must be captured during the native draft/submission lifecycle.

---

## 4. Implemented collector

New file:

`apps/ledgix_saas/services/erpnext_fbr_snapshot_v2.py`

The collector subclasses ERPNext's own:

`erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals`

It does not replace ERPNext formulas.

It observes ERPNext's own call to:

`get_current_tax_and_net_amount()`

for each:

```text
unique invoice item row
x
native ERPNext tax row
```

and records the result using unique child-row identity.

---

## 5. Additional-discount behavior

ERPNext 15.121.3 handles distributed additional discount by:

1. calculating normally;
2. distributing the discount to item net amounts;
3. running `_calculate()` again.

The V2 collector resets its capture at each `_calculate()`.

Therefore the retained capture is the final native pass after ERPNext's own discount distribution.

Ledgix does not distribute that discount itself.

---

## 6. Pinned-version fail-closed limitations

### 6.1 Round Tax Amount Row-wise

In the pinned version, row-wise rounding happens in ERPNext's outer tax loop after the per-item calculation method returns.

The collector therefore refuses to run when:

`Accounts Settings -> Round Tax Amount Row-wise`

is enabled.

This is deliberate.

Do not approximate the rounded line split.

A future runtime proof or ERPNext upgrade can remove this limitation safely.

### 6.2 Charge Type = Actual

ERPNext performs the final proportional remainder adjustment for an `Actual` tax row outside the per-item method.

Therefore a tax Account mapped to an FBR component is rejected if its native charge type is:

`Actual`

This is especially important because the old Ledgix bridge created Actual rows for calculated special taxes.

The V2 design should instead use a native ERPNext charge structure that can be captured exactly, where legally appropriate.

Examples to prove may include:

- On Net Total;
- On Item Quantity;
- On Previous Row Amount;
- On Previous Row Total;
- an app-defined taxable-base resolver handled inside ERPNext.

---

## 7. Native reconciliation

The collector does not merely capture numbers.

For every tax Account explicitly mapped through:

`Ledgix FBR Tax Component Mapping`

it compares:

```text
sum of captured ERPNext per-line amounts
vs
ERPNext tax row tax_amount_after_discount_amount
```

If the difference exceeds the narrow monetary tolerance, the collector fails.

This protects against silently producing an FBR line split that does not reconcile to the authoritative ERPNext invoice.

---

## 8. FBR component mapping

The collector reads:

`Ledgix FBR Tax Component Mapping`

Supported semantic labels:

- Sales Tax Applicable;
- Sales Tax Withheld At Source;
- Extra Tax;
- Further Tax;
- FED Payable.

The mapping contains no amount or tax rate.

Its only job is:

```text
ERPNext authoritative Account
        ->
FBR semantic payload component
```

---

## 9. FBR item classification

The collector also resolves the active:

`Ledgix FBR Item Mapping`

by:

- Company;
- ERPNext Item;
- posting date;
- effective-from/effective-to.

Overlapping active mappings fail closed.

The item classification may include:

- HS Code;
- FBR UOM;
- Sale Type;
- FBR Rate description;
- Tax Basis;
- Notified Retail Price;
- SRO Schedule;
- SRO Item serial;
- reference version.

No Sandbox scenario ID exists in the Item Mapping.

---

## 10. Current collector output

The non-persisted candidate returns:

- source DocType/name;
- Company;
- posting date;
- currency;
- ERPNext net total;
- ERPNext total taxes and charges;
- ERPNext grand total;
- each unique invoice item row;
- native rate/amount/net amount;
- Item Tax Template;
- native item tax map;
- matched FBR Item Mapping;
- captured mapped FBR components;
- exact native tax-row evidence;
- reconciliation checks.

The output explicitly marks:

```text
authority = ERPNext Native
database_write = false
fbr_network_call = false
```

---

## 11. Diagnostic mode

Function:

`build_snapshot_candidate(reference_doctype, reference_name)`

This reads an existing ERPNext Sales Invoice or POS Invoice and recalculates a detached in-memory copy.

It does not write the persisted invoice.

### Submitted returns

Submitted returns are explicitly blocked from after-the-fact reconstruction.

Their V2 snapshot must eventually be captured during draft/submission.

---

## 12. Static contract

New test:

`apps/ledgix_saas/setup/test_fbr_redesign_phase4_snapshot_contract.py`

It locks the following rules:

- ERPNext calculator is the engine;
- Ledgix tax formulas are absent;
- unique child-row identity is used;
- item-code aggregated native JSON is not used as line authority;
- row-wise rounding fails closed;
- mapped Actual rows fail closed;
- captured mapped rows reconcile to ERPNext totals;
- V2 FBR-only mapping DocTypes are used;
- no database write;
- no FBR network call;
- submitted return reconstruction is blocked.

The consolidated gate:

`scripts/run_fbr_redesign_static_gate.sh`

now includes Phase 4.

---

## 13. What is intentionally NOT wired yet

The collector is not yet called from:

- Sales Invoice hooks;
- POS Invoice hooks;
- native checkout;
- native return submission;
- `fbr_native.py`;
- current immutable snapshot fields;
- FBR payload generation.

This prevents an unproven collector from changing live transaction behavior.

---

## 14. Required local proof

Once `ledgix-erpnext.local` is available:

### Accounting prerequisites

First complete the Phase 1 native-tax probe and configure native ERPNext tax masters.

### Collector cases

Then prove:

1. normal percentage sales tax;
2. mixed-rate items;
3. duplicate rows using the same Item code;
4. tax-inclusive price if client requires it;
5. additional discount on Net Total;
6. additional discount on Grand Total where supported;
7. zero-rated/native not-applicable cases;
8. On Item Quantity if a real legal component needs it;
9. previous-row tax only if required;
10. native Sales Invoice return during draft lifecycle;
11. native POS Invoice;
12. native POS return;
13. mapped-row totals exactly reconcile;
14. unmapped non-FBR charge rows remain identifiable and do not get mislabeled as FBR tax;
15. row-wise rounding setting correctly fails closed if enabled;
16. mapped Actual tax row correctly fails closed.

No FBR Production POST belongs in this test.

---

## 15. Runtime cutover order

Only after the above passes:

1. invoke the collector from the temporary native-tax authority path;
2. generate immutable V2 snapshot data during the transaction lifecycle;
3. prove saved snapshot matches the final submitted invoice;
4. implement Payload Builder V2 from:
   - immutable native snapshot;
   - FBR Item Mapping;
   - FBR reference cache;
   - Company/customer legal identity;
5. switch FBR readiness to V2 snapshots;
6. remove the old monetary snapshot builder;
7. later retire legacy snapshot fields that are no longer required.

---

## 16. Phase 4 definition of done

### Code foundation

Implemented.

### Runtime parity

Pending.

### FBR payload cutover

Not started.

This boundary is deliberate: no FBR monetary payload should be cut over until ERPNext-native tax parity and line-capture reconciliation are proven on the local integration site.
