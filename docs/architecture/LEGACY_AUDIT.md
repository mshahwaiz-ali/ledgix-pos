# Ledgix Legacy Audit and Retention Policy

**Status:** CURRENT  
**ERPNext-core migration:** COMPLETE  
**Applies to:** Frappe 15 / ERPNext 15 / `ledgix_saas`

## Decision summary

The ERPNext-core migration is complete. Legacy Ledgix business-engine records are no longer active authority, but many remain intentionally preserved as **frozen historical migration and audit evidence**.

The operating rule is:

> New business activity is written to ERPNext. Frozen legacy rows remain immutable unless a separate evidence-preserving retirement project proves physical removal is safe.

Do **not** reactivate a legacy DocType merely because an old endpoint, report, fixture or migration document still mentions it.

---

## 1. Current ownership classes

### 1.1 Active Ledgix product/compliance capability — RETAIN

These remain first-class Ledgix ownership because they are product, UX, compliance, configuration or safety capabilities rather than duplicate ERP business ledgers.

Retained product pages include:

- `ledgix-pos`
- `business-intelligence-center`
- `ledgix-tax-center`
- `ledgix-setup`

Retained product/configuration records include, among others:

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
- readiness, reconciliation, printing/device and UAT support records that remain part of the current product

These records may augment ERPNext transactions. They must not become parallel Customer, Item, stock, accounting, payment or invoice ledgers.

### 1.2 Frozen historical business-engine data — RETAIN READ-ONLY

`apps/ledgix_saas/api/legacy_retirement.py` defines the authoritative frozen set.

Top-level frozen DocTypes:

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

Frozen child DocTypes:

- `Ledgix Sale Item`
- `Ledgix Sale Payment`
- `Ledgix Purchase Item`
- `Ledgix Sales Return Item`
- `Ledgix POS Hold Item`
- `Ledgix Payment Allocation`
- `Ledgix Stock Lot Allocation`

After the retirement state is frozen, document-event guards reject ordinary writes to these DocTypes. The internal write bypass is for an explicitly controlled migration/rollback procedure only; it is not an operating API.

---

## 2. ERPNext replacements

| Frozen legacy concept | Current authority |
|---|---|
| Ledgix Item | ERPNext `Item` |
| Ledgix Category | ERPNext `Item Group` |
| Ledgix Customer | ERPNext `Customer` |
| Ledgix Supplier | ERPNext `Supplier` |
| Ledgix Price List | ERPNext `Price List` |
| Ledgix Item Price | ERPNext `Item Price` / native pricing |
| Ledgix Payment Method | ERPNext `Mode of Payment` |
| Ledgix Sale | ERPNext `Sales Invoice` / `POS Invoice` |
| Ledgix Sales Return | ERPNext return `Sales Invoice` / return `POS Invoice` |
| Ledgix Purchase | ERPNext `Purchase Order` / `Purchase Receipt` / `Purchase Invoice` |
| Ledgix Payment | ERPNext `Payment Entry` or native POS payment rows |
| Ledgix POS Shift | ERPNext `POS Opening Entry` / `POS Closing Entry` |
| Ledgix POS Hold | Draft ERPNext `POS Invoice` / `Sales Invoice` with Ledgix hold metadata |
| Ledgix Stock Movement | ERPNext `Stock Entry` / `Stock Reconciliation` / native stock vouchers |
| Ledgix Stock Lot / Serial | ERPNext `Batch`, `Serial No`, Serial and Batch Bundle, Stock Ledger |

The practical operating flows are documented in `docs/operations/ERP_WORKFLOWS.md`.

---

## 3. Why the frozen schema remains

Physical retention currently preserves:

- deterministic snapshot/digest evidence;
- source-to-ERPNext migration traceability;
- master mapping reconciliation;
- submitted/cancelled historical records;
- proof that legacy rows did not mutate after cutover;
- controlled rollback evidence if ever required.

This is a retention decision, **not** permission to use the old records operationally.

