# Ledgix POS — Sales, Returns and Payments

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Primary implementation:** services/erpnext_selling.py + api/selling_compat.py

## 1. Purpose

This document describes the current non-retail/B2B selling, customer payment, receivable, return, refund and exchange architecture.

Current financial authority is ERPNext:

- Sales Invoice;
- Payment Entry;
- native Sales Invoice return / Credit Note;
- ERPNext outstanding / AR / GL.

Ledgix contributes:

- product UX;
- compatibility;
- idempotency metadata;
- controlled price-override audit;
- allocation validation;
- return selection;
- exchange linkage;
- FBR compliance around the same native invoice.

Historical Ledgix Sale / Payment / Sales Return are not current financial authority.

---

## 2. Core service boundary

Primary reusable service:

    services/erpnext_selling.py

Stable/compatibility API:

    api/selling_compat.py

hooks.py redirects historical Ledgix B2B RPC contracts into selling_compat.

The current implementation should therefore be read from the compatibility API + native service, not from an old generic selling module in isolation.

---

## 3. Identity resolution

The selling service resolves:

- Company;
- Customer;
- Item;
- Selling Price List;
- Mode of Payment;
- Company payment account.

If a native ERPNext identity exists directly, it is used.

Migration compatibility can resolve old Ledgix identifiers through mapped custom fields.

Compatibility resolution does not transfer authority back to the old record.

---

## 4. Company locking and retry safety

Several current write paths lock the Company row as a lightweight serialization boundary for client-id/idempotency checks.

The goal is to reduce duplicate native transaction creation during concurrent retries.

This lock is not a business ledger.

Future idempotent endpoints should preserve equivalent safety when retry behavior matters.

---

## 5. Native pricing

Sales Invoice construction uses ERPNext pricing/item-detail logic.

The service intentionally avoids treating a raw Item Price lookup as complete price authority because it could bypass:

- validity dates;
- UOM conversion;
- Pricing Rule behavior;
- party context;
- native ERPNext item detail logic.

Ledgix may allow an authorized price override in selected product flows, but that override must be explicit and auditable.

---

## 6. Building a Sales Invoice

The service builds an unsaved ERPNext Sales Invoice using native masters and pricing.

Typical inputs include:

- Customer;
- item rows;
- Company;
- Selling Price List;
- sale channel;
- update_stock behavior;
- discount;
- client sale ID;
- exchange reference;
- checkout source.

Before submission, ERPNext-native monetary tax authority is applied.

Ledgix does not compute a second authoritative invoice total.

---

## 7. Creating a Sales Invoice

create_sales_invoice:

1. resolves Company;
2. locks Company;
3. checks client_sale_id for an existing active native invoice;
4. returns existing invoice on retry;
5. builds native Sales Invoice;
6. inserts;
7. optionally submits;
8. reloads.

The created Sales Invoice is the financial source of truth.

---

## 8. B2B stock behavior

The Sales Invoice may use update_stock where the selected workflow requires direct stock effect.

This is an explicit native ERPNext choice.

Do not assume all B2B invoices must update stock.

Do not simulate stock outside ERPNext if update_stock is false.

---

## 9. Compatibility result

api/selling_compat.py decorates native results for the Ledgix frontend.

It may expose:

- native invoice identifier;
- paid/remaining amount;
- payment state;
- ERPNext receivable/credit context;
- price override audit;
- print target.

The compatibility response is a UI contract.

The native Sales Invoice / Payment Entry remain authority.

---

## 10. Customer payment workflow

Current Ledgix payment posting creates an ERPNext Payment Entry.

Inputs include:

- Customer;
- Mode of Payment;
- amount;
- one or more Sales Invoice allocations;
- Company;
- client payment ID;
- optional reference number.

### Rules

- amount must be positive;
- Customer must resolve;
- Company must match;
- Sales Invoices must be submitted;
- allocations must belong to the same Customer/Company;
- allocation cannot exceed invoice positive outstanding;
- total allocated cannot exceed the supplied payment amount.

---

## 11. Allocated-payment requirement

The Ledgix cutover payment API requires at least one Sales Invoice allocation.

This keeps its workflow explicit and avoids silently creating an advance when the operator intended settlement.

For a true unapplied customer advance:

> use native ERPNext Payment Entry directly.

Do not create a fake invoice allocation merely to fit the Ledgix helper.

---

## 12. Mode of Payment account

The service resolves the Company default account for the selected Mode of Payment.

For customer receipt:

- paid_to is the resolved receipt account.

The Payment Entry remains the accounting record.

services/erpnext_payment_policy.py additionally validates Ledgix-marked Payment Entries against configured account policy.

