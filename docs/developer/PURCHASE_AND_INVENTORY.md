# Ledgix POS — Purchasing and Inventory

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Primary implementation:** services/erpnext_buying_inventory.py

## 1. Purpose

This document describes the current purchasing, supplier payment, inventory movement, stock correction and batch/serial architecture.

Current authority is ERPNext:

- Supplier;
- Item;
- Warehouse;
- Purchase Order;
- Purchase Receipt;
- Purchase Invoice;
- Payment Entry;
- Stock Entry;
- Stock Reconciliation;
- Stock Ledger Entry;
- Bin;
- Batch;
- Serial No;
- Serial and Batch Bundle.

Historical Ledgix Purchase, Stock Movement, Stock Lot and Stock Serial are not current operational authority.

---

## 2. Core service boundary

Primary service:

    services/erpnext_buying_inventory.py

This module is the Ledgix compatibility/service boundary for current buying and stock operations.

It deliberately writes standard ERPNext purchase/payment/stock documents.

---

## 3. Identity resolution

The service resolves:

- Company;
- Supplier;
- Item;
- Mode of Payment;
- Warehouse.

Migration compatibility may resolve an old Ledgix ID into a native ERPNext master.

Native ERPNext records remain authority.

---

## 4. Company and warehouse rules

A warehouse used by the service must be:

- real ERPNext Warehouse;
- non-group;
- enabled;
- associated with the requested Company.

If no warehouse is explicitly supplied, the service may consider the global Stock Settings default only if it belongs to the current Company.

Otherwise it selects a valid Company leaf warehouse.

It fails if no valid warehouse exists.

This avoids cross-company stock contamination.

---

## 5. Purchase item normalization

For each requested purchase row, the service resolves:

- ERPNext Item;
- positive quantity;
- UOM;
- stock/non-stock status;
- target warehouse for stock items.

A non-stock item does not need a stock warehouse effect in the same way as a stock item.

The native purchase document remains responsible for the resulting accounting/stock lifecycle.

---

## 6. Purchase idempotency

Current write methods accept client identifiers on several document types.

Examples:

- client purchase ID;
- client receipt ID;
- client purchase invoice ID;
- client payment ID;
- client stock ID;
- client reconciliation ID.

Before creating another native document, the service checks for an existing non-cancelled ERPNext document using the identifier.

Retry metadata prevents duplicate business documents.

It is not a separate transaction model.

---

## 7. Full purchasing flow

Preferred multi-stage flow:

    Supplier
      -> Purchase Order
      -> Purchase Receipt
      -> Purchase Invoice
      -> Payment Entry

Use this flow when ordering, physical receipt and supplier invoicing must remain operationally distinct.

---

## 8. Purchase Order

create_purchase_order:

1. resolves Company;
2. locks Company;
3. checks idempotency;
4. resolves Supplier;
5. resolves Warehouse;
6. normalizes item rows;
7. sets schedule dates;
8. creates ERPNext Purchase Order;
9. inserts;
10. optionally submits.

The Purchase Order is native ERPNext order authority.

Historical Ledgix Purchase is not written.

---

## 9. Purchase Receipt

create_purchase_receipt requires a submitted ERPNext Purchase Order.

It uses ERPNext's Purchase Order -> Purchase Receipt mapper.

The service:

- validates source submission;
- locks Company;
- applies idempotency;
- resolves target Warehouse;
- sets warehouse on stock item rows;
- inserts;
- submits.

The submitted Purchase Receipt creates native ERPNext stock effects.

---

## 10. Purchase Invoice from receipt

create_purchase_invoice_from_receipt requires a submitted Purchase Receipt.

It uses ERPNext's native Purchase Receipt -> Purchase Invoice mapper.

The resulting Purchase Invoice is the AP authority.

The service carries Ledgix client/source metadata for traceability but does not create another payable ledger.

---

## 11. Direct Purchase Invoice

