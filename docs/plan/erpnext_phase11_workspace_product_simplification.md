# Phase 11 — Workspace and Product Simplification

**Implementation branch:** `main`  
**Integration site:** `ledgix-erpnext.local`  
**Pinned stack:** Frappe 15.113.4 / ERPNext 15.121.3

## Goal

Make the combined ERPNext + Ledgix system feel like one Ledgix product without rebuilding standard ERPNext CRUD screens.

Phase 11 is a **navigation/product-shell** cutover only. It does not change business authority or grant permissions.

## Authority rule

- ERPNext/Frappe permissions remain authoritative.
- ERPNext standard Forms/Lists remain authoritative for Customer, Item, Supplier, Sales/POS Invoice, Payment Entry, Purchase documents, Warehouse and stock documents.
- Ledgix retains only differentiated product pages:
  - `ledgix-pos`;
  - `ledgix-tax-center`;
  - `business-intelligence-center`.
- `Ledgix Business Profile` controls product visibility only; it is explicitly not an authorization system.

## Workspace design

The public `Ledgix` Workspace is repository-authoritative and force-synced after migrate.

Cards:

1. Sales & POS
2. Catalog & Pricing
3. Buying & Suppliers
4. Inventory & Stock
5. Reports & Insights
6. Tax & FBR
7. Administration

Operational links point to ERPNext standard DocTypes and native-backed Ledgix reports. Legacy duplicate operational DocTypes are forbidden from the active workspace.

## Role experience

### Ledgix Cashier

- POS-enabled profile: landing route is Ledgix POS.
- POS-disabled profile: landing route is Ledgix Workspace.
- Workspace exposure is intentionally minimal and still constrained by server permissions.

### Ledgix Manager

- Ledgix Workspace is the landing surface.
- Operational sales/buying/stock/report/FBR links follow enabled profile features.
- Admin-only product configuration is hidden.

### Ledgix Admin

- Ledgix Workspace is the landing surface.
- Enabled operations plus Administration are visible.
- Business Profile, branding, user profile and compliance configuration remain available.

### System Manager

- Not restricted to the curated Ledgix sidebar.
- Full Frappe/ERPNext workspace navigation remains available for technical administration.

## Business Profile behavior

Existing profile flags from Phase 3 are consumed directly:

- Invoice + FBR Only
- Small Retail
- Full Retail
- B2B
- Mixed

No new configuration engine is introduced in Phase 11.

Examples:

- Invoice + FBR Only / B2B hides POS, buying and stock controls from Cashier navigation.
- Small Retail exposes POS and normal retail flow but not advanced manual stock controls.
- Full Retail exposes buying and advanced stock controls to Manager/Admin.
- Mixed exposes retail + B2B + buying/inventory according to role.

Phase 13 may later add a setup wizard, but it must configure these same flags rather than create another business engine.

## Sidebar rule

For Ledgix Cashier/Manager/Admin users, Desk workspace navigation is curated to Ledgix so normal users do not need ERPNext's full workspace tree.

This is UX only. Direct access still depends on Frappe permissions.

System Manager is exempt from sidebar curation.

## Migration behavior

`ledgix_saas.setup.erpnext_phase11_product_shell.after_migrate`:

- force-reloads the repository Ledgix Workspace;
- installs Cashier/Manager/Admin/System Manager workspace roles;
- verifies legacy operational DocTypes are absent;
- verifies required ERPNext targets are present;
- synchronizes profile-aware role home metadata;
- clears cache.

Saving `Ledgix Business Profile` refreshes profile-aware landing metadata immediately.

## Final gate

Runner:

`scripts/run_erpnext_phase11_final_gate.sh ledgix-erpnext.local`

Required proofs:

- Ledgix Workspace exposes native ERPNext operational targets;
- Cashier has workspace access for non-POS profiles;
- only three differentiated custom product pages remain in active workspace navigation;
- all five Business Profiles produce the intended navigation surface;
- Cashier/Manager/Admin/System Manager role behavior is correct;
- profile flags do not modify `Custom DocPerm` rows;
- no legacy business ledger counts change;
- current Business Profile remains unchanged by the gate.

Phase 11 closes only when `phase11_complete=true`, `phase12_ready=true` and no cases fail.

## Next

Phase 12 — Legacy Freeze, Reconciliation and Retirement.
