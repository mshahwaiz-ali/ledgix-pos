# Ledgix ERPNext Core Migration — Implementation Progress

**Started:** 2026-09-16  
**Active implementation branch:** `erpnext-core-migration`  
**Pre-functional-change main baseline:** `148b35e63371cb0bd5bd5408df69f5262e64680e`  
**Rollback tag:** `pre-erpnext-core-2026-09-16`

This file records exercised evidence against `erpnext_core_migration_plan.md`. A phase is not marked complete merely because code exists; runtime gates must pass on the dedicated integration site where applicable.

---

## Phase 0 — Baseline / Safety

### Completed

- Repository architecture audit completed.
- ERPNext-core master plan locked.
- Rollback baseline recorded at `148b35e63371cb0bd5bd5408df69f5262e64680e`.
- Rollback tag `pre-erpnext-core-2026-09-16` created and pushed.
- Superseded plan removed.
- Repository CI, package validation, ERPNext dependency validation and secret scan established.
- Runtime bench/sites/databases/secrets/environments are excluded from Git.
- Tested Frappe/ERPNext baseline is tracked in `config/framework.lock` rather than vendoring framework source.

### Pending before production cutover

- Back up any meaningful staging/production Ledgix database/site.
- Record installed apps/framework versions on each staging/production site immediately before cutover work.

---

## Phase 1 — ERPNext Dependency and Fresh Integration Site — COMPLETE

### Dependency plumbing

- `required_apps = ["erpnext"]` is declared in Ledgix hooks.
- `pyproject.toml` declares Frappe v15 + ERPNext v15 support.
- Local and production install/deploy scripts prepare ERPNext before Ledgix site migration.
- ERPNext dependency validation is part of local CI.
- `site_setup.sh` is compatible with recursive required-app installation and its local secret-index parsing was repaired.

### Proven framework baseline

- Frappe `15.113.4`, commit `588e443808206a7bfe87429c5a55e16016ec7840`.
- ERPNext `15.121.3`, commit `26f06878346fb6861229ccb1fe3a53dc1bf5bad3`.
- Ledgix `0.0.1` from `erpnext-core-migration`.

### Fresh-site evidence

Integration site: `ledgix-erpnext.local`

Verified on the real bench:

- all three apps installed;
- migrate completed;
- Ledgix assets built;
- `site_config.json` exists;
- `frappe.get_installed_apps()` returned `frappe`, `erpnext`, `ledgix_saas`;
- runtime files/secrets remained outside Git.

**Phase 1 decision: PASS.**

---

## Phase 2 — Native ERPNext Capability / Gap Matrix — FINAL GATE READY

### Objective

Prove what Ledgix can replace with ERPNext native authority before building adapters or retiring any existing Ledgix business model.

### Schema capability evidence

The integration-site schema probe confirmed the required native models exist for:

- Item, Item Group, UOM, Customer, Supplier, Address, Contact;
- Price List, Item Price, Pricing Rule;
- Sales Invoice, POS Invoice;
- Mode of Payment, Payment Entry;
- Purchase Order, Purchase Receipt, Purchase Invoice;
- Warehouse, Stock Entry, Stock Ledger Entry;
- Batch, Serial No, Serial and Batch Bundle;
- POS Profile, POS Opening Entry, POS Closing Entry.

The submittable probe was corrected to use Frappe v15 `meta.is_submittable`. Transaction DocTypes then reported their expected submit capability.

Pinned-source verification confirmed ERPNext `15.121.3` POS Invoice intentionally has no `update_stock` field. POS stock/accounting is therefore evaluated through the native closing/consolidation lifecycle rather than by introducing a compatibility field.

### Integration business bootstrap — PASS

The fresh site initially had no business setup. A guarded helper, restricted to `ledgix-erpnext.local`, reused ERPNext's setup-wizard path to create the isolated test business.

Test business:

- Company: `Ledgix ERPNext Integration` (`LEI`)
- Country: Pakistan
- Currency: PKR
- Fiscal year: 2026-07-01 through 2027-06-30
- Chart of Accounts: Standard

Post-bootstrap evidence included 82 accounts, 5 warehouses, 2 price lists, 5 modes of payment, required groups/UOMs and no behavioral preflight blockers.

### Core behavioral batch — PASS

Real integration-site execution at branch commit `85ab4b8e00b3` passed all core business-engine paths.

#### Invoice-only / FBR-style profile — PASS

Proven natively:

- non-stock Item;
- submitted Sales Invoice;
- GL posting;
- zero Stock Ledger Entry for the invoice-only path;
- Payment Entry and full settlement;
- linked native return/Credit Note;
- zero stock effect on the non-stock return;
- no parallel `Ledgix Sale` creation.

**Decision:** invoice + FBR-only clients can use ERPNext non-stock Items and Sales Invoice/Payment Entry without fake or negative inventory.

#### Purchase / inventory / stock sale / return — PASS

Proven natively:

- Purchase Order -> Purchase Receipt -> Purchase Invoice;
- supplier Payment Entry and AP settlement;
- Purchase Receipt stock ledger increase;
- stock Sales Invoice stock decrease;
- native linked return restoring stock;
- GL posting on purchase, payment, sale and return;
- no parallel Ledgix Sale/Purchase/Payment/Stock Movement creation.

