# Ledgix POS — Master Data and Pricing

**Audience:** Client administrator, manager, inventory/pricing staff

## 1. Purpose

This guide explains how to maintain the main business records used by Ledgix.

Current business master data is stored in ERPNext.

Use ERPNext records for:

- Company;
- Customer;
- Supplier;
- Item;
- Item Group;
- Warehouse;
- Price List;
- Item Price;
- Pricing Rule;
- Mode of Payment;
- POS Profile.

Do not create duplicate historical Ledgix masters for current operation.

---

## 2. Company

Company defines the legal/accounting business.

Before operations, verify:

- Company Name;
- country;
- default currency;
- tax ID where applicable;
- Chart of Accounts;
- accounting defaults;
- default address.

For FBR clients, legal identity must match the real registered seller.

---

## 3. Chart of Accounts

ERPNext accounting requires a valid Chart of Accounts.

Ledgix onboarding checks that the Company has accounts.

Depending on the Business Profile, also verify relevant defaults such as:

- receivable;
- income;
- payable;
- expense.

Your accountant/ERPNext administrator should review these before go-live.

---

## 4. Customer

Use ERPNext Customer for every current customer.

Typical uses:

- walk-in retail Customer;
- individual customer;
- business customer;
- credit/account customer.

For POS, set the correct default/walk-in Customer on the POS Profile.

For B2B/FBR, use the customer's real legal/business information where required.

---

## 5. Customer FBR details

When FBR requires buyer information, ERPNext Customer can include Ledgix FBR buyer fields such as:

- Buyer Registration Type;
- Buyer NTN/CNIC;
- Buyer STRN;
- Buyer Province;
- Buyer FBR Address;
- verification status.

Enter real client/customer data.

Do not invent NTN/CNIC/registration details just to pass readiness.

---

## 6. Supplier

Use ERPNext Supplier for current purchasing.

Maintain:

- supplier name;
- supplier group/type as applicable;
- tax/contact/address information;
- payment/accounting information required by the business.

Do not use historical Ledgix Supplier for new purchasing.

---

## 7. Item

Use ERPNext Item for:

- retail products;
- wholesale products;
- services;
- stock items;
- non-stock/service items.

Configure:

- Item Code;
- Item Name;
- Item Group;
- Stock UOM;
- is stock item;
- sales/purchase settings;
- barcode;
- batch/serial settings;
- taxes/pricing as needed.

---

## 8. Item Groups

Use Item Groups to organize catalog.

Examples:

- Grocery;
- Cosmetics;
- Electronics;
- Services.

Keep the hierarchy practical.

Do not create excessive categories that staff cannot use consistently.

---

## 9. Stock vs non-stock Items

### Stock Item

Use when quantity should be tracked.

Examples:

- physical retail product;
- warehouse goods.

Stock changes through native ERPNext stock transactions.

### Non-stock/service Item

Use for services or items where inventory quantity is not tracked.

Examples:

- professional service;
- fee;
- installation/service charge.

Choose correctly before go-live.

---

## 10. Barcode

For scanner-based POS, maintain ERPNext Item barcodes.

Test each barcode with the actual scanner.

A scanner usually behaves like keyboard input, but physical compatibility must be tested during UAT.

---

## 11. Batch-controlled Item

Enable ERPNext batch tracking for Items that require lot/batch control.

Examples may include:

- expiry-sensitive stock;
- regulated batch goods.

Batch identity is maintained in ERPNext Batch.

Full Retail/Mixed profiles expose the advanced inventory screens required for these workflows.

---

## 12. Serial-controlled Item

Enable ERPNext serial tracking for individually identified units.

Serial identity is maintained in ERPNext Serial No.

Use only when the business really needs individual-unit tracking.

---

## 13. Warehouse

Warehouse represents the stock location.

A Warehouse used by Ledgix POS/inventory should be:

- enabled;
- non-group/leaf;
- assigned to the correct Company.

Examples:

- Main Store;
- Branch 1;
- Warehouse A.

Do not use another Company's Warehouse.

---

## 14. Default Warehouse

The Ledgix Setup Wizard can apply the selected Warehouse as the ERPNext site default where appropriate.

Review this before applying on a multi-Company/complex site.

POS also uses the Warehouse configured on the POS Profile.

---

## 15. Selling Price List

Selling profiles require an enabled ERPNext Selling Price List.

Examples:

- Standard Selling;
- Retail;
- Wholesale.

Choose the Price List that matches the business/customer channel.

---

## 16. Item Price

Use ERPNext Item Price to store price for an Item under a Price List.

Maintain:

- Item;
- Price List;
- rate;
- UOM where applicable;
- validity/effective date where used.

Ledgix uses ERPNext pricing rules, not a separate current Ledgix price table.

---

## 17. Pricing Rules

Use ERPNext Pricing Rule for controlled automatic pricing/discount behavior.

Examples:

- customer-specific discount;
- quantity-based pricing;
- campaign discount.

Review rules carefully to avoid overlapping/contradictory discounts.

---

## 18. Effective price

The final price can depend on:

- Item Price;
- Price List;
- Customer;
- UOM;
- Pricing Rule;
- date/effective validity.

If the POS/invoice price looks wrong, review these ERPNext settings first.

---

## 19. Manual price override

Where Ledgix allows an authorized price override, treat it as an exception.

Best practice:

- normal prices maintained in ERPNext;
- manager override used only when approved;
- reason/audit preserved where applicable.

Do not make manual override the normal pricing process.

---

## 20. Buying Price List

If the client uses purchasing, configure the appropriate ERPNext buying/pricing data.