For simpler clients/workflows, create_direct_purchase_invoice can create a Purchase Invoice directly.

Inputs include:

- Supplier;
- item rows;
- Company;
- Warehouse;
- update_stock;
- client identifiers.

### update_stock = true

The Purchase Invoice itself creates the stock effect.

### update_stock = false

The Purchase Invoice creates AP/accounting without the same direct stock update.

Choose intentionally.

Do not accidentally post both a direct stock-updating Purchase Invoice and a separate receipt for the same physical event.

---

## 12. Supplier payable authority

Accounts Payable is native ERPNext state.

Use:

- submitted Purchase Invoice;
- Payment Entry;
- GL/AP reports.

Do not derive current supplier payable from historical Ledgix Purchase records.

---

## 13. Supplier payment

post_supplier_payment requires:

- submitted non-return Purchase Invoice;
- valid Mode of Payment;
- valid default account for Company;
- positive target amount;
- target not exceeding current invoice outstanding.

It uses ERPNext's Payment Entry mapper.

### Account behavior

The service resolves the Mode of Payment account for the invoice Company.

Payment Entry remains the financial record.

### Partial payment

A target smaller than outstanding is supported by adjusting:

- paid/received amount;
- allocated amount on the Purchase Invoice reference.

### Idempotency

client_payment_id can return the existing active native Payment Entry on retry.

---

## 14. Purchase return

create_purchase_return requires a submitted non-return Purchase Invoice.

It uses:

    make_return_doc("Purchase Invoice", original)

The resulting return Purchase Invoice is submitted.

This native return represents both financial and, where applicable, stock reversal according to ERPNext rules.

Do not create a current Ledgix Purchase Return ledger.

---

## 15. Stock authority

Current stock truth is:

    ERPNext Stock Ledger Entry + Bin

For an Item/Warehouse, Bin provides current stock-oriented values such as:

- actual quantity;
- reserved quantity;
- projected quantity;
- valuation rate;
- stock value.

Stock Ledger Entry provides voucher-level stock history.

Ledgix reads/presents these values.

It does not own an independent stock balance.

---

## 16. Stock snapshot

stock_snapshot resolves:

- native Item;
- valid Warehouse;
- ERPNext Bin values.

The returned object explicitly identifies ERPNext Bin + Stock Ledger Entry as authority.

This is a read model only.

---

## 17. Serial availability

available_serials works only for ERPNext serial-tracked Items.

It queries native Serial No records.

Optional Warehouse filtering can restrict results.

Returned serial information can include purchase/source details where available in the pinned ERPNext schema.

Historical Ledgix Stock Serial is not used as current availability authority.

---

## 18. Stock Entry

create_stock_entry creates a native ERPNext Stock Entry through ERPNext stock utilities.

Supported purposes are intentionally limited to:

- Material Receipt;
- Material Issue;
- Material Transfer.

A requested unsupported purpose fails.

---

## 19. Stock Entry validation

The service requires:

- stock Item;
- positive quantity;
- valid purpose;
- valid Company;
- valid source Warehouse for issue/transfer;
- valid target Warehouse for receipt/transfer.

Optional inputs include:

- valuation rate;
- batch number;
- serial numbers;
- remarks;
- client stock ID.

---

## 20. Batch / serial fields on Stock Entry

Where batch or serial information is supplied, the native stock-entry helper is invoked with serial/batch fields enabled.

The service passes:

- batch_no;
- serialized serial_no text;
- from/to warehouse;
- quantity;
- optional rate.

ERPNext remains responsible for validating stock identity rules.

---

## 21. Stock Entry idempotency

client_stock_id can return the existing active Stock Entry.

This prevents a retry from intentionally moving stock twice.

For inventory operations, idempotency is especially important because a duplicate Stock Entry changes real quantity.

---

## 22. Stock Reconciliation

create_stock_reconciliation creates a native ERPNext Stock Reconciliation.

It is intended for a verified physical-count/valuation correction.

