# Ledgix POS — Daily POS Operations

**Audience:** Cashiers, store managers, retail operators  
**Applies to:** Small Retail, Full Retail and Mixed profiles

## 1. Purpose

This guide explains the normal daily retail workflow in Ledgix POS.

The official retail transaction is the ERPNext POS Invoice created through the Ledgix POS screen.

Use this guide for:

- opening a shift;
- selling;
- barcode/item search;
- split payment;
- change;
- hold/resume;
- returns;
- closing a shift;
- receipt printing.

---

## 2. Before the first sale

Confirm the store has:

- an enabled POS Profile;
- correct Company;
- correct Warehouse;
- correct Selling Price List;
- default/walk-in Customer;
- Modes of Payment;
- correct Company accounts for payment methods;
- Items/prices;
- named Cashier user;
- receipt printer/scanner tested where used.

If any of these are missing, ask a Manager/Admin to fix setup before selling.

---

## 3. Sign in with your own user

Use your own named account.

Do not share the Administrator or another cashier's login.

Your activity should be attributable to the person actually operating the POS.

---

## 4. Open Ledgix POS

Cashiers normally land directly on:

    Ledgix POS

If not, open it from the Ledgix navigation.

If POS is not visible:

- confirm your role;
- confirm the Business Profile enables POS;
- ask the administrator to review permissions.

---

## 5. Open the shift

Before checkout, open the POS shift.

Ledgix creates/uses the ERPNext POS Opening Entry for your user and POS Profile.

Enter the opening cash amount where required.

The system may reuse an already active opening for the same user/profile instead of creating a duplicate.

---

## 6. Opening cash

Opening cash should match the actual cash in the drawer at shift start.

Do not enter a random amount simply to continue.

It affects the expected cash calculation at closing.

---

## 7. If shift will not open

Check:

- correct POS Profile;
- POS Profile is enabled;
- default Customer exists;
- Warehouse exists;
- payment methods exist;
- you have permission;
- there is not an existing conflicting opening.

Escalate to Manager/Admin if needed.

Do not create an old Ledgix POS Shift manually.

---

## 8. Search for an item

You can normally add Items using:

- item search;
- barcode scan;
- item code/name selection.

The product comes from ERPNext Item master data.

If an Item is missing, the master data must be corrected by an authorized user.

---

## 9. Barcode scanning

A normal keyboard-wedge scanner can use the same item-selection input as manual entry.

Before go-live, verify the actual scanner with real Items.

If a barcode does not find the product:

- verify Item Barcode in ERPNext;
- verify scanner sends the expected characters;
- check that the Item is active/sellable.

---

## 10. Quantity

Enter the required quantity.

For stock-controlled Items, stock availability comes from ERPNext.

Do not try to bypass a stock warning by using a historical Ledgix stock screen.

---

## 11. Price

Ledgix uses the ERPNext Selling Price List/pricing rules.

If the price looks wrong:

- stop before posting;
- verify Item/Price List/Pricing Rule;
- ask a Manager if an override is genuinely required.

Do not routinely change price manually to work around bad master data.

---

## 12. Customer

Retail can use the default/walk-in Customer configured on the POS Profile.

Select the real Customer when needed for:

- customer-specific invoice;
- account/credit relationship;
- customer history;
- FBR buyer identity;
- business/customer receipt details.

---

## 13. Review the cart

Before payment confirm:

- Items;
- quantities;
- prices;
- discounts;
- Customer;
- tax;
- total.

Correct errors before submitting the sale.

---

## 14. Payment

Choose the payment method(s) accepted by the store.

Typical examples:

- Cash;
- Card;
- Bank.

Only payment methods configured on the POS Profile should be used.

---

## 15. Split payment

Ledgix supports split tender using the same POS Invoice.

Example:

    Total: 3,000

    Cash: 1,000
    Card: 2,000

Enter each payment separately.

The split is stored on the official POS Invoice.

There is no separate current Ledgix payment ledger for the same sale.

---

## 16. Payment reference

Some payment methods can require a reference number.

Examples:

- card authorization/reference;
- transfer/reference number.

If the system asks for a reference, enter the real transaction reference.

Do not enter fake text just to continue.

---

## 17. Partial payment

Partial payment behavior depends on the POS Profile.

If partial payment is not allowed, Ledgix will require enough payment to cover the invoice.

If the business needs partial payment at POS, the POS Profile must be configured accordingly.

---

## 18. Cash over-tender and change

If the customer gives more cash than the sale total, Ledgix can calculate change when the POS payment configuration allows it.

Example:

    Sale: 2,750
    Cash received: 3,000
    Change: 250

Use the configured cash method.

Do not over-tender a non-cash method simply to force checkout.

---

## 19. Complete sale

When everything is correct, complete checkout.

The system submits an ERPNext POS Invoice.

After completion verify:

- sale is successful;
- amount is correct;
- payment split is correct;
- receipt can be printed.

---

## 20. Avoid repeated checkout clicks

If the browser/network feels slow after pressing checkout:

- do not repeatedly create another transaction;
- first check whether the sale already completed.

