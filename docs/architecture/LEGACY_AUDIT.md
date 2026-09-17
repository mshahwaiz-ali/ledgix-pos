# Ledgix Legacy Audit and Retention Policy

## Decision summary

The ERPNext-core migration is complete. Legacy Ledgix business-engine records are no longer active authority, but many are intentionally retained as **frozen historical migration/audit evidence**.

Do **not** drop legacy tables merely because their business function moved to ERPNext.

The active rule is:

> New business activity is written to ERPNext. Historical legacy rows remain immutable unless a separate evidence-preserving retirement project proves physical removal is safe.

---

## Category 1 — Active product-specific Ledgix capability: retain

These capabilities remain first-class Ledgix ownership because ERPNext is not intended to replace the product/compliance layer itself.

### Retained product pages

- `ledgix-pos`
- `business-intelligence-center` — Inventory Intelligence
- `ledgix-tax-center`
- `ledgix-setup`

### Retained product/configuration DocTypes and modules

Examples include:

- `Ledgix Business Profile`
- `Ledgix Brand Settings`
- `Ledgix User Profile`
- `Ledgix Tax Profile`
- `Ledgix Tax Category`
- `Ledgix Tax Rate`
- `Ledgix Item Tax Profile`
- `Ledgix FBR Settings`
- `Ledgix FBR Submission Log`
- `Ledgix Tax Audit Log`
- legacy-retirement state/digest controls
- retained FBR/readiness/reconciliation/printing/device/UAT support records required by the current product

These are not duplicate ERP business ledgers. They provide Ledgix UX, profile/branding, tax/FBR, audit, safety and orchestration capabilities.

---

## Category 2 — Historical/read-only migration evidence: retain frozen

`apps/ledgix_saas/api/legacy_retirement.py` defines the authoritative frozen set.

### Top-level legacy business DocTypes

- `Ledgix Item`
- `Ledgix Category`
- `Ledgix Customer`
- `Ledgix Supplier`
- `Ledgix Price List`
- `Ledgix Item Price`
- `Ledgix Payment Method`
- `Ledgix Sale`
- `Ledgix Purchase`
- `Ledgix Sales Return`
- `Ledgix POS Shift`
- `Ledgix POS Hold`
- `Ledgix Payment`
- `Ledgix Stock Movement`
- `Ledgix Stock Lot`
- `Ledgix Stock Serial`

### Legacy child DocTypes

- `Ledgix Sale Item`
- `Ledgix Sale Payment`
- `Ledgix Purchase Item`
- `Ledgix Sales Return Item`
- `Ledgix POS Hold Item`
- `Ledgix Payment Allocation`
- `Ledgix Stock Lot Allocation`

### Why they remain physically present

Phase 12 deliberately preserves these rows so that the system can retain:

- deterministic legacy snapshot/digest evidence;
- source-to-ERPNext migration traceability;
- mapping reconciliation;
- submitted/cancelled historical records;
- controlled rollback evidence if ever required;
- proof that legacy data did not mutate after cutover.

After the retirement state is frozen, document-event guards reject writes to these DocTypes. A tightly controlled internal bypass exists only for explicit migration/rollback handling.

### ERPNext replacements

| Frozen legacy concept | Current authority |
|---|---|
| Ledgix Item | ERPNext `Item` |
| Ledgix Category | ERPNext `Item Group` |
| Ledgix Customer | ERPNext `Customer` |
| Ledgix Supplier | ERPNext `Supplier` |
| Ledgix Price List | ERPNext `Price List` |
| Ledgix Item Price | ERPNext `Item Price` |
| Ledgix Payment Method | ERPNext `Mode of Payment` |
| Ledgix Sale | ERPNext `Sales Invoice` / `POS Invoice` |
| Ledgix Sales Return | ERPNext return/credit note documents |
| Ledgix Purchase | ERPNext `Purchase Order` / `Purchase Receipt` / `Purchase Invoice` |
| Ledgix Payment | ERPNext `Payment Entry` or POS payment rows |
| Ledgix POS Shift | ERPNext `POS Opening Entry` / `POS Closing Entry` |
| Ledgix POS Hold | ERPNext draft Sales/POS Invoice with Ledgix hold metadata |
| Ledgix Stock Movement | ERPNext `Stock Entry` / `Stock Reconciliation` / native stock vouchers |
| Ledgix Stock Lot / Serial | ERPNext `Batch`, `Serial No`, Serial and Batch Bundle, Stock Ledger |

---

## Category 3 — Obsolete active code/navigation: remove or redirect

Code that **creates new records in the frozen business DocTypes**, exposes them as current business masters, or presents them as an operator workflow is obsolete.

Safe cleanup applied in the final pre-client-testing pass includes:

- active workspace navigation uses ERPNext masters/documents/reports instead of frozen business DocTypes;
- retained custom Ledgix pages resolve/read/write ERPNext-native authority;
- the old `setup/demo_data.py` legacy seeder no longer creates legacy masters/transactions and now routes to the ERPNext-native local demo utility;
- completed migration plans are archived rather than presented as active product documentation.

The compatibility API layer may still contain old endpoint names where external/UI callers depend on them, but those endpoints must route to ERPNext-native services. Endpoint naming compatibility is not legacy business authority.

---

## Physical schema deletion rule

A legacy DocType/table may be physically removed only when **all** of the following are proven:

1. no import, hook, API compatibility route, report, print format, workspace, test, patch or migration references it;
2. no Phase-12 digest/snapshot/reconciliation logic requires it;
3. no retained historical row is required for audit or client recovery;
4. no legacy-to-ERPNext mapping depends on it;
5. backup/restore evidence is captured before deletion;
6. the removal has an explicit migration path and rollback plan.

The current audit does **not** establish those conditions for the frozen business DocTypes, so their database schema is retained.

---

## Navigation rule

The active Ledgix workspace must not expose frozen business masters/transactions as current navigation.

Current user-facing authority should resolve to:

- ERPNext native forms/lists/reports for masters, buying, sales, accounting and stock;
- retained Ledgix POS, Inventory Intelligence, Tax & FBR Center and Setup Wizard for product-specific UX.

Role/profile-aware visibility remains a navigation concern only; ERPNext/Frappe permissions remain the security authority.

---

## Demo-data rule

New demo data must not repopulate the frozen historical Ledgix business ledgers.

The supported entrypoint is:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.seed
```

It creates ERPNext Items, Customers, Suppliers, warehouses, purchase/stock vouchers, Sales/POS Invoices, returns and payments. The cleanup utility is marker-scoped and does not delete arbitrary historical rows.

---

## Source of truth

For implementation behavior, use:

```text
apps/ledgix_saas/api/legacy_retirement.py
apps/ledgix_saas/setup/erpnext_phase12_legacy_retirement.py
apps/ledgix_saas/hooks.py
```

Historical rationale and phase evidence live under `docs/archive/migration/`.
