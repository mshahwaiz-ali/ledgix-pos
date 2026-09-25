# FBR Redesign — Phase 1 ERPNext-Native Tax Contract

**Status:** COMPLETE LOCALLY - ERPNext-native monetary authority cut over and parity-proven
**Date:** 2026-09-24
**Repository:** `mshahwaiz-ali/ledgix-pos`
**Branch:** `main`
**Parent plan:** `docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`
**Phase 0 inventory:** `docs/fbr/FBR_PHASE0_BASELINE_INVENTORY.md`
**Supported ERPNext pin reviewed:** `15.121.3`

---

## 1. Phase 1 objective

Replace the current active Ledgix monetary tax-calculation authority with ERPNext-native tax behavior without breaking current checkout, returns, GL, FBR audit safety or historical data.

Target:

```text
ERPNext Tax Category / Tax Rule / Sales Taxes and Charges Template
        +
ERPNext Item Tax Template
        |
        v
ERPNext Sales Invoice / POS Invoice / native return
        |
        v
ERPNext calculate_taxes_and_totals()
        |
        +--> authoritative taxes
        +--> authoritative grand total
        +--> authoritative GL
        |
        v
Ledgix FBR classification / translation only
```

No Ledgix code may remain a second monetary tax calculator after the cutover.

---

## 2. What was confirmed in ERPNext 15.121.3

The actual pinned ERPNext source was inspected before implementing the boundary.

### 2.1 Party / Tax Rule resolution

ERPNext party setup can resolve a Sales Taxes and Charges Template through:

- Company;
- Customer;
- Customer Group;
- Tax Category;
- billing/shipping location;
- Item / Item Group;
- effective dates;
- Tax Rule priority.

The relevant native flow uses `erpnext.accounts.party.set_taxes()` and `Tax Rule.get_tax_template()`.

### 2.2 POS Profile tax authority

ERPNext POS Invoice setup natively reads from POS Profile:

- `tax_category`;
- `taxes_and_charges`;
- customer;
- company;
- price list;
- warehouse;
- other POS defaults.

Ledgix must not replace those tax rows afterward.

### 2.3 Item Tax Template

ERPNext `get_item_details()` resolves Item Tax Templates from:

1. Item tax assignment;
2. Item Group / ancestor assignments.

Assignments support:

- Tax Category;
- valid-from date;
- min/max net-rate range.

The resulting native invoice item stores:

- `item_tax_template`;
- `item_tax_rate`.

### 2.4 Item-specific rate override

ERPNext tax calculation reads `item_tax_rate` by tax Account Head.

This means a common Sales Taxes and Charges Template can contain a tax account row while different Items use different rates through Item Tax Templates.

Ledgix should not calculate:

```text
taxable amount x rate
```

itself.

### 2.5 Zero vs not-applicable

ERPNext Item Tax Template Detail distinguishes:

- numeric `0` rate;
- `not_applicable`.

This is useful for the financial distinction between zero-rated and a tax that does not apply.

FBR legal classification remains separate and must not be inferred only from the financial number.

### 2.6 Inclusive tax

Native Sales Taxes and Charges rows support:

`included_in_print_rate`.

ERPNext calculates the exclusive/net amount and tax amount.

Ledgix must not maintain its own inclusive-tax formula.

### 2.7 Fixed/per-unit tax

Native charge type:

`On Item Quantity`

allows an Item Tax Template number to behave as a per-unit charge for the corresponding account.

This provides an ERPNext-native primitive that may support legally verified per-unit components such as Extra Tax / Further Tax / FED where the client's actual FBR treatment requires that structure.

Exact legal mapping must still be verified.

### 2.8 Custom taxable base extension hook

ERPNext 15.121.3 contains:

`erpnext_taxable_base_resolvers`

as an application extension hook inside the ERPNext tax engine.

This is important for cases such as a tax based on a legally defined value other than the normal invoice net amount.

A future Ledgix resolver can supply an FBR notified-retail-price base while ERPNext still performs the tax calculation.

This is the preferred extension mechanism for Third Schedule/notified-value treatment if required and proven.

It does **not** require modifying ERPNext core.

---

## 3. Native financial capability matrix - local closure state

