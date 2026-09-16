# Phase 4 — ERPNext Tax Parity and Accounting Foundation

**Branch:** `erpnext-core-migration`  
**Integration site:** `ledgix-erpnext.local`  
**Framework baseline:** Frappe 15.113.4 / ERPNext 15.121.3

## Authority contract

Phase 4 establishes one monetary authority:

```text
Ledgix FBR classification / legal basis
                  |
                  v
Ledgix Phase 4 tax adapter
  - resolves per-line legal tax inputs
  - freezes FBR/legal snapshots
  - never sets grand_total
                  |
                  v
ERPNext Sales Taxes and Charges
                  |
                  v
ERPNext net/tax/grand totals + GL
```

Ledgix remains authoritative only for FBR/legal metadata that generic ERPNext accounting does not express completely: HS code, FBR UOM, Sales Type, rate description, scenario/SRO references, Third Schedule/notified retail price, component classification and immutable FBR snapshots.

## Component mapping

| Ledgix concept | Phase 4 monetary mapping | FBR snapshot |
| --- | --- | --- |
| Ordinary Sales Tax | ERPNext tax row + tax account | Yes |
| Inclusive ordinary Sales Tax | ERPNext `On Net Total` row with `included_in_print_rate=1` | Yes |
| Third Schedule Sales Tax | Ledgix notified-price basis -> ERPNext `Actual` tax row | Yes |
| Extra Tax | ERPNext `Actual` tax row + dedicated account | Yes |
| Further Tax | ERPNext `Actual` tax row + dedicated account | Yes |
| FED Payable | ERPNext `Actual` tax row + dedicated account | Yes |
| Sales Tax Withheld at Source | **Not added to invoice payable in Phase 4** | Yes |

The withheld-at-source component is intentionally not mapped to ERPNext supplier TDS/Tax Withholding Category. Existing Ledgix behavior reports this value separately and does not add it to customer payable. A reserved Company account link is created for a later legally verified accounting treatment, but the Phase 4 invoice gate asserts that no withholding GL is posted.

## Company accounting extensions

Phase 4 adds Ledgix Custom Fields to ERPNext `Company` for explicit account mapping:

- Sales Tax Payable Account;
- Extra Tax Payable Account;
- Further Tax Payable Account;
- FED Payable Account;
- reserved Sales Tax Withheld Account.

These fields do not create another Company/master model. Production account selection remains company-specific.

## Mandatory runtime matrix

The integration gate creates isolated, non-stock ERPNext test items and exercises exactly 13 cases:

1. ordinary taxable item;
2. tax-inclusive price;
3. zero-rated item;
4. exempt item;
5. Third Schedule / Notified Retail Price;
6. Further Tax;
7. Extra Tax;
8. FED;
9. Sales Tax Withheld at Source;
10. mixed-tax invoice;
11. full return;
12. partial return;
13. price-only / financial-only credit note.

Every case proves the relevant subset of:

- submitted ERPNext Sales Invoice/Credit Note;
- ERPNext net total;
- ERPNext `total_taxes_and_charges`;
- ERPNext grand total;
- dedicated tax-account GL amount;
- balanced GL;
- no stock effect for the dedicated Phase 4 non-stock fixtures;
- immutable Ledgix line snapshot;
- FBR tax-preview fields derived from the ERPNext transaction.

## Return and credit-note rule

Returns are created with ERPNext's native return mapper. The Ledgix adapter is re-applied to the draft return so fixed `Actual` component rows scale to the returned quantity instead of blindly copying the original invoice amount.

ERPNext requires at least one negative-quantity item on a linked Sales Invoice return, so a zero-quantity linked Credit Note is not used by this gate. The price-adjustment case instead uses a dedicated **non-stock** item, `qty=-1`, a reduced adjustment rate and `update_stock=0`. It therefore proves a pure financial/tax credit with no Stock Ledger Entry while remaining valid under ERPNext's native return validation.

## Inclusive-price rule

ERPNext rejects an inclusive `Actual` tax row. Therefore the adapter uses native `On Net Total` percentage tax for the proven homogeneous inclusive case. Mixed-rate or Third-Schedule inclusive invoices are explicitly fail-closed until an Item Tax Template design is proven; Phase 4 does not silently guess.

## FBR safety

Phase 4 performs **preview only**:

- no FBR HTTP request;
- no sandbox/production submission;
- no FBR Submission Log cutover;
- no duplicate submission path;
- no real FBR datasource switch.

The real FBR datasource cutover remains a later phase after master and transaction migration.

## Completion gate

Run:

```bash
bash scripts/run_erpnext_phase4_final_gate.sh
```

The runner performs local CI, Redis readiness, migrate, complete Phase 2 regression, complete Phase 3 regression and then the 13-case Phase 4 matrix.

Phase 4 is complete only when all foundation checks and all 13 runtime cases pass on `ledgix-erpnext.local`.