Inputs include:

- Item;
- target quantity;
- valuation rate;
- Warehouse;
- Company;
- client reconciliation ID.

The Item must be a stock Item.

The warehouse must be a valid current Company leaf Warehouse.

---

## 23. Reconciliation semantics

Stock Reconciliation sets ERPNext stock toward a verified target state.

Use it when the business fact is:

> "The physical count/value is this."

Do not use it to hide a missing:

- sale;
- purchase;
- receipt;
- transfer;
- return.

If the underlying business event exists, record that native event.

---

## 24. Batch management

ensure_batch:

- resolves native Item;
- requires batch number;
- returns existing Batch if it belongs to same Item;
- rejects reuse of a Batch ID belonging to another Item;
- otherwise creates native ERPNext Batch.

Batch is ERPNext identity.

Do not mirror batch authority into Ledgix Stock Lot.

---

## 25. Serial management

Serial identity remains ERPNext Serial No.

Availability and warehouse location must come from native ERPNext state.

Do not maintain current serial availability in Ledgix Stock Serial.

---

## 26. Voucher-level stock verification

stock_ledger_qty can sum native Stock Ledger Entry actual_qty for:

- voucher type;
- voucher number;
- item.

It excludes cancelled ledger rows.

This is useful for acceptance/gate verification.

It is not a stored alternative stock counter.

---

## 27. Native voucher cancellation

The service exposes controlled cancellation for supported native vouchers:

- Purchase Order;
- Purchase Receipt;
- Purchase Invoice;
- Payment Entry;
- Stock Entry;
- Stock Reconciliation.

Only submitted vouchers can be cancelled.

Cancellation then follows ERPNext lifecycle.

Do not delete the native record or edit Stock Ledger/GL rows directly.

---

## 28. Buying + stock interaction

### Full chain

    Purchase Order
      -> Purchase Receipt
          -> stock increases
      -> Purchase Invoice
          -> AP increases
      -> Payment Entry
          -> AP decreases

### Direct stock-updating invoice

    Purchase Invoice(update_stock = 1)
      -> stock increases
      -> AP increases
      -> Payment Entry
          -> AP decreases

The two paths should not be accidentally combined for the same receipt.

---

## 29. Returns + stock interaction

A Purchase Invoice return created through the native return mapper can reverse financial/stock consequences according to the original invoice's native setup.

Always verify the actual native ledger effect rather than assuming based on Ledgix UI labels.

---

## 30. Inventory Intelligence

Ledgix Inventory Intelligence is a reporting/read layer over ERPNext.

Current reporting service reads:

- Item;
- Bin;
- Warehouse;
- Item Reorder;
- Item Price;
- Stock Ledger Entry;
- native purchase/sales documents.

It must not read frozen Ledgix stock ledgers as current truth.

---

## 31. Current stock report

services/erpnext_reporting.py derives current stock rows from native ERPNext data.

Typical values include:

- current stock;
- minimum/reorder stock;
- valuation;
- stock value;
- stock status;
- batch/serial flags.

Authority is explicitly ERPNext Item + Bin + related native masters.

---

## 32. Stock movement report

Current stock movement reporting reads ERPNext Stock Ledger Entry.

It can expose:

- voucher type;
- voucher number;
- warehouse;
- actual quantity;
- stock value difference;
- batch/serial information.

Historical Ledgix Stock Movement is not current reporting authority.

---

## 33. Low stock

Low-stock interpretation is derived from:

- current Bin quantity;
- Item Reorder levels.

Ledgix can present the risk/status.

ERPNext quantities remain authoritative.

---

## 34. Cross-company safety

A stock/purchase transaction must not silently use a Warehouse or account from another Company.

The service validates Company-specific warehouse and payment context.

Future inventory features must preserve this boundary.

---

## 35. Negative stock

ERPNext site/accounting settings determine whether negative stock is permitted.

