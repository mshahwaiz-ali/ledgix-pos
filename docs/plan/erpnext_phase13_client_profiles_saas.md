# Phase 13 — Client Profiles and SaaS Productization

**Status:** COMPLETE  
**Closed:** 2026-09-16  
**Final guarded migration gate HEAD:** `d813d26d16a11665522da98c7bd542a7cc09c53f`  
**Authority:** `docs/plan/erpnext_core_migration_plan.md`  
**Stack:** Frappe `15.113.4` + ERPNext `15.121.3` + `ledgix_saas`

---

## 1. Goal

Phase 13 turns the completed ERPNext-backed Ledgix product into one configurable codebase for different client complexity levels.

The rule is:

> **Client differences are configuration, not forks.**

No profile creates a parallel Item, Customer, accounting, stock, sales or purchase engine. ERPNext remains business authority for every client profile.

---

## 2. Supported presets

The existing `Ledgix Business Profile` is the canonical product-profile configuration.

### Invoice + FBR Only

- Sales Invoice enabled;
- POS disabled;
- inventory/buying disabled;
- B2B mode disabled;
- FBR enabled;
- accounting workspace enabled.

### Small Retail

- Sales Invoice + POS enabled;
- normal inventory and buying enabled;
- advanced inventory disabled;
- B2B disabled;
- FBR enabled.

### Full Retail

Small Retail plus:

- advanced inventory;
- Stock Entry/Reconciliation visibility;
- Serial/Batch workflows.

### B2B

- Sales Invoice enabled;
- POS disabled;
- B2B enabled;
- inventory/buying disabled by default;
- FBR and accounting enabled.

### Mixed

- retail POS;
- B2B;
- buying;
- normal + advanced inventory;
- FBR;
- accounting.

---

## 3. Setup Wizard

Desk page:

- `/app/ledgix-setup`

Server service:

- `ledgix_saas.api.client_setup`

Access:

- `System Manager`;
- `Ledgix Admin`.

The wizard is intentionally **configuration-only**.

It may:

- select a Business Profile preset;
- select an existing ERPNext Company;
- resolve/select an enabled Selling Price List;
- resolve/select an enabled leaf Warehouse when the profile needs stock;
- resolve/select an enabled POS Profile when POS is enabled;
- validate POS Profile customer/warehouse/price-list/payment configuration;
- set safe site defaults for Company, Selling Price List and Warehouse when explicitly requested;
- record setup audit metadata on `Ledgix Business Profile`.

It does **not** create Items, Customers, Suppliers, invoices, stock/accounting transactions, accounts or parallel Ledgix business masters/ledgers.

Explicit invalid Price List/Warehouse/POS Profile selections fail closed. Blank optional selections may resolve safe existing site defaults.

FBR token/seller activation is a separate compliance step. FBR Settings must exist, but live activation remains an explicit operator decision.

---

## 4. Setup audit metadata

`Ledgix Business Profile` records:

- Setup Complete;
- Setup Version;
- Configured Company;
- Setup Completed At;
- Setup Completed By;
- hidden setup snapshot JSON.

This is configuration/audit metadata only. It never becomes a second source of truth for Company, Warehouse, Price List or POS Profile.

---

## 5. Product-shell behavior

Phase 11 remains the navigation authority.

Phase 13 adds only one new product page:

- `Setup Wizard` under Administration.

Visibility:

- System Manager: visible;
- Ledgix Admin: visible;
- Ledgix Manager: hidden;
- Ledgix Cashier: hidden.

Business Profile feature flags curate navigation only. ERPNext/Frappe permissions remain authorization authority.

---

## 6. Deployment dependency preflight

Read-only site preflight:

```bash
bash scripts/run_ledgix_client_preflight.sh <site>
```

It fails if:

- `frappe` is not installed;
- `erpnext` is not installed;
- `ledgix_saas` is not installed;
- Frappe is not major version 15;
- ERPNext is not major version 15;
- the Ledgix app dependency contract does not require ERPNext.

---

## 7. Final guarded gate evidence

Runner:

```bash
bash scripts/run_erpnext_phase13_final_gate.sh ledgix-erpnext.local
```

Final guarded migration gate ran against:

- branch: `main`;
- HEAD: `d813d26d16a11665522da98c7bd542a7cc09c53f`;
- site: `ledgix-erpnext.local`;
- Frappe: `15.113.4`;
- ERPNext: `15.121.3`;
- Ledgix app: `0.0.1` / `main`.

### Static evidence

- repository validation passed;
- shell/Python/JSON/TOML validation passed;
- ERPNext v15 dependency contract passed;
- secret scan passed;
- fail-closed Phase 6–13 static suite passed **90/90**.

### Runtime evidence

All **6/6** Phase 13 cases passed:

1. `site_dependency_and_setup_surface`;
2. `five_client_profile_presets`;
3. `profile_specific_readiness_requirements`;
4. `apply_configuration_without_fork`;
5. `configuration_creates_no_business_masters`;
6. `integration_site_state_restored`.

The gate proved:

- all five presets on one codebase;
- profile-specific readiness requirements;
- Invoice + FBR Only does not require a POS Profile;
- POS-enabled profiles require valid native POS configuration;
- explicit invalid Selling Price List/Warehouse/POS Profile selections fail closed;
- FBR Production activation remains a non-blocking setup warning and separate compliance decision;
- one real Mixed-profile configuration application persisted setup audit metadata;
- Product Shell reflected the applied profile for Admin and Cashier contexts;
- configuration created **zero** new ERPNext business masters;
- ERPNext business-master counts were unchanged before/after apply and restore;
- Phase 12 retirement state remained frozen;
- Phase 12 deterministic historical digest still matched;
- original integration-site Business Profile/setup state was restored without error.

Final machine verdict:

- `phase13_complete=true`;
- `migration_complete=true`;
- `failed_cases=[]`;
- `passed=true`.

---

## 8. Phase 12 boundary

Phase 13 never unfreezes or edits Phase 12 historical Ledgix business records.

The final gate proved the Phase 12 frozen snapshot remained stable before, during and after configuration testing. No legacy schema or historical business rows were deleted.

---

## 9. Exit gate — PASSED

Phase 13 is closed. A client can be represented through one Ledgix codebase using supported Business Profile configuration plus standard ERPNext setup, without a client-specific implementation fork or duplicate business engine.

**ERPNext Core Migration Phases 0–13 are COMPLETE.**

There is no Phase 14. The next workstream is:

**Client Acceptance + Production Provisioning + Release Hardening**

See:

- `docs/plan/client_acceptance_production_release_hardening.md`;
- `docs/production/client_lifecycle.md`.
