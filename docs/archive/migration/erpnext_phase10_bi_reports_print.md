# Phase 10 — BI, Reports and Print Migration

**Implementation branch:** `main`  
**Integration site:** `ledgix-erpnext.local`  
**Pinned stack:** Frappe 15.113.4 / ERPNext 15.121.3

## Goal

Phase 10 removes the remaining active reporting/print dependency on duplicate Ledgix business ledgers while retaining Ledgix UX, analytics and branding.

ERPNext owns the source data. Ledgix owns presentation and differentiated analysis.

## BI authority

Active Inventory Intelligence reads:

- Item / Item Group;
- Bin;
- Stock Ledger Entry;
- Sales Invoice;
- POS Invoice;
- Purchase Invoice;
- Batch / Serial identity carried by native stock entries.

The legacy `ledgix_saas.api.inventory_intelligence.get_inventory_intelligence_data` RPC is overridden to an ERPNext-native implementation so the existing page contract can remain stable.

Consolidated POS accounting Sales Invoices are excluded from native sales analytics when their source POS Invoices are already counted.

## Active report authority

The retained Ledgix report names remain available for user continuity, but their Python data sources and filter masters are native ERPNext.

- Ledgix Current Stock -> Item + Bin + Item Reorder + Item Price;
- Ledgix Low Stock -> Item + Bin + Item Reorder;
- Ledgix Stock Movement Report -> Stock Ledger Entry;
- Ledgix Sales Report -> Sales Invoice + POS Invoice;
- Ledgix Sales Return Report -> native Sales/POS return invoices;
- Ledgix Purchase Report -> Purchase Invoice;
- Ledgix Customer Statement -> GL Entry / Customer;
- Inventory Intelligence Report -> ERPNext-native inventory intelligence.

Historical/disabled report code is not deleted in Phase 10; Phase 12 owns retirement cleanup.

## Print authority

New Ledgix print formats are bound directly to native ERPNext documents:

- `Ledgix ERPNext Tax Invoice` -> `Sales Invoice` (A4);
- `Ledgix ERPNext POS Receipt` -> `POS Invoice` (80mm thermal).

A native return uses the same underlying native document and renders as a Credit Note / POS return rather than creating a separate Ledgix financial document.

Print context is read-only and combines:

- ERPNext document identity, customer, totals, payments and return linkage;
- immutable Ledgix FBR line snapshot JSON already stored on the native invoice;
- persisted Phase 9 FBR status, invoice number, reference and reconciliation state;
- self-contained QR generated from the persisted official FBR invoice number;
- Ledgix brand/FBR presentation settings.

The legacy `Ledgix B2B Invoice` and `Ledgix Thermal Receipt` remain available only for historical `Ledgix Sale` records. New checkout results never restore a legacy Sale ID just to print.

## POS print handoff

The Phase 8 compatibility response now returns:

- `native_document`;
- `print_doctype`;
- `print_format`;
- `print_mode`;
- `print_deferred = false`.

The Phase 10 client bridge opens/auto-prints the native ERPNext target and never builds a `Ledgix Sale` print URL.

## Safety rules

- no ERPNext core modifications;
- no new Ledgix Sale/Purchase/Payment/Stock ledger writes;
- no FBR submission/network activity is required for report or print migration;
- the guarded Phase 10 gate blocks any attempted FBR/PRAL adapter call;
- legacy records and legacy print formats remain preserved for historical access;
- Phase 12 remains responsible for final freeze/retirement cleanup.

## Final gate

Runner:

`scripts/run_erpnext_phase10_final_gate.sh ledgix-erpnext.local`

The guarded runtime gate must prove:

1. Sales Invoice A4 print context and rendered HTML;
2. POS Invoice thermal print context and rendered HTML;
3. native Credit Note label and original FBR invoice reference;
4. persisted FBR number + self-contained QR rendering without a network call;
5. POS compatibility returns native print targets, never a legacy Sale print identity;
6. active Ledgix stock/sales/returns/purchase/customer reports execute from ERPNext-native sources;
7. Inventory Intelligence executes from native ERPNext stock/sales/purchase sources;
8. legacy business ledger counts stay unchanged;
9. real FBR/PRAL adapter calls remain zero.

Phase 10 closes only when `phase10_complete=true`, `phase11_ready=true`, every runtime case passes and `real_fbr_network_calls=0`.

## Next

Phase 11 — Workspace and Product Simplification.