Ledgix must not fake availability or write an independent stock balance to bypass native rules.

If ERPNext rejects stock chronology:

- inspect native documents;
- inspect Warehouses;
- inspect posting sequence;
- inspect stock settings;
- correct the underlying business data.

---

## 36. Valuation

Stock valuation and COGS are ERPNext concerns.

Ledgix may display valuation results through reporting.

Do not maintain an independent Ledgix cost/valuation ledger.

The final forensic hardening specifically removed unsafe stale/fallback cost behavior from current reporting paths.

---

## 37. Price vs valuation

Selling price and stock valuation are different concepts.

- selling price -> ERPNext selling/pricing authority;
- purchase price -> native purchase document context;
- valuation -> ERPNext stock/accounting state.

Do not use one as an undocumented fallback for another.

---

## 38. FBR boundary

Purchasing/inventory is not the FBR commercial submission source.

FBR attaches to submitted sales-side ERPNext invoices.

Inventory effects created by sales/returns must still reconcile natively.

Do not let an FBR workaround directly mutate stock.

---

## 39. Legacy boundaries

Do not create current operational records in:

- Ledgix Purchase;
- Ledgix Purchase Item;
- Ledgix Stock Movement;
- Ledgix Stock Lot;
- Ledgix Stock Lot Allocation;
- Ledgix Stock Serial.

These may remain for historical evidence/migration traceability.

Current quantity/payment/AP truth belongs to ERPNext.

---

## 40. Verification — Purchase Order

Check:

- submitted/draft state as intended;
- correct Supplier;
- correct Company;
- correct Items/qty;
- correct target Warehouse;
- client purchase ID.

---

## 41. Verification — Purchase Receipt

Check:

- source Purchase Order;
- submitted receipt;
- correct received quantities;
- stock item Warehouses;
- Stock Ledger Entry effect;
- idempotency metadata.

---

## 42. Verification — Purchase Invoice

Check:

- source Purchase Receipt where applicable;
- Supplier/Company;
- update_stock behavior;
- AP outstanding;
- GL effect;
- stock effect only once.

---

## 43. Verification — Supplier Payment

Check:

- submitted Payment Entry;
- correct Purchase Invoice reference;
- amount <= prior outstanding;
- Mode of Payment;
- Company account;
- invoice outstanding reduced.

---

## 44. Verification — Stock Entry

Check:

- submitted Stock Entry;
- purpose;
- source/target Warehouse;
- quantity;
- batch/serial where required;
- Stock Ledger Entry;
- client stock ID.

---

## 45. Verification — Stock Reconciliation

Check:

- submitted reconciliation;
- Item/Warehouse;
- target quantity/value;
- resulting Bin;
- Stock Ledger Entry;
- business justification for correction.

---

## 46. Primary source map

| Concern | Current source |
|---|---|
| Buying/stock service | services/erpnext_buying_inventory.py |
| Current reporting | services/erpnext_reporting.py |
| Inventory Intelligence API | api/inventory_intelligence_native.py |
| Workspace/product visibility | api/product_shell.py |
| ERPNext extension schema | setup/erpnext_phase7_extensions.py and related current setup |
| Native authority rule | docs/developer/ARCHITECTURE.md |

---

## 47. Development rule

When extending purchasing/inventory:

- use ERPNext Supplier/Item/Warehouse;
- create native purchase/stock vouchers;
- preserve Company isolation;
- preserve idempotency on external/retry-prone writes;
- verify real Stock Ledger/Bin effects;
- use native batch/serial identity;
- do not recreate Ledgix Purchase or stock ledgers;
- do not modify ERPNext stock/accounting to satisfy a legacy expectation.

---

## 48. Summary

The current purchasing/inventory architecture is:

> **Ledgix provides controlled service and reporting layers over ERPNext-native purchasing and stock documents, while ERPNext Purchase/Payment/Stock Ledger/Bin/Batch/Serial state remains the sole operational and accounting authority.**
