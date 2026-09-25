# Ledgix POS — Purchasing and Inventory

**Audience:** Purchasing staff, stock managers, client managers  
**Applies to:** Small Retail, Full Retail and Mixed profiles

## 1. Purpose

This guide explains current purchasing and stock operations.

Official records are ERPNext:

- Supplier;
- Purchase Order;
- Purchase Receipt;
- Purchase Invoice;
- Payment Entry;
- Stock Entry;
- Stock Reconciliation;
- Stock Ledger;
- Bin;
- Batch;
- Serial No.

Do not use old historical Ledgix purchase/stock records for current work.

---

## 2. Choose the right purchase workflow

There are two common workflows.

### Standard controlled purchasing

    Purchase Order
      -> Purchase Receipt
      -> Purchase Invoice
      -> Supplier Payment

Use when ordering, physical receipt and supplier invoice are separate stages.

### Direct Purchase Invoice

Use for simpler businesses where the supplier bill is entered directly.

If the direct Purchase Invoice uses stock update, do not also create a duplicate Purchase Receipt for the same goods.

---

## 3. Supplier

Create/maintain Supplier in ERPNext.

Before purchasing verify:

- Supplier is correct;
- Company is correct;
- contact/address is correct;
- accounting setup is complete.

---

## 4. Purchase Order

Create Purchase Order when the business formally orders stock.

Enter:

- Supplier;
- Items;
- quantities;
- expected date;
- target Warehouse;
- rates/terms.

Review before submit.

The Purchase Order does not by itself mean stock has been physically received.

---

## 5. Receive goods

When goods arrive, create Purchase Receipt from the submitted Purchase Order.

Before submit verify:

- actual received Items;
- actual quantity;
- Warehouse;
- batch/serial details where applicable;
- damaged/short goods handled correctly.

Submitting the receipt creates the native stock effect.

---

## 6. Supplier invoice

Create Purchase Invoice from the Purchase Receipt when following the standard chain.

Verify:

- Supplier;
- received Items;
- quantities;
- rates;
- tax;
- source receipt;
- amount payable.

The Purchase Invoice becomes the Accounts Payable record.

---

## 7. Direct Purchase Invoice

For a simpler business process, use direct Purchase Invoice.

Understand whether:

    Update Stock

is enabled.

If enabled, the invoice itself affects stock.

Do not also receive the same goods through another stock transaction.

---

## 8. Supplier payment

When paying the supplier:

1. open/reference the submitted Purchase Invoice;
2. choose Mode of Payment;
3. enter amount;
4. verify Company payment account;
5. submit Payment Entry.

The payment amount cannot exceed the current invoice outstanding.

---

## 9. Partial supplier payment

Partial payment is allowed where the workflow supports it.

Example:

    Supplier invoice outstanding: 50,000
    Payment: 20,000
    Remaining: 30,000

Review the outstanding after posting.

---

## 10. Purchase return

For a supplier return:

- start from the original submitted Purchase Invoice;
- create the native return;
- verify Items/quantities;
- submit.

The return Purchase Invoice is the official financial/stock return evidence.

Do not create a custom Ledgix purchase return record.

---

## 11. Warehouse

Every stock transaction must use the correct ERPNext Warehouse.

A normal operational Warehouse should be:

- active;
- leaf/non-group;
- owned by the correct Company.

Do not post one Company's stock into another Company's Warehouse.

---

## 12. Current stock quantity

Use ERPNext stock reports / Inventory Intelligence.

Current quantity is based on:

- Stock Ledger Entry;
- Bin.

Do not use old Ledgix Stock Movement/Lot tables as current quantity.

---

## 13. Inventory Intelligence

Ledgix Inventory Intelligence provides a focused view of ERPNext stock.

Depending on configuration, it can help review:

- current stock;
- low stock;
- valuation;
- Item/Warehouse position;
- movements.

It is a reporting view, not a separate stock ledger.

---

## 14. Stock Entry

Use Stock Entry for operational movements such as:

- Material Receipt;
- Material Issue;
- Material Transfer.

Use the correct purpose.

---

## 15. Material Receipt

Use when stock enters inventory without the normal purchase-receipt flow and the business reason genuinely calls for a Stock Entry.

Do not use Material Receipt as a shortcut for every purchase.

---

## 16. Material Issue

Use when stock leaves inventory for a valid non-sale reason.

Record a clear reason/remarks.

Do not use it to hide an unrecorded sale.

---

## 17. Material Transfer

Use when moving stock between Warehouses.

Verify:

- source Warehouse;
- target Warehouse;
- Item;
- quantity.

Both locations should belong to the same intended Company context.