| Tax behavior | ERPNext-native mechanism | Local Phase 1 result |
|---|---|---|
| Ordinary percentage sales tax | Sales Taxes and Charges + Item Tax Template | PROVEN |
| Different rate per Item | Item Tax Template | PROVEN |
| Tax Category / template selection | Tax Category + Tax Rule / ERPNext setup | PROVEN in native transaction path |
| POS tax authority | POS Profile + native ERPNext tax lifecycle | PROVEN |
| Inclusive tax | `included_in_print_rate` | PROVEN |
| Zero rate | Item Tax Template rate `0` | PROVEN |
| Not applicable / exempt | native zero/not-applicable treatment plus FBR classification | PROVEN |
| Mixed standard / zero / exempt | ERPNext native per-item tax resolution | PROVEN |
| Third Schedule / notified retail value | `erpnext_taxable_base_resolvers` + Ledgix `On Notified Retail Price` extension | PROVEN LOCALLY |
| Extra Tax | ERPNext `On Item Quantity` with dedicated account/template mapping | PROVEN LOCALLY |
| Further Tax | ERPNext `On Item Quantity` with dedicated account/template mapping | PROVEN LOCALLY |
| FED | ERPNext `On Item Quantity` with dedicated account/template mapping | PROVEN LOCALLY |
| Sales Tax Withheld legal evidence | ERPNext Item Tax Template + native `On Item Quantity` primitive captured as non-posting FBR evidence | PROVEN LOCALLY |
| Sales Tax Withheld buyer net-payment settlement | Separate legally/accountingly correct settlement design required | UNRESOLVED - DO NOT GUESS |
| FBR HS/UOM/Sale Type/SRO | Ledgix FBR classification/mapping only | NON-MONETARY |
| Sandbox Scenario ID | Certification context | NOT ITEM TAX CONFIGURATION |

Client legal rates and mappings remain review-gated. Local parity proves the software/accounting mechanism, not that a particular client's rate or legal classification is correct.

---

## 4. Final Phase 1 transaction boundary

Current transaction flow is:

```text
ERPNext Sales Invoice / POS Invoice / native return
        |
        v
ledgix_saas.services.erpnext_tax_authority.apply_sales_tax_authority()
        |
        +--> stamp approved FBR taxable-base inputs only
        +--> ERPNext set_taxes_and_charges()
        +--> ERPNext calculate_taxes_and_totals()
        +--> Ledgix validates the native contract
        |
        v
ERPNext authoritative totals / tax rows / GL
```

Current active callers are the ERPNext selling/POS services for:

- Sales Invoice;
- Sales Invoice return / Credit Note;
- POS Invoice;
- POS Invoice return.

The former `ledgix_erpnext_native_tax_authority` selector is no longer a monetary-engine switch. `native_tax_authority_enabled()` is retained only as a caller-compatibility shim and always resolves to native authority.

`erpnext_tax_authority.py` has:

- no Legacy Bridge branch;
- no call to `erpnext_tax_foundation.apply_tax_plan()`;
- no transaction path that creates `[LEDGIX-TAX]` monetary rows.

`erpnext_tax_foundation.py` may remain physically present for historical/setup/migration compatibility, but it is not the active transaction monetary authority.

No ERPNext core file was modified.

---

## 5. Local runtime parity evidence

Local Phase 1 runtime gates have proven the following against the pinned ERPNext v15.121.3 integration site.

### Core matrix

1. Sales Invoice standard 18%;
2. Sales Invoice tax-inclusive 18%;
3. Sales Invoice zero-rated;
4. Sales Invoice exempt/not-applicable;
5. Sales Invoice mixed standard/zero/exempt;
6. POS Invoice standard;
7. Sales Invoice full native return;
8. POS Invoice full native return.

The core gate also proves:

- raw POS Invoice correctly defers GL to POS Closing consolidation;
- configured GST GL uses the native ERPNext tax account;
- no `[LEDGIX-TAX]` rows are created.

### Dedicated special-case gates

Separate dedicated gates additionally prove:

- Third Schedule/notified retail base;
- Extra Tax;
- Further Tax;
- FED;
- Sales Tax Withheld FBR evidence treatment;
- POS Closing consolidated Sales Invoice/Credit Note GL and exact reversal behavior.

Representative local evidence:

- Third Schedule: transaction value 1,000; notified retail base 1,200; tax 216; native GL 216; return reverses 216.
- Extra Tax: GST 180 + Extra Tax 25; total tax 205; dedicated Extra Tax GL; return reversal correct.
- Further Tax: GST 180 + Further Tax 50; total tax 230; dedicated Further Tax GL; return reversal correct.
- FED: GST 180 + FED 30; total tax 210; dedicated FED GL; return reversal correct.
- Sales Tax Withheld: invoice remains 1,180 with GST 180; withheld evidence 40 is not appended as a financial invoice tax row and posts no withheld GL in this Phase 1 treatment; return evidence reverses to zero.
- POS Closing: raw POS sale/return creates no direct GL; ERPNext closing consolidation creates the accounting Sales Invoice / Credit Note and GST/cash/revenue reverse exactly.

