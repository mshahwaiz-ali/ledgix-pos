# FBR Redesign — Phase 1 ERPNext-Native Tax Contract

**Status:** IMPLEMENTATION IN PROGRESS — NATIVE SERVER TAX-RESOLUTION BOUNDARY COMPLETE, RUNTIME CUTOVER PENDING  
**Date:** 2026-09-23  
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

## 3. Native financial capability matrix

| Tax behavior | ERPNext-native mechanism | Phase 1 decision |
|---|---|---|
| Ordinary percentage sales tax | Sales Taxes and Charges + Item Tax Template | USE |
| Different rate per Item | Item Tax Template | USE |
| Tax Category selection | Tax Category + Tax Rule | USE |
| Customer/location-specific template | Tax Rule / Address Tax Category | USE |
| POS tax template | POS Profile | USE |
| Inclusive tax | `included_in_print_rate` | USE |
| Zero rate | Item Tax Template rate `0` | USE |
| Not applicable | Item Tax Template `not_applicable` | USE |
| Per-unit tax | `On Item Quantity` | USE where legally applicable |
| Previous-tax-based tax | On Previous Row Amount / Total | USE where legally applicable |
| Arbitrary fixed invoice charge | Actual | USE only where business/legal rule fits |
| Notified/MRP taxable base | `erpnext_taxable_base_resolvers` app hook | EXTEND ERPNext, do not create second engine |
| FBR HS/UOM/Sale Type/SRO | Not accounting tax | Ledgix FBR mapping |
| Sandbox Scenario ID | Certification context | Not Item tax configuration |
| Sales-tax-withheld semantics | Legal/accounting meaning still must be verified | DO NOT GUESS |

---

## 4. Phase 1 code boundary now added

New module:

`apps/ledgix_saas/services/erpnext_tax_authority.py`

Purpose:

Create one transaction-level tax-authority boundary.

Before this change:

```text
erpnext_pos.py ----------------------+
                                     +-> erpnext_tax_foundation.apply_tax_plan()
erpnext_selling.py ------------------+
```

After this change:

```text
erpnext_pos.py ----------------------+
                                     +-> erpnext_tax_authority.apply_sales_tax_authority()
erpnext_selling.py ------------------+
```

The old tax foundation is now referenced only inside the transitional authority module for these active transaction paths.

This makes final retirement controlled and localized.

---

## 5. Temporary migration switch

Temporary site-config key:

`ledgix_erpnext_native_tax_authority`

Current behavior:

- missing / `0`: Legacy Bridge;
- `1`: ERPNext Native.

This is an **engineering migration switch only**.

It is not:

- a client business setting;
- a final feature flag;
- a substitute for Desk tax configuration.

It must be removed after native runtime parity passes.

The final product has no choice between two tax engines.

Final state:

```text
ERPNext Native only
```

---

## 6. Native contract enforcement

When the temporary native mode is enabled, Ledgix does not append tax rows.

Before calculating totals, the native boundary now invokes ERPNext's own
`set_taxes_and_charges()` server method. This is important for the pinned
ERPNext v15.121.3 lifecycle because native tax rows can be populated there from
Accounts Settings / Sales Taxes and Charges Templates / Item Tax Templates.
Ledgix does not reproduce that logic and does not append monetary rows itself.

The native order is now:

```text
ERPNext set_missing_values()
    -> ERPNext set_taxes_and_charges()
    -> ERPNext calculate_taxes_and_totals()
    -> Ledgix native tax contract validation
```

Mapped return documents that intentionally preserve the original ERPNext tax
rows continue to use the non-recalculation path rather than rebuilding return
taxes in Ledgix.

It inspects the ERPNext document and fails closed if configuration is inconsistent.

Checks include:

- Sales Invoice/POS Invoice only;
- valid Company;
- no `[LEDGIX-TAX]` managed rows;
- Sales Taxes and Charges Template belongs to the same Company;
- template is enabled;
- tax accounts exist;
- tax accounts belong to the same Company;
- tax accounts are not group/disabled accounts;
- Item Tax Templates exist;
- Item Tax Templates belong to the same Company;
- Item Tax Templates are enabled;
- positive Item Tax Template accounts have a corresponding invoice tax row.

If no tax configuration resolves at all, the contract emits a warning rather than automatically inventing a tax.

That case is valid only for an intentionally non-taxable/exempt transaction.

---

## 7. Active transaction services changed

### 7.1 ERPNext selling

File:

`apps/ledgix_saas/services/erpnext_selling.py`

Changed:

- removed direct transaction-layer import of `erpnext_tax_foundation`;
- Sales Invoice construction now calls the authority boundary;
- native return construction now calls the authority boundary.

Default current behavior remains the old proven bridge until the native gate is run.

### 7.2 ERPNext POS

File:

`apps/ledgix_saas/services/erpnext_pos.py`