---

## 18. Stock Reconciliation

Use Stock Reconciliation when the physical count is known and the system quantity/value must be corrected.

Example:

    System quantity: 100
    Physical count: 96

After investigating the reason, Stock Reconciliation can set the verified target quantity.

---

## 19. Do not use reconciliation to hide mistakes

If the reason for the mismatch is actually:

- missing sale;
- missing purchase;
- unposted return;
- missing transfer,

fix the real transaction.

Use Stock Reconciliation for genuine physical count/valuation correction.

---

## 20. Physical stock count

Recommended process:

1. stop/control stock movement for the count;
2. count actual stock;
3. investigate major differences;
4. correct missing business transactions;
5. use Stock Reconciliation only for remaining genuine differences;
6. review resulting Stock Ledger/Bin.

---

## 21. Batch-controlled stock

For a batch-controlled Item:

- use ERPNext Batch;
- select correct batch during receipt/issue/sale;
- maintain expiry/identity information where required.

Do not maintain the same current batch in a historical Ledgix Stock Lot.

---

## 22. Serial-controlled stock

For serial-controlled Item:

- each unit uses ERPNext Serial No;
- correct serial must be selected during movements;
- quantity and serial count must agree.

Do not type arbitrary serials simply to bypass a stock error.

---

## 23. Negative stock

Whether negative stock is permitted is an ERPNext policy decision.

If ERPNext blocks the transaction:

- check current quantity;
- check Warehouse;
- check posting chronology;
- check missing receipts/transactions.

Do not create a fake stock adjustment only to bypass the block.

---

## 24. Valuation

ERPNext calculates stock valuation.

Do not use selling price as the stock valuation unless ERPNext accounting intentionally produces that result.

Purchase cost, selling price and valuation are different concepts.

---

## 25. Low stock

Use Inventory Intelligence / Stock reports / reorder configuration to monitor low stock.

Set practical reorder levels per Item/Warehouse where the business uses them.

---

## 26. Stock movement review

Managers should periodically review:

- Material Receipts;
- Material Issues;
- Transfers;
- Stock Reconciliations;
- purchase receipts;
- sales/returns.

Unexpected adjustments deserve investigation.

---

## 27. Buying roles

Purchasing/inventory administration is normally for:

- Ledgix Manager;
- Ledgix Admin;
- appropriate ERPNext users.

Cashier is not normally responsible for back-office purchasing/stock corrections.

---

## 28. Common issue: stock received twice

Check whether:

- Purchase Receipt already moved stock;
- Purchase Invoice has Update Stock enabled;
- a second Stock Entry was posted.

Do not correct by deleting submitted ledgers.

Use the proper native return/cancellation/correction process.

---

## 29. Common issue: stock not received

Check:

- Purchase Receipt docstatus;
- target Warehouse;
- Item is a stock Item;
- Purchase Invoice update_stock if direct flow;
- Stock Ledger.

---

## 30. Common issue: supplier balance wrong

Check:

- Purchase Invoice;
- Purchase return;
- Payment Entries;
- Accounts Payable / GL.

Do not calculate AP from historical Ledgix Purchase records.

---

## 31. Purchase checklist

- [ ] correct Supplier
- [ ] correct Company
- [ ] Items/qty
- [ ] Warehouse
- [ ] rates/tax
- [ ] PO submitted
- [ ] actual goods received
- [ ] Purchase Receipt submitted
- [ ] Purchase Invoice posted
- [ ] supplier payment allocated
- [ ] stock/AP reviewed

---

## 32. Stock adjustment checklist

Before reconciliation:

- [ ] physical count performed
- [ ] missing transactions investigated
- [ ] correct Item
- [ ] correct Warehouse
- [ ] target quantity confirmed
- [ ] valuation reviewed if changing
- [ ] manager approval obtained where required

---

## 33. Advanced inventory availability

Advanced inventory screens are normally available on:

- Full Retail;
- Mixed.

Small Retail provides normal stock/buying without exposing all advanced stock-control tools by default.

---

## 34. What not to do

Do not:

- create new historical Ledgix Purchase records;
- create current Ledgix Stock Movement/Lot/Serial records;
- edit Stock Ledger Entry directly;
- change Bin directly;
- use Stock Reconciliation as routine transaction entry;
- duplicate receipt and stock-updating invoice;
- mix Warehouses from different Companies;
- ignore batch/serial rules.

---

## 35. Summary

> **Use ERPNext purchasing documents for ordering/receiving/payables, use Stock Entry for real movements and Stock Reconciliation only for verified physical corrections, and always treat ERPNext Stock Ledger/Bin as the official quantity and valuation.**
