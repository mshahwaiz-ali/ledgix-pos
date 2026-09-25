# Ledgix POS — Client Troubleshooting

**Audience:** Cashier, Manager, Ledgix Admin

## 1. First rule

Do not make random accounting/stock/FBR changes just to remove an error.

Use the message/status to identify the real problem.

If the issue involves:

- submitted accounting;
- stock ledger;
- FBR Reconciliation Required;
- Production setup;
- server update/recovery,

escalate to the responsible administrator.

---

## 2. I cannot log in

Check:

- correct site URL;
- correct email/user;
- Caps Lock;
- password;
- user is enabled.

If still blocked, ask the client administrator to reset/access-check your named user.

Do not use another person's account.

---

## 3. I logged in but cannot see Ledgix POS

Possible causes:

- Business Profile does not enable POS;
- you do not have Ledgix Cashier/Manager/Admin access;
- permissions were changed;
- setup is incomplete.

Ask Ledgix Admin/Manager.

---

## 4. I see fewer menu options than another user

This can be normal.

Navigation depends on:

- Business Profile;
- your role;
- ERPNext permissions.

Cashier intentionally sees less than Manager/Admin.

---

## 5. POS says no active shift

Open the shift first.

Current checkout requires an ERPNext POS Opening Entry.

If opening fails, contact Manager/Admin.

Do not bypass by creating a historical Ledgix shift.

---

## 6. Item not found at POS

Check:

- correct Item exists;
- Item enabled;
- correct barcode;
- correct selling setup.

Ask Manager to review Item master.

---

## 7. Barcode does not work

Try searching the Item by code/name.

If search works but scan does not:

- verify barcode in Item;
- verify scanner input;
- verify scanner is in correct mode.

Test scanner on a normal text field if necessary.

---

## 8. Price is wrong

Stop before posting if possible.

Ask Manager to check:

- Selling Price List;
- Item Price;
- Pricing Rule;
- Customer-specific pricing;
- UOM;
- effective dates.

Do not keep manually overriding every sale.

---

## 9. Tax is wrong

Ask Admin/accountant to review ERPNext tax setup.

Do not edit FBR mapping to fix a monetary-tax problem unless the issue is actually FBR classification.

---

## 10. Payment method missing

Check POS Profile/Mode of Payment configuration.

The Manager/Admin should verify:

- Mode of Payment exists;
- POS Profile includes it;
- Company account mapping exists.

---

## 11. Card/bank payment asks for reference

Enter the real reference/authorization value.

If the business does not use this requirement, ask the administrator to review the payment configuration.

Do not enter fake text.

---

## 12. Split payment will not complete

Check:

- all selected Modes of Payment are allowed;
- all amounts are positive;
- total tender meets the invoice requirement;
- partial payment policy;
- references are entered;
- change rules if over-tendered.

---

## 13. Checkout seems stuck

Do not repeatedly click Complete.

Wait briefly and check whether the POS Invoice was created.

If uncertain, ask Manager to search the latest transaction before attempting another sale.

---

## 14. Receipt will not print

Check:

- browser printer selection;
- printer powered/connected;
- paper;
- correct print format;
- browser popup/print settings.

If the invoice exists, printing can normally be retried without creating another sale.

---

## 15. Receipt is cut off

Check:

- printer paper width;
- scale;
- margins;
- correct thermal print format.

Record printer model/paper width and ask Admin/technical support.

Do not modify invoice data to fix layout.

---

## 16. Return is blocked

Check:

- original POS/Sales Invoice is submitted;
- correct original invoice selected;
- correct Item/row selected;
- return quantity not above remaining returnable quantity;
- return reason supplied;
- active POS shift for retail return.

---

## 17. Customer says refund not received

Check whether:

- Credit Note exists;
- refund Payment Entry exists.

A Credit Note alone does not prove cash/bank was refunded.

---

## 18. Customer outstanding looks wrong

Ask Manager/accounts staff to inspect:

- Sales Invoice;
- Payment Entry;
- Credit Note;
- Customer Statement.

Do not create another payment until the first payment is checked.

---

## 19. Customer payment rejected

Check:

- invoice submitted;
- outstanding positive;
- correct Customer;
- correct Company;
- amount <= outstanding;
- correct payment method/account.

---

## 20. Purchase receipt not changing stock

Check:

- Purchase Receipt is submitted;
- Item is stock Item;
- Warehouse correct;
- no duplicate/direct stock workflow confusion.

Manager should inspect Stock Ledger.

---

## 21. Stock quantity looks wrong

Use:

- Inventory Intelligence;
- Stock Balance;
- Stock Ledger.

Trace the vouchers that changed quantity.

Do not manually edit stock quantity.

---

## 22. Stock Reconciliation should I use it?

Only when the real business fact is a verified physical count/valuation correction.

Do not use it just because:

- a sale was forgotten;
- a purchase was not entered;
- a transfer is missing.

Record the real transaction first.

---

## 23. Batch/serial error

Check:

- Item setup;
- correct Batch/Serial;
- Warehouse stock;
- quantity.

Ask stock Manager.