Every parity gate used rollback cleanup and blocked/intercepted FBR submission. No real FBR/PRAL network proof is claimed by these tests.

---

## 6. Sales Tax Withheld boundary

Sales Tax Withheld must not be modeled as an additive Sales Invoice tax simply to force the FBR field to exist.

The locally proven Phase 1 treatment is:

```text
ERPNext Item Tax Template rate
        |
        v
ERPNext native On Item Quantity calculation primitive
        |
        v
transient / non-posting FBR evidence
        |
        v
immutable Ledgix FBR snapshot
```

The reserved withheld account/rate must not be added to the Sales Invoice `.taxes` collection by Ledgix.

Therefore the Phase 1 proof establishes:

- no invoice grand-total inflation;
- no invented withheld GL posting;
- no Ledgix `rate * qty` monetary calculation;
- reproducible immutable FBR evidence;
- return evidence reversal.

Still unresolved and explicitly outside the proven Phase 1 invoice treatment:

> How payment settlement should be accounted for when a buyer actually remits net of Sales Tax Withheld.

That settlement workflow must be designed from verified legal/accounting requirements before implementation.

---

## 7. Legacy FBR execution isolation

The old Ledgix Sale / Ledgix Sales Return FBR code remains physically present where needed for historical records, tests, migration provenance or shared non-monetary helpers.

It is no longer allowed to become a current FBR issuance source:

- legacy browser/RPC FBR preview/validate/payload/submit/reconciliation actions are routed fail-closed;
- legacy `Ledgix Sale` submit lifecycle no longer queues FBR;
- legacy `Ledgix Sales Return` submit lifecycle no longer queues FBR;
- scheduler retry/offline upload remains disabled;
- current new-business FBR hooks target ERPNext `Sales Invoice` / `POS Invoice`.

Shared helpers in `fbr_payload.py` and `fbr_submission.py` are intentionally retained where `fbr_native.py` still uses them for formatting, validation, response parsing, locking or submission-log creation. Physical module presence is not evidence of monetary authority.

---

## 8. Static regression closure

After legacy FBR isolation and stale contract refresh, the focused Phase 1 / Phase 6 / Phase 9 / Phase 12 static regression suite passes:

```text
51 tests
OK
```

The suite covers, among other things:

- native monetary-authority boundary;
- Third Schedule contract;
- Sales Tax Withheld contract;
- legacy FBR isolation;
- ERPNext-native FBR source cutover;
- legacy retirement/freeze contract;
- current Desk FBR-V2 surface.

Static tests complement but do not replace the runtime parity gates described above.

---

## 9. What remains after Phase 1

Phase 1 closes the **local monetary tax authority** problem. It does not mean the complete FBR redesign or Production rollout is finished.

Remaining work includes:

- complete/re-validate the FBR V2 data-model and current runtime handoff;
- move remaining non-monetary defaults still read from old tax-profile helpers into the intended V2/company-scoped configuration;
- finish the canonical FBR payload-builder/certification path;
- prove authorized FBR reference-data calls where required;
- obtain real Sandbox credentials and perform real Sandbox certification;
- preserve real Sandbox evidence;
- complete offline/reconciliation workflows required by the final design;
- finish correction/note behavior against current FBR requirements;
- retire obsolete physical legacy modules only after dependency proof;
- resolve buyer net-payment settlement accounting for Sales Tax Withheld;
- perform explicit Production activation only after all Production gates are green.

Production remains fail-closed and NOT READY.

---

## 10. Phase 1 local definition of done

The Phase 1 monetary-authority definition is satisfied locally because:

- Sales Invoice uses ERPNext-native tax configuration;
- POS Invoice uses ERPNext-native tax configuration;
- native returns preserve/reverse ERPNext-native tax results;
- GL uses native configured accounts;
- transaction services contain no direct old tax-engine call;
- `erpnext_tax_authority.py` has no monetary Legacy Bridge fallback;
- the temporary monetary-authority switch is removed as an engine selector;
- no current transaction creates `[LEDGIX-TAX]` monetary rows;
- core and dedicated runtime parity gates pass;
- legacy FBR Sale/Return execution surfaces are isolated fail-closed.

This is a **local Phase 1 closure**, not FBR Sandbox certification and not Production approval.

---

## 11. Safety / evidence statement

Phase 1 evidence does **not** claim:

- a real FBR Sandbox validation;
- a real FBR Sandbox POST;
- a real FBR Production POST;
- approval of any client-specific legal rate;
- resolution of Sales Tax Withheld net-payment settlement accounting.

Those items require separate evidence and later redesign gates.