---

## 4. Compatibility APIs are not authority

Some old RPC or endpoint names remain because callers may still depend on those names. Current compatibility routes must resolve into ERPNext-native services.

A legacy-sounding method name therefore does **not** justify:

- inserting `Ledgix Sale`;
- inserting `Ledgix Payment`;
- updating `Ledgix Stock Movement`;
- creating `Ledgix POS Shift` or `Ledgix POS Hold`;
- restoring Ledgix Item/Customer/Supplier as active masters;
- maintaining a second outstanding, stock, tax or payment balance.

Endpoint compatibility may remain. Duplicate business authority may not.

---

## 5. Navigation and UI rule

Active navigation must resolve to:

- ERPNext native forms/lists/reports for masters, buying, sales, accounting and stock;
- retained Ledgix POS, Inventory Intelligence, Tax & FBR Center and Setup Wizard for product-specific UX.

Frozen business DocTypes must not be presented as current operator workflows.

Role/profile visibility is only a navigation concern. ERPNext/Frappe permissions remain security authority.

---

## 6. Operating-data rule

The current local acceptance dataset is `LEDGIX-RETAIL-OPERATING-V1` and is already a completed verified operating dataset.

Do **not** casually run the seed/cleanup path just to refresh local data. First use the read-only verifier documented in `docs/operations/LOCAL_DEMO_DATA.md`.

The seeder may be used only when intentionally rebuilding local acceptance data. It creates **ERPNext-native** masters and transactions and must never repopulate the frozen legacy business ledgers.

Supported implementation entrypoint:

```bash
bench --site ledgix-erpnext.local execute ledgix_saas.setup.demo_data.seed
```

Treat that command as a deliberate rebuild operation, not a normal startup step.

---

## 7. Physical schema deletion rule — DEFERRED

A frozen legacy DocType/table may be physically removed only when all of the following are proven:

1. no import, hook, compatibility route, report, print format, workspace, test, patch or migration still requires it;
2. no retirement digest/snapshot/reconciliation logic requires it;
3. no retained historical row is required for audit or recovery;
4. no legacy-to-ERPNext mapping depends on it;
5. a current backup/restore proof exists before deletion;
6. an explicit migration and rollback plan exists;
7. the removal is separately approved as a schema-retirement change.

The current project does **not** establish those conditions for the frozen business DocTypes.

**Current state: DEFERRED. Keep the schema frozen and read-only.**

---

## 8. Behaviors that must not return

The following are retired and must not be reintroduced:

- dual-writing a sale/payment/stock operation into ERPNext and a Ledgix legacy transaction DocType;
- deriving current receivables from `Ledgix Sale` or `Ledgix Payment`;
- deriving current stock from `Ledgix Stock Movement`, `Ledgix Stock Lot` or `Ledgix Stock Serial`;
- using `Ledgix Customer`, `Ledgix Supplier` or `Ledgix Item` as the master record for new business;
- implementing new POS shifts/holds using the frozen Ledgix shift/hold DocTypes;
- submitting FBR from historical `Ledgix Sale` instead of the current ERPNext-native source documents;
- unfreezing legacy ledgers as a convenience workaround.

Corrections to current business activity belong in the authoritative ERPNext document/workflow.

---

## 9. Source of truth

Implementation behavior:

```text
apps/ledgix_saas/api/legacy_retirement.py
apps/ledgix_saas/setup/erpnext_phase12_legacy_retirement.py
apps/ledgix_saas/hooks.py
apps/ledgix_saas/services/erpnext_pos.py
apps/ledgix_saas/services/erpnext_selling.py
apps/ledgix_saas/services/erpnext_buying_inventory.py
```

Current architecture:

```text
docs/architecture/CURRENT_ARCHITECTURE.md
docs/operations/ERP_WORKFLOWS.md
docs/operations/LOCAL_DEMO_DATA.md
```

Historical migration rationale and phase evidence remain under `docs/archive/migration/` and are not current operating instructions.