This hook enforces product policy; it does not replace Payment Entry accounting.

---

## 13. Payment idempotency

client_payment_id can identify a previous active Payment Entry.

On retry, the service returns the existing native Payment Entry instead of deliberately creating another receipt/refund.

The same identifier must not be reused for unrelated transactions.

---

## 14. B2B checkout with tenders

The compatibility layer can orchestrate sale + payment behavior.

Important safety property:

- Sales Invoice creation and Payment Entry posting are independently idempotent.

If a retry occurs after invoice creation but before all intended payments are completed, the compatibility layer can continue against the original native invoice rather than create another invoice.

This is preferable to storing a custom Ledgix checkout ledger.

---

## 15. Payment state presentation

After payment posting, the compatibility result can present:

- paid amount;
- remaining amount;
- settled / partially settled / unpaid interpretation.

Those values are derived from current native invoice outstanding.

They are not a separate balance maintained by Ledgix.

---

## 16. Receivable model

get_customer_receivables reads ERPNext-native state.

It examines submitted Sales Invoices for the Customer/Company.

### Positive outstanding

Positive Sales Invoice outstanding contributes to trade receivable.

### Credit Note outstanding

Negative outstanding on submitted return Sales Invoices contributes invoice credit.

### Unallocated customer advance

Submitted Receive Payment Entries can contribute unallocated credit.

### Derived values

The service returns values such as:

- credit_limit;
- outstanding;
- invoice_credit;
- unallocated_credit;
- net_balance;
- credit_balance;
- available_credit;
- overdue;
- oldest_due_date;
- invoice list;
- credit-note list.

Authority is explicitly:

    ERPNext Sales Invoice + Payment Entry

---

## 17. Overdue calculation

Overdue is based on positive outstanding invoices whose due date is before the requested as-of date.

The service tracks the oldest due date among overdue balances.

Do not calculate overdue from historical Ledgix Sale dates.

---

## 18. Credit limit

The service resolves the Customer credit limit for the relevant Company.

Available credit is derived from the current native net balance.

Credit presentation is not a replacement for ERPNext credit policy.

---

## 19. Creating a B2B return / Credit Note

create_sales_return requires:

- submitted Sales Invoice;
- source not already a return;
- non-empty reason;
- requested return items.

The current service uses ERPNext:

    make_return_doc("Sales Invoice", source)

The returned document is a native Sales Invoice with is_return.

---

## 20. Exact source-row matching

Return requests are mapped to original Sales Invoice rows.

The service attempts to match by native source row identity.

Where fallback matching by Item is needed, it is accepted only when the match is unambiguous.

If every requested source row cannot be matched, the operation fails.

This protects against returning the wrong duplicate item row.

---

## 21. Return quantity

Requested return quantity is represented as a negative quantity on the native Credit Note.

The service also adjusts stock_qty using the original conversion factor.

The native return lifecycle owns financial reversal.

---

## 22. Return rate integrity

ERPNext's return mapper carries the original submitted line rate.

Ledgix deliberately does not overwrite that rate with a client-supplied return rate.

This rule protects historical transaction economics.

---

## 23. Return tax

After selecting return rows, the current service applies ERPNext-native monetary tax authority.

Ledgix does not calculate a separate return total.

---

## 24. Return metadata

Ledgix may store:

- client return ID;
- exchange reference;
- sale channel;
- checkout source;
- remarks/reason.

These fields support idempotency, UX and audit.

ERPNext return_against/source-row relationships remain the financial linkage.

---

## 25. Return idempotency

A client return ID can resolve to an existing active native return invoice.

The retry returns the original Credit Note.

Future changes must ensure an identifier cannot silently resolve to an unrelated source transaction.

---

## 26. Customer refund

A Credit Note does not automatically mean cash/bank has been returned.

refund_credit_note creates an ERPNext Payment Entry for the refund.

### Preconditions

- source must be a submitted Sales Invoice return;
- ERPNext payment mapper must resolve Payment Type Pay;
- refundable outstanding must be positive in absolute terms;
- requested refund cannot exceed refundable outstanding.

### Accounting

For refund:

- paid_from is the selected Mode of Payment account;
- Credit Note reference allocation is negative;
- Payment Entry is submitted.

The Payment Entry proves the actual refund transaction.

---

## 27. Refund idempotency

client_payment_id is also used for refund retry safety.

The same principles as customer receipts apply.

---

## 28. Exchange

Current exchange implementation creates:

1. native Credit Note;
2. native replacement Sales Invoice.

A required exchange reference links the two.

Flow:

    original Sales Invoice
      -> selected return rows
      -> Credit Note
      -> replacement items
      -> replacement Sales Invoice