Purchase document rates can also come from supplier/item transaction context.

Do not use selling price as a replacement for purchase cost.

---

## 21. Mode of Payment

Use ERPNext Mode of Payment for methods such as:

- Cash;
- Bank;
- Card.

Each selling/payment-enabled client should have at least one valid Company account mapping.

If the Company account is missing, payment posting can be blocked.

---

## 22. Payment account mapping

For each Mode of Payment, verify the Company-specific account.

Examples:

- Cash -> Cash account;
- Bank -> Bank account;
- Card -> appropriate clearing/bank account.

Use accounts approved by your accountant.

---

## 23. POS payment methods

The POS Profile controls which Modes of Payment are available at retail checkout.

Add only payment methods actually accepted by the store.

If a payment method requires a reference number, ensure staff know when/how to enter it.

---

## 24. POS Profile

A POS-enabled client requires ERPNext POS Profile.

Verify:

- Company;
- enabled status;
- default Customer;
- Warehouse;
- Selling Price List;
- Modes of Payment.

The Ledgix Setup Wizard blocks incomplete POS Profile configuration.

---

## 25. Default/walk-in Customer

Retail POS normally requires a default Customer.

Create a proper ERPNext Customer such as your approved walk-in customer.

Use the actual customer instead when a transaction needs customer-specific identity/credit/FBR details.

---

## 26. Tax setup

ERPNext calculates monetary tax.

Depending on the business, configure:

- Tax Category;
- Tax Rule;
- Sales Taxes and Charges Template;
- Item Tax Template;
- tax Accounts.

Work with your accountant/tax adviser for correct tax setup.

---

## 27. FBR classification is separate

Ledgix FBR Item Mapping can contain:

- HS Code;
- FBR UOM;
- FBR Sale/Transaction Type;
- regulatory rate/reference description;
- tax basis;
- SRO references;
- effective dates.

These fields support FBR classification.

They do not replace ERPNext monetary tax calculation.

---

## 28. Notified Retail Price / special tax basis

Some FBR Items may require a special taxable basis such as Notified Retail Price.

Only configure this using verified legal/FBR information.

Do not guess the value.

Ledgix passes the approved basis into the ERPNext tax calculation.

---

## 29. Price vs tax vs FBR classification

Keep these three concepts separate:

### Price

What the customer pays before/with discounts.

Maintained through ERPNext pricing.

### Monetary tax

Tax amount posted on the ERPNext invoice.

Maintained through ERPNext tax configuration/calculation.

### FBR classification

How the transaction/item is described/mapped for FBR.

Maintained through Ledgix FBR mapping/reference data.

Do not try to solve one by changing another.

---

## 30. Opening stock

For a new inventory client, opening stock should be created through the approved ERPNext stock process.

Do not type starting quantities into an old Ledgix stock table.

Opening quantity affects:

- stock availability;
- valuation;
- accounting.

Coordinate with the implementation/accounting team.

---

## 31. Stock corrections

If physical stock differs later, use the correct ERPNext process.

Possible options:

- missing sale/purchase -> enter/fix the real transaction;
- stock transfer -> Stock Entry;
- verified physical count correction -> Stock Reconciliation.

Do not use Stock Reconciliation to hide missing business transactions.

---

## 32. Data quality before go-live

Review:

- duplicate Customers;
- duplicate Suppliers;
- duplicate Items;
- wrong UOM;
- missing prices;
- missing Warehouse;
- bad barcodes;
- incorrect stock/non-stock flag;
- incomplete payment mappings;
- incorrect POS Profile;
- incomplete tax setup;
- incomplete FBR mapping.

Clean master data prevents most daily-operation problems.

---

## 33. Who should maintain master data

Suggested:

### Ledgix Admin / authorized ERPNext admin

- Company setup;
- accounting;
- Business Profile;
- major tax/FBR setup;
- user/security.

### Ledgix Manager / authorized back-office staff

- Items;
- pricing;
- Customers/Suppliers;
- purchasing/inventory configuration according to permissions.

### Cashier

Normally consumes configured master data at POS.

Avoid giving Cashiers broad master-data edit access unless the business explicitly requires it.

---

## 34. Change control

Before large master-data changes:

- take/export appropriate backup;
- document why the change is needed;
- test pricing/tax/stock consequence;
- avoid changing submitted historical documents;
- verify result after change.

FBR-sensitive mappings should be reviewed particularly carefully.

---

## 35. Master-data checklist

### Company

- [ ] correct legal name
- [ ] currency/country
- [ ] tax ID
- [ ] Company Address
- [ ] Chart of Accounts
- [ ] required account defaults

### Selling

- [ ] Customer
- [ ] Item
- [ ] Selling Price List
- [ ] Item Prices
- [ ] Pricing Rules if used
- [ ] Mode of Payment accounts

### POS

- [ ] default Customer
- [ ] Warehouse
- [ ] Selling Price List
- [ ] Modes of Payment
- [ ] barcodes tested

### Buying/Inventory

- [ ] Suppliers
- [ ] Warehouse
- [ ] stock/non-stock Item flags
- [ ] opening stock
- [ ] batch/serial setup where required

### Tax/FBR

- [ ] ERPNext monetary tax setup
- [ ] FBR Item Mapping
- [ ] FBR Tax Component Mapping
- [ ] legal/special tax-basis data reviewed

---

## 36. Summary

> **Maintain customers, suppliers, items, warehouses, prices, payments and monetary tax in ERPNext; use Ledgix FBR mappings only for compliance classification, and keep master data clean before staff begin daily operations.**
