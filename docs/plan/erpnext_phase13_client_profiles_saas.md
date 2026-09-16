# Phase 13 — Client Profiles and SaaS Productization

**Status:** IMPLEMENTED, FINAL GUARDED GATE PENDING  
**Authority:** `docs/plan/erpnext_core_migration_plan.md`  
**Stack:** Frappe v15 + ERPNext v15 + `ledgix_saas`

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

Use for invoice/e-invoicing clients that do not need stock operations.

### Small Retail

- Sales Invoice + POS enabled;
- normal inventory and buying enabled;
- advanced inventory disabled;
- B2B disabled;
- FBR enabled.

Use for normal small-shop POS deployments.

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

Use for invoice-led wholesale/account-customer businesses.

### Mixed

- retail POS;
- B2B;
- buying;
- normal + advanced inventory;
- FBR;
- accounting.

Use when one client runs both counter retail and account/B2B operations.

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

It does **not** create:

- Items;
- Customers;
- Suppliers;
- Sales Invoices;
- Purchase Invoices;
- Stock Entries;
- Accounts;
- parallel Ledgix business masters or ledgers.

If required native ERPNext configuration is missing, setup fails closed and names the target configuration screen.

FBR token/seller activation is a separate compliance step. FBR Settings must exist, but live activation remains an explicit operator decision.

---

## 4. Setup audit metadata

`Ledgix Business Profile` now records:

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

Business Profile feature flags still curate navigation only. ERPNext/Frappe permissions remain authorization authority.

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

This complements the repository-level `scripts/validate_erpnext_dependency.sh` and deployment helpers that install ERPNext before Ledgix migration.

---

## 7. Client provisioning sequence

A fresh client uses the same repository and app code:

```text
Provision Frappe/ERPNext v15 site
        |
        v
Install ERPNext + Ledgix
        |
        v
Migrate / build
        |
        v
Run client dependency preflight
        |
        v
Create/configure standard ERPNext Company + required native masters
        |
        v
Open Ledgix Setup Wizard
        |
        v
Select one Ledgix Business Profile
        |
        v
Resolve readiness blockers
        |
        v
Apply configuration
        |
        v
Configure/validate FBR before live submission
        |
        v
Client acceptance
```

No code branch, custom fork or per-client business engine is required.

---

## 8. Phase 12 boundary

Phase 13 never unfreezes or edits Phase 12 historical Ledgix business records.

The final runtime gate verifies:

- Phase 12 retirement state is Frozen;
- the saved digest matches before Phase 13;
- the digest still matches after applying setup configuration;
- no ERPNext business-master counts change;
- the original integration-site Business Profile is restored after the test.

---

## 9. Final gate

Runner:

```bash
bash scripts/run_erpnext_phase13_final_gate.sh ledgix-erpnext.local
```

It runs:

1. repository/local CI;
2. temporary Redis runtime;
3. migrate;
4. Ledgix asset build;
5. installed-app check;
6. client-site ERPNext dependency preflight;
7. Phase 6–13 fail-closed static contracts;
8. Phase 13 runtime profile matrix;
9. configuration-only apply proof;
10. business-master count proof;
11. Phase 12 digest proof;
12. integration-site profile restoration proof.

Required final result:

- `phase13_complete=true`;
- `migration_complete=true`;
- no failed cases;
- Phase 12 legacy snapshot still matches;
- no ERPNext business-master counts changed.

---

## 10. Exit gate

Phase 13 closes when a new client can be provisioned from the same Ledgix codebase by selecting configuration/presets and standard ERPNext setup only, with no code edits or custom fork.

After Phase 13 the ERPNext Core Migration is complete on the guarded integration workflow. Remaining work is release/client acceptance, production provisioning, operational monitoring and any later separately-approved physical deletion of historical legacy schema after the observation period.