The replacement invoice uses:

- source Customer unless overridden;
- same Company;
- selected/current Selling Price List;
- source sale channel where applicable.

No hidden net custom exchange transaction replaces the two native documents.

---

## 29. Exchange settlement

The exchange helper creates the two commercial documents.

Any difference in money owed/refunded must still be represented through native invoice/payment state.

Do not store an exchange "net balance" that competes with ERPNext outstanding.

---

## 30. Cancellation

Payment Entry cancellation or invoice cancellation must respect native ERPNext lifecycle.

The selling service contains explicit payment cancellation support for appropriate use cases.

Do not:

- delete submitted Payment Entries;
- change GL rows directly;
- cancel a source invoice after irreversible FBR state without satisfying FBR cancellation/correction safety.

---

## 31. FBR boundary

Submitted Sales Invoice is the B2B commercial source for FBR when applicable.

Relationship:

    Sales Invoice
      -> native tax/accounting
      -> immutable FBR snapshot
      -> readiness/payload
      -> controlled transport

Historical Ledgix Sale is not a valid new FBR source.

A Sales Invoice remains valid ERPNext financial evidence even when FBR transport is not active.

---

## 32. Print boundary

Current B2B print should target the native ERPNext Sales Invoice with the current Ledgix ERPNext print format.

Do not construct a current print route using historical Ledgix Sale.

---

## 33. Price override audit

Where the product allows a rate override, selling_compat records explicit override audit metadata on the native Sales Invoice.

Important behaviors include:

- override audit is tied to the native invoice;
- an idempotent retry must not rewrite the original authorized audit trail.

Do not allow override metadata to become a second pricing authority.

---

## 34. Error behavior

The selling/payment workflow should fail when:

- Company invalid;
- Customer/Item/Price List cannot be resolved;
- no effective safe price is found;
- Payment amount is non-positive;
- allocation exceeds outstanding;
- Customer/Company mismatch exists;
- Mode of Payment has no valid account;
- return source is invalid;
- return source row cannot be matched;
- refund exceeds refundable amount;
- exchange reference is missing.

Do not work around these errors through frozen Ledgix records.

---

## 35. Verification — sale

Check:

- Sales Invoice exists;
- docstatus correct;
- Customer and Company correct;
- pricing and tax native result correct;
- update_stock behavior intentional;
- client sale ID correct;
- outstanding reflects native state;
- FBR state if applicable.

---

## 36. Verification — payment

Check:

- submitted Payment Entry;
- Payment Type expected;
- correct party;
- correct Company;
- correct Mode of Payment/account;
- correct references;
- correct allocated amount;
- invoice outstanding changed.

---

## 37. Verification — return

Check:

- submitted return Sales Invoice;
- is_return enabled;
- return_against correct;
- source rows mapped correctly;
- negative quantity correct;
- source rate preserved;
- stock/accounting reversal correct;
- client return ID correct.

---

## 38. Verification — refund

Check:

- submitted Payment Entry;
- payment_type = Pay;
- Credit Note reference present;
- allocated amount negative as expected by native mapper;
- correct paid_from account;
- Credit Note outstanding changed.

---

## 39. Legacy boundaries

Do not create new:

- Ledgix Sale;
- Ledgix Sale Payment;
- Ledgix Payment;
- Ledgix Payment Allocation;
- Ledgix Sales Return.

Do not derive current receivable or settlement truth from these historical records.

Compatibility identifiers may still be read to map migrated data.

---

## 40. Primary source map

| Concern | Current source |
|---|---|
| Sales Invoice construction | services/erpnext_selling.py |
| Customer receipt | services/erpnext_selling.py |
| Refund | services/erpnext_selling.py |
| Credit Note | services/erpnext_selling.py |
| Exchange | services/erpnext_selling.py |
| Receivables | services/erpnext_selling.py |
| B2B compatibility API | api/selling_compat.py |
| Payment policy hook | services/erpnext_payment_policy.py |
| Monetary tax | services/erpnext_tax_authority.py |
| API override wiring | hooks.py |

---

## 41. Development rule

When extending sales/payments:

- use ERPNext Sales Invoice / Payment Entry;
- keep return linkage native;
- preserve idempotency;
- validate allocation/outstanding at transaction time;
- keep price override explicit/auditable;
- do not duplicate AR;
- do not reintroduce Ledgix Sale/Payment as current authority.

---

## 42. Summary

The current selling architecture is:

> **ERPNext Sales Invoice and Payment Entry own B2B sales, receivables, returns, refunds and settlement; Ledgix provides a stable product workflow, retry safety, metadata and compliance around those native documents without maintaining a second financial ledger.**