Changed:

- removed direct transaction-layer import of `erpnext_tax_foundation`;
- POS Invoice construction now calls the authority boundary.

Again, default behavior remains unchanged until the native switch is deliberately enabled for integration testing.

---

## 8. Static regression contract

New test:

`apps/ledgix_saas/setup/test_fbr_redesign_phase1_tax_authority_contract.py`

It prevents:

- transaction services from directly importing the old tax foundation again;
- native branch from creating `[LEDGIX-TAX]` rows;
- Ledgix from replacing ERPNext's own native tax-row population;
- calculation from running before ERPNext native tax-row population;
- removal of the native validation boundary by accident;
- the temporary switch being presented as normal business configuration.

This test does not replace accounting runtime tests.

---

## 9. Read-only runtime probe

New module:

`apps/ledgix_saas/migration/fbr_redesign_phase1_native_tax_probe.py`

Runner:

`scripts/run_fbr_redesign_phase1_native_tax_probe.sh`

The probe is restricted to:

`ledgix-erpnext.local`

It performs no tax writes and no FBR network traffic.

It reports:

- Accounts Settings tax flags;
- Sales Taxes and Charges Templates;
- each native tax row;
- Item Tax Templates;
- Item/Item Group tax assignments;
- Sales Tax Rules;
- POS Profile tax configuration;
- remaining old Ledgix tax record counts;
- unmatched Item Tax Template accounts;
- temporary tax-authority switch state.

Later local command:

```bash
cd ~/data_drive/pos
bash scripts/run_fbr_redesign_phase1_native_tax_probe.sh ledgix-erpnext.local
```

This should be the first runtime command after pulling the GitHub work.

---

## 10. What has NOT changed yet

Phase 1 has deliberately **not** yet:

- enabled the native switch;
- changed client tax rates;
- created client tax accounts;
- created Tax Categories;
- created Sales Taxes and Charges Templates;
- created Item Tax Templates;
- created Tax Rules;
- changed POS Profile tax configuration;
- migrated old tax records;
- deleted old tax DocTypes;
- deleted `erpnext_tax_foundation.py`;
- changed FBR payload snapshots;
- changed Production FBR state.

Therefore this GitHub batch is safe to pull before the runtime proof.

---

## 11. Required runtime parity before cutover

The integration-site gate must prove at least:

1. Standard taxable Sales Invoice;
2. Standard taxable POS Invoice;
3. same tax/accounting result from native configuration;
4. tax-inclusive case where applicable;
5. zero-rated case;
6. exempt/not-applicable case;
7. mixed-rate items;
8. native Sales Invoice return;
9. native POS return;
10. GL Entries use the configured native tax accounts;
11. no `[LEDGIX-TAX]` rows in native mode;
12. FBR snapshot generation is not yet allowed to silently rely on removed old calculation data.

Special cases are added only where actually required:

- Third Schedule/notified retail value;
- Extra Tax;
- Further Tax;
- FED;
- sales tax withheld.

Do not create fake complexity for a client that does not legally need those cases.

---

## 12. Cutover sequence from here

### Gate 1 — read-only site inventory

Run the Phase 1 native-tax probe.

### Gate 2 — configure native ERPNext tax masters

Based on actual client/integration requirements, configure:

- Accounts;
- Tax Category;
- Sales Taxes and Charges Template;
- Item Tax Templates;
- Tax Rules;
- POS Profile tax fields;
- Accounts Settings only where required.

### Gate 3 — native parity tests

Enable the temporary native switch **only on `ledgix-erpnext.local`** and run test transactions.

### Gate 4 — make native authority default

Only after parity is green:

- switch the integration runtime to native;
- remove legacy fallback from the transaction authority module;
- remove the temporary site-config switch;
- remove active calls into the old tax calculation engine.

### Gate 5 — old model retirement

Then proceed with:

- old Ledgix Tax Profile retirement;
- old Ledgix Tax Category retirement;
- old Ledgix Tax Rate retirement;
- replacement of Ledgix Item Tax Profile with FBR Item Mapping;
- removal of Company old tax-account custom fields after migration proof;
- removal of old tax UI.

---

## 13. Phase 1 definition of done

Phase 1 is complete only when:

- Sales Invoice uses ERPNext-native tax configuration;
- POS Invoice uses ERPNext-native tax configuration;
- native returns preserve/reverse the native ERPNext tax result;
- GL uses native configured accounts;
- transaction services contain no direct old tax-engine call;
- `erpnext_tax_authority.py` no longer has a legacy fallback;
- `ledgix_erpnext_native_tax_authority` switch is removed;
- no current transaction creates `[LEDGIX-TAX]` rows;
- required runtime parity cases pass;
- old financial tax masters are no longer required for new business.

At that point Phase 2 can safely introduce the clean FBR-only data model without carrying the old monetary tax architecture forward.