Do not type random batch/serial identifiers.

---

## 24. Supplier balance looks wrong

Review:

- Purchase Invoice;
- Purchase return;
- supplier Payment Entry;
- Accounts Payable/GL.

Do not use old Ledgix Purchase history as current AP.

---

## 25. FBR says Not Submitted

Possible reasons:

- FBR disabled;
- invoice not eligible;
- readiness incomplete;
- manual trigger not used;
- certification/Production not active.

Ask Ledgix Admin to review Tax & FBR Center.

---

## 26. FBR says Failed

Review the error and Submission Log.

Common areas:

- seller identity;
- buyer identity;
- Item Mapping;
- official reference data;
- token/mode;
- payload readiness.

Correct the real data/configuration.

Do not manually change Failed to Submitted.

---

## 27. FBR says Reconciliation Required

STOP.

Do not retry.

Tell Ledgix Admin/System Manager immediately.

This means FBR may have received a Production POST but the local result is uncertain.

External reconciliation is required.

---

## 28. FBR says Offline Pending

This invoice is in the controlled Known Offline workflow.

Do not submit it through another route.

Authorized Admin should:

- check upload due time;
- use the controlled Offline Pending queue;
- upload through the approved action when connectivity/policy allows.

---

## 29. FBR QR is missing

Check whether:

- invoice actually has accepted FBR number/reference;
- correct print format is used;
- FBR submission completed.

Do not invent a QR.

---

## 30. FBR Production is not ready

This may be correct.

Production stays blocked until:

- real Sandbox proof;
- certification;
- Production token;
- mappings/reference;
- DI logo where required;
- fresh backup;
- approved release;
- zero reconciliation;
- explicit authorization.

Do not bypass the gate.

---

## 31. I accidentally see an old Ledgix Sale/Purchase screen

Migrated sites can contain historical records.

If it is read-only, leave it read-only.

Use current:

- Sales Invoice;
- POS Invoice;
- Purchase documents;
- Payment Entry;
- stock documents.

Report unexpected writable historical records to the administrator.

---

## 32. A report total looks wrong

First verify filters:

- Company;
- date range;
- Customer/Supplier;
- Warehouse.

Then inspect source ERPNext transactions.

Do not edit transactions just to match a manual report.

---

## 33. Profit looks wrong

Ask accountant/Manager to review:

- sales;
- returns;
- Item valuation;
- COGS;
- expenses/income accounts;
- purchase/stock chronology.

---

## 34. Site shows maintenance message

The technical team may be:

- deploying an update;
- recovering from an issue;
- running a controlled maintenance operation.

Do not attempt repeated transactions.

Wait for the administrator to confirm the site is reopened.

---

## 35. Site gives 502 / unavailable

Notify technical administrator.

Provide:

- site URL;
- time;
- screenshot/error text;
- what you were doing.

Do not repeatedly refresh/submit a payment or sale if you are unsure whether it posted.

---

## 36. After a network outage

For ordinary ERPNext/Ledgix operations:

- check whether the transaction already exists before repeating it.

For FBR Production:

- if Reconciliation Required appears, do not retry;
- if a properly approved Known Offline workflow is active, follow that controlled process.

---

## 37. Backup error

If technical/admin staff report backup verification failed:

- pause major updates/go-live;
- create a new verified backup.

Do not proceed based on an unverified recovery point.

---

## 38. Update failed and site remains in maintenance

This is a safety behavior.

The technical administrator must decide whether to:

- repair current release; or
- restore previous known-good release/backup.

Do not ask them to simply disable maintenance first.

---

## 39. What information to send support

Useful information:

- site/domain;
- your user/role;
- exact time;
- page/document type;
- document number;
- exact error text;
- screenshot with secrets hidden;
- what action you pressed;
- whether you retried.

Do not send:

- passwords;
- database credentials;
- FBR tokens.

---

## 40. What not to do

Never troubleshoot by:

- sharing Administrator password;
- assigning System Manager to everyone;
- deleting submitted invoices;
- editing GL/Stock Ledger;
- creating fake stock movements;
- editing historical Ledgix ledgers;
- changing FBR success status manually;
- retrying Reconciliation Required;
- inventing FBR token/reference/QR.

---

## 41. Escalation guide

### Cashier can handle

- normal item/customer selection;
- normal payment entry;
- normal receipt retry;
- correct input mistake before submission.

### Manager should handle/review

- price/master data;
- returns;
- stock review;
- shift discrepancy;
- purchasing;
- reports;
- FBR status observation.

### Ledgix Admin/System Manager required

- setup/profile;
- roles/permissions;
- FBR configuration;
- Known Offline declaration/upload;
- Reconciliation Required release after external proof;
- Production activation;
- technical configuration.

### Technical administrator required

- site unavailable;
- migrate/deployment;
- backup/restore;
- code/release issue;
- server/Nginx/Supervisor.

---

## 42. Summary

> **Check the real ERPNext transaction/configuration behind the error, avoid duplicate retries, and escalate any accounting/stock/FBR ambiguity instead of forcing the screen to pass.**