#### POS / split payment / opening-closing — PASS

Proven natively:

- POS Profile;
- POS Opening Entry;
- submitted POS Invoice;
- split tender using Cash + Credit Card;
- fully paid POS transaction;
- POS Closing Entry;
- consolidation into submitted Sales Invoice;
- direct POS Invoice did not double-post stock;
- consolidated Sales Invoice posted stock and GL;
- no parallel Ledgix Sale/Payment/POS Shift/Stock Movement creation.

**Current POS decision:** keep the Ledgix POS UX over the ERPNext native engine unless later UI evaluation justifies using ERPNext's native screen directly. Do not retain a parallel financial/stock engine.

### Phase 2 extended final gate — READY TO RUN

The remaining plan items are now packaged into one guarded final gate instead of separate user-side test cycles.

Runner:

- `scripts/run_erpnext_phase2_final_gate.sh`

Consolidated Python gate:

- `ledgix_saas.migration.erpnext_phase2_final_gate.run`

The final gate reruns the proven core engine and additionally tests:

1. **Pricing / receivables / workflow / print**
   - ERPNext Pricing Rule resolution;
   - partial Payment Entry and remaining invoice outstanding;
   - unallocated customer advance Payment Entry;
   - partial linked Credit Note/return;
   - native Sales Invoice print rendering.

2. **Stock operations / tracking**
   - Stock Entry Material Receipt;
   - Stock Reconciliation to a target quantity;
   - Batch with inbound/outbound Serial and Batch Bundles;
   - Serial No creation and inbound/outbound Serial and Batch Bundles;
   - Stock Ledger quantity assertions.

3. **Saved/unfinished POS**
   - persist a draft POS Invoice in an open shift;
   - verify no GL or Stock Ledger posting while draft;
   - verify stock quantity is unchanged;
   - clean up the test draft/opening session after evidence capture.

4. **Tax architecture decision**
   - read-only verification of ERPNext tax rows, item tax templates, inclusive-tax capability and separate withholding model;
   - no monetary tax cutover;
   - preserve Phase 4 parity requirements for Third Schedule/notified retail price, Further Tax, Extra Tax, FED and Sales Tax Withheld at Source.

The tax probe was explicitly aligned with the pinned ERPNext v15 schema; it does not assume removed/nonexistent `Sales Taxes and Charges` fields.

### Expected evidence-backed target decisions if final gate passes

| Capability | Target decision |
| --- | --- |
| Standard masters | USE NATIVE |
| Price List / Item Price / Pricing Rule | USE NATIVE |
| Invoice-only sales | USE NATIVE |
| Payment / AR / AP | USE NATIVE |
| Returns / Credit Notes | USE NATIVE |
| Purchase / inventory | USE NATIVE |
| Stock Entry / Reconciliation | USE NATIVE |
| Serial / Batch | USE NATIVE |
| POS financial/stock engine | ERPNext native |
| Ledgix POS screen | KEEP LEDGIX UI OVER NATIVE ENGINE for now |
| Saved/held POS backend | ERPNext draft POS Invoice if final draft spike passes |
| Financial tax engine | EXTEND/USE NATIVE only after Phase 4 parity |
| FBR compliance metadata/submission | KEEP LEDGIX layer, sourced from ERPNext transactions |

### Phase 2 completion rule

Phase 2 remains **not yet marked COMPLETE** until `run_erpnext_phase2_final_gate.sh` passes on `ledgix-erpnext.local`.

No production authority cutover has occurred.

---

## Phase 3 — Standard Masters and Ledgix Extension Schema — NEXT AFTER PHASE 2 GREEN

Once the Phase 2 final gate passes, the next implementation batch will establish the target extension schema before transaction cutover:

- ERPNext Customer FBR fields;
- Ledgix Item Tax Profile relinked to ERPNext Item;
- required Sales Invoice/POS/return FBR fields;
- immutable line-level FBR/tax snapshots;
- Ledgix role mapping to Frappe/ERPNext permissions;
- business/client profile configuration without duplicate masters;
- migration-safe fixtures/patches;
- automated schema tests.

No old Ledgix master will be retired merely by creating this schema.

---

## Phase 4 — Tax Parity and Accounting Foundation — PLANNED

ERPNext will become monetary/tax authority only after an explicit parity matrix passes for:

- ordinary taxable sales;
- tax-inclusive pricing;
- zero-rated and exempt sales;
- Third Schedule/notified retail price;
- Further Tax;
- Extra Tax;
- FED;
- Sales Tax Withheld at Source;
- mixed invoices;
- full and partial returns;
- price-only credit notes where required.

The parity gate must compare ERPNext totals/GL with Ledgix/FBR-required values and adapt FBR preview to the ERPNext transaction source before any old tax engine is retired.

---

## Safety Status

- No production sales, purchase, stock, payment, tax, FBR, POS, receivable or master-data authority has been cut over.
- Existing Ledgix business DocTypes/services remain available while replacement paths are proven.
- Migration behavioral helpers are hard-guarded to `ledgix-erpnext.local`.
- FBR has not been switched to ERPNext transaction sourcing yet.
