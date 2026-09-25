# Ledgix POS — Getting Started

**Audience:** Client owner, administrator or implementation lead  
**Goal:** Configure a newly provisioned Ledgix site for business use

## 1. Before you begin

Your Ledgix site should already be installed by your technical administrator.

A correctly provisioned site contains:

- Frappe;
- ERPNext;
- Ledgix.

Installation alone does not make the site business-ready.

The next step is to configure the client's real business setup.

---

## 2. What Ledgix setup does

Ledgix uses existing ERPNext business configuration.

The setup process selects:

- Company;
- Business Profile;
- Warehouse where needed;
- Selling Price List;
- POS Profile where needed.

The setup wizard does not create duplicate:

- Items;
- Customers;
- accounting ledgers;
- stock ledgers.

ERPNext remains the official business system.

---

## 3. What must exist before Ledgix setup

Depending on the selected Business Profile, configure the relevant ERPNext records first.

Common requirements:

- Company;
- Chart of Accounts;
- Company accounting defaults;
- Selling Price List;
- at least one Mode of Payment with Company account mapping;
- named users.

For retail/inventory/buying profiles also configure:

- active non-group Warehouse;
- Items;
- POS Profile;
- default/walk-in Customer;
- payment methods on the POS Profile.

For buying:

- Suppliers;
- buying/accounting defaults.

For FBR:

- Company legal identity;
- Company Address;
- company-scoped FBR Integration Profile.

---

## 4. Open Ledgix Client Setup

Sign in as:

- Ledgix Admin; or
- System Manager.

Open the Ledgix Setup Wizard.

From the Ledgix workspace, use:

    Setup Wizard

The Page title is:

    Ledgix Client Setup

---

## 5. Choose your Company

Select the ERPNext Company that this Ledgix setup will operate against.

Verify before continuing:

- correct legal business;
- correct currency;
- correct country;
- correct Chart of Accounts.

Do not select a test Company for a real client go-live.

---

## 6. Choose a Business Profile

Available profiles:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

### Invoice + FBR Only

Choose when:

- no retail POS is needed;
- stock operations are not being managed through Ledgix;
- the business mainly issues invoices/digital invoices.

Enabled experience includes:

- Sales Invoice;
- FBR;
- accounting.

### Small Retail

Choose when:

- counter POS is required;
- normal inventory/purchases are required;
- advanced batch/serial controls are not needed.

Enabled experience includes:

- Sales Invoice;
- POS;
- inventory;
- buying;
- FBR;
- accounting.

### Full Retail

Choose when Small Retail is not enough and the business requires:

- Stock Entry;
- Stock Reconciliation;
- Batch;
- Serial Number;
- advanced inventory controls.

### B2B

Choose when:

- account customers/wholesale are primary;
- sales are invoice-led rather than counter POS.

Enabled experience includes:

- Sales Invoice;
- B2B features;
- FBR;
- accounting.

### Mixed

Choose when the business uses:

- retail POS;
- B2B/account sales;
- buying;
- full inventory;
- accounting;
- FBR.

---

## 7. Select the Selling Price List

If selling is enabled, select an enabled ERPNext Selling Price List.

Examples might include:

- Standard Selling;
- Retail;
- Wholesale.

Use the price list actually approved for this business.

Do not create prices only inside a cash register or external spreadsheet and expect Ledgix to know them automatically.

---

## 8. Select Warehouse

Profiles using:

- POS;
- inventory;
- buying

require a valid ERPNext Warehouse.

The Warehouse must be:

- enabled;
- a leaf/non-group Warehouse;
- part of the selected Company.

Choose the Warehouse that represents the actual operating location/stock pool.

---

## 9. Select POS Profile

Profiles with POS enabled require an enabled ERPNext POS Profile.

The selected POS Profile must have:

- same Company;
- enabled status;
- default Customer;
- Warehouse;
- Selling Price List;
- at least one Mode of Payment.

If any of these are missing, Ledgix readiness will block POS setup.

---

## 10. Apply ERPNext site defaults

The setup screen includes:

    Apply ERPNext Site Defaults

When enabled, Ledgix can safely set the selected configuration as relevant ERPNext site defaults, such as:

- Company;
- Selling Price List;
- Warehouse.

Use this when the selected values should be the site's normal default.

For multi-Company/complex ERPNext sites, review this carefully before applying.

---

## 11. Run Check Readiness

Before applying configuration, click:

    Check Readiness

You will see:

- green checks;
- warnings;
- blocking checks.

Do not apply while blocking prerequisites remain.

Resolve each blocker in the ERPNext configuration it identifies.

---

## 12. Apply Configuration

When readiness is green, click:

    Apply Configuration

Confirm the action.

Ledgix records:

- selected Business Profile;
- configured Company;
- setup completion state;
- setup time/user;
- selected safe defaults.

It does not create a second set of business masters.

---

## 13. Refresh Operational Onboarding

After applying setup, use:

    Refresh Onboarding

This checks the site for handover readiness.

Checks can include:

- Company Chart of Accounts;
- receivable/income defaults;
- payable/expense defaults where buying is enabled;
- Mode of Payment Company account mapping;
- Ledgix role definitions;
- named operational users;
- cashier availability on POS-enabled clients;
- FBR safety/setup state;
- release/backup evidence visibility.

---

## 14. Create named users

Do not operate the client permanently as Administrator.

Create named users for actual staff.

At least one enabled named user should have a Ledgix operational role:

- Ledgix Admin;
- Ledgix Manager;
- Ledgix Cashier.

POS-enabled sites should normally have at least one named Ledgix Cashier.

---

## 15. Configure payment methods

Selling/payment-enabled profiles require at least one valid Mode of Payment account mapping for the selected Company.

Typical examples:

- Cash;
- Bank;
- Card.

For each Mode of Payment:

- verify it is active;
- verify the Company account mapping;
- verify POS Profile includes it when used at POS.

If the payment method requires a reference number, staff must enter it during payment.

---

## 16. Configure Customers

Create ERPNext Customers.

For retail POS, configure a default/walk-in Customer on the POS Profile.

For B2B/account customers, use proper individual/company Customer records.

If FBR applies, buyer legal information may also be required.

---

## 17. Configure Items

Create ERPNext Items with:

- correct Item Group;
- UOM;
- stock/non-stock setting;
- selling price;
- tax configuration;
- barcode where used.

If the item is batch/serial controlled, configure that in ERPNext Item.

Do not create a second Ledgix Item for current operation.

---

## 18. Configure pricing

Use ERPNext:

- Price List;
- Item Price;
- Pricing Rule where required.

Ledgix uses ERPNext pricing.

A manager price override, where allowed, should be treated as an exception, not the main price-maintenance process.

---

## 19. Configure taxes

Monetary tax is configured in ERPNext.

Depending on the business this can include:

- Tax Category;
- Tax Rule;
- Sales Taxes and Charges Template;
- Item Tax Template;
- tax Accounts.

FBR Item Mapping is for FBR classification, not a replacement monetary tax calculator.

---

## 20. Configure FBR separately

If your Business Profile enables FBR, continue with:

    FBR_SETUP_AND_OPERATIONS.md

Do not assume FBR is ready because the Business Profile says FBR is enabled.

Your site still needs genuine:

- seller identity;
- mapping;
- reference data;
- Sandbox credential;
- Sandbox proof/certification;
- Production credential/approval when appropriate.

---

## 21. Test the business workflows

Before handover, test the workflows relevant to your profile.

### Invoice + FBR Only

Test:

- Customer;
- Item/service;
- Sales Invoice;
- payment;
- print;
- FBR Sandbox flow when available.

### Small Retail

Test:

- POS opening;
- item search/barcode;
- sale;
- split payment/change;
- return;
- closing;
- receipt print;
- stock movement.

### Full Retail

Small Retail tests plus:

- purchase receipt;
- Stock Entry;
- Stock Reconciliation;
- Batch/Serial if used.

### B2B

Test:

- Customer;
- invoice;
- partial/full payment;
- outstanding;
- return/Credit Note;
- customer statement;
- print.

### Mixed

Test both retail and B2B paths.

---

## 22. Device testing

If the business uses:

- thermal printer;
- A4 printer;
- barcode scanner;
- cash drawer or related equipment,

test the real devices.

Software checks cannot prove physical printer/scanner behavior.

---

## 23. Backup/go-live readiness

Before Production go-live ensure:

- client configuration is green;
- named staff users exist;
- manual workflow/device UAT is complete;
- verified backup exists;
- approved software release is recorded;
- FBR certification is complete if FBR Production is part of go-live.

---

## 24. Important stop conditions

Do not go live if:

- setup readiness has blockers;
- Company accounting is incomplete;
- payment account mapping is missing;
- POS Profile is incomplete;
- stock location is wrong;
- staff access is not tested;
- backup is not verified;
- FBR Production is being assumed without real certification.

---

## 25. After go-live

Normal maintenance should include:

- user/access review;
- regular verified backups;
- ERPNext master-data maintenance;
- stock/accounting reconciliation;
- controlled system updates;
- FBR evidence review where applicable.

Do not make ad-hoc technical changes on Production without backup/change control.

---

## 26. Quick handover checklist

- [ ] Company selected
- [ ] correct Business Profile selected
- [ ] Selling Price List selected
- [ ] Warehouse selected where required
- [ ] POS Profile selected where required
- [ ] Check Readiness green
- [ ] configuration applied
- [ ] Operational Onboarding green
- [ ] named users created
- [ ] correct roles assigned
- [ ] Items/Customers/Suppliers configured
- [ ] payment account mappings configured
- [ ] tax setup reviewed
- [ ] FBR onboarding completed if applicable
- [ ] workflow UAT complete
- [ ] printer/scanner UAT complete
- [ ] verified backup available
- [ ] go-live approved

---

## 27. Summary

> **Configure ERPNext first, select the Ledgix profile that matches the business, resolve all readiness blockers, test real workflows/devices, and complete FBR/backup/go-live evidence before Production use.**
