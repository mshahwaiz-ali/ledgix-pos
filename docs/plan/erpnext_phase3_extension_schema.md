# ERPNext Phase 3 Extension Schema Contract

**Status:** implementation prepared on `erpnext-core-migration`; runtime final gate required before Phase 3 is marked complete.

## Purpose

Phase 3 establishes the target Ledgix-on-ERPNext schema before any transactional authority cutover. ERPNext remains authoritative for standard business concepts; Ledgix stores only product configuration and FBR/legal metadata that generic ERPNext records do not express.

## Standard master ownership

- Product master: ERPNext `Item`
- Product grouping: ERPNext `Item Group`
- Customer: ERPNext `Customer`
- Supplier: ERPNext `Supplier`
- Pricing: ERPNext `Price List`, `Item Price`, `Pricing Rule`
- Payment method: ERPNext `Mode of Payment`
- Stock identity/tracking: ERPNext Warehouse/Batch/Serial/ledger model

No replacement Ledgix master is introduced in Phase 3.

## Customer FBR extension

ERPNext `Customer` receives Ledgix custom fields for:

- Buyer Registration Type
- Buyer NTN/CNIC
- Buyer STRN
- Buyer Province
- Buyer FBR Address
- FBR verification status
- last verification date

Commercial identity, contacts, addresses, payment terms, credit and receivables remain native ERPNext responsibilities.

## FBR transaction envelope

Both `Sales Invoice` and `POS Invoice` receive server-managed Ledgix fields for:

- FBR status
- FBR invoice number/reference
- submitted timestamp
- error code/message
- reconciliation-required state
- submission trigger
- client-sale/idempotency identifier
- immutable header snapshot version + JSON

Returns/credit notes are covered because ERPNext uses the same native sales transaction types with return semantics.

## Immutable line snapshot

`Sales Invoice Item` and `POS Invoice Item` receive read-only/no-copy snapshot fields for:

- source Ledgix FBR Item Profile
- HS Code
- FBR UOM
- Sales Type
- FBR rate description
- Sandbox Scenario ID
- SRO Schedule Number
- SRO Item Serial Number
- tax basis
- Notified Retail Price / Third Schedule basis
- Sales Tax Withheld at Source
- Extra Tax
- Further Tax
- FED Payable
- snapshot version + JSON

These fields are storage contracts only in Phase 3. Phase 4 proves monetary tax parity before ERPNext becomes the tax authority, and Phase 9 switches FBR submission to ERPNext transactions.

## Item Tax Profile transition

`Ledgix Item Tax Profile` now supports an `ERPNext Item` link as the target reference. The legacy `Ledgix Item` link is retained but made optional for migration compatibility.

The migration patch only backfills the ERPNext link when a matching native Item already exists. It never creates or synchronizes Items; full master migration remains Phase 5.

## Ledgix Business Profile

A site-level Single DocType configures product experience only:

- Invoice + FBR Only
- Small Retail
- Full Retail
- B2B
- Mixed

Feature flags control experience/workspace intent such as POS, inventory, buying, advanced inventory, B2B, FBR and accounting visibility. They do **not** replace server-side permissions and do not duplicate Company, Warehouse, Item, Customer or pricing masters.

## Role mapping

Phase 3 adds explicit `Custom DocPerm` grants for Ledgix Cashier, Manager and Admin on the relevant standard ERPNext DocTypes. Native ERPNext role permissions remain intact.

Broad intent:

- Cashier: sales/POS/customer/payment operations plus read access to item/pricing/stock references.
- Manager: operational master maintenance, selling, buying, stock and transaction cancellation/amendment where appropriate.
- Admin: full Ledgix operational administration on the mapped standard DocTypes.

## Migration mechanism

The schema is installed through:

1. a post-model-sync patch for existing sites;
2. an idempotent `after_migrate` synchronizer for future schema evolution;
3. standard Ledgix fixture filters for exported custom fields;
4. a Phase 3 integration-site final gate that re-runs synchronization twice and checks duplicate-free results.

## Exit gate

Phase 3 passes only when the integration-site gate proves:

- all target custom fields exist with the intended types/options;
- immutable snapshot fields are read-only/no-copy;
- each Custom Field exists exactly once after repeated sync;
- ERPNext Customer persists FBR buyer metadata;
- Ledgix Item Tax Profile can reference ERPNext Item without a legacy Item;
- Sales Invoice persists the FBR envelope and immutable line snapshot;
- Business Profile defaults are deterministic;
- Ledgix role grants exist on standard ERPNext DocTypes;
- Phase 2 core behavior remains green.

No production authority cutover occurs in this phase.