Ledgix has retry/idempotency protection, but operators should still avoid unnecessary repeated actions.

---

## 21. Print receipt

Use the current Ledgix ERPNext POS receipt format.

Verify:

- business identity;
- Items/quantities;
- total;
- tax;
- payment;
- FBR reference/QR only where genuine FBR evidence exists.

Do not treat a placeholder/local QR as official FBR certification.

---

## 22. Hold a cart

Use Hold when the customer has not completed the sale and you need to temporarily save the cart.

A held retail cart is saved as a draft ERPNext POS Invoice.

Holding does not:

- post accounting;
- reduce the customer's balance as a submitted invoice;
- complete the sale.

---

## 23. Resume a held cart

Open the held transaction and resume it.

Recheck:

- Items;
- prices;
- quantities;
- Customer.

Pricing can be re-evaluated depending on the current transaction context.

---

## 24. Cancel a hold

If the customer abandons the transaction, cancel the held cart through the supported Ledgix hold workflow.

A cancelled hold is not the same as returning a submitted sale.

---

## 25. Retail return

A return must be linked to the original submitted POS Invoice.

Process:

1. locate original sale;
2. choose the Items/rows to return;
3. enter return quantity;
4. enter the return reason;
5. submit the return.

An active POS opening is required for the current retail return workflow.

---

## 26. Return quantity

You cannot legitimately return more than the remaining returnable quantity.

The system considers quantity already returned.

If the return is blocked:

- confirm original invoice;
- confirm exact item/row;
- confirm previous returns;
- confirm quantity.

---

## 27. Return price

The return uses the original sale's pricing.

Do not type a new arbitrary price for a return.

This protects the original commercial/accounting history.

---

## 28. Return receipt

The result is an ERPNext return POS Invoice.

Print the return document as required by business policy.

FBR return/note terminology should only be treated as certified when the client's actual FBR workflow has been proven.

---

## 29. Exchange

If a customer returns one product and buys another:

- process the return correctly;
- create the replacement sale correctly.

Do not hide the exchange as an undocumented manual stock/payment adjustment.

---

## 30. Closing the shift

At end of shift, close the POS.

Ledgix uses ERPNext POS Closing Entry.

Review expected payment totals and enter the actual cash amount where required.

---

## 31. Count cash physically

Before final close:

- count drawer cash;
- remove/identify opening cash according to business policy;
- compare to expected cash.

Record the actual amount.

Do not change sales just to make the drawer match.

---

## 32. Non-cash methods

Card/bank totals should be checked against the actual terminal/bank evidence where required.

The system can use expected native totals for configured non-cash payment rows.

The business should still perform its normal reconciliation.

---

## 33. Submit closing

Submit the POS Closing Entry.

ERPNext then performs its normal POS closing/consolidation behavior.

The closing is the official shift-close record.

---

## 34. If closing fails

Check:

- active opening;
- unclosed POS Invoices;
- payment reconciliation;
- cash method;
- system error message.

Ask Manager/Admin to investigate.

Do not manually edit submitted POS Invoices or old Ledgix shift records.

---

## 35. FBR at POS

If FBR is enabled, the submitted POS Invoice is the business source for FBR.

A cashier should not manually create another FBR transaction for the same sale.

FBR status may show states such as:

- Not Submitted;
- Ready;
- Submitted;
- Failed;
- Offline Pending;
- Reconciliation Required.

Follow the FBR client guide for exceptional states.

---

## 36. Reconciliation Required at POS

If an invoice shows:

    Reconciliation Required

stop any repeated FBR submission attempts.

This can mean a Production request may have reached FBR but the local outcome is uncertain.

Escalate to Ledgix Admin/System Manager.

---

## 37. Offline Pending

If the business has an approved Known Offline workflow, an invoice can be marked Offline Pending through the controlled admin process.

Cashiers should not invent or clear this state manually.

---

## 38. Daily cashier checklist

### Start

- [ ] sign in with own user
- [ ] POS screen opens
- [ ] shift opened
- [ ] opening cash entered correctly
- [ ] scanner/printer available

### During sales

- [ ] correct Customer
- [ ] correct Item/qty
- [ ] price checked
- [ ] payment method correct
- [ ] payment reference entered where required
- [ ] receipt issued

### Returns

- [ ] original sale selected
- [ ] quantity valid
- [ ] reason entered
- [ ] return receipt issued

### End

- [ ] drawer counted
- [ ] payment totals reviewed
- [ ] shift closing submitted
- [ ] discrepancies reported

---

## 39. What Cashiers should never do

Do not:

- use another employee's login;
- modify accounting configuration;
- edit old historical Ledgix Sale/Payment/Shift records;
- create stock corrections to fix a POS mistake;
- manually change FBR success status;
- repeatedly retry Reconciliation Required invoices;
- fabricate payment/FBR references.

---

## 40. Summary

> **Open the native POS shift, sell through Ledgix POS, use configured payments, link every return to its original POS Invoice, and close/reconcile the shift through ERPNext at the end of the day.**
