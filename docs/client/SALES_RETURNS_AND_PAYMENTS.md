# Ledgix POS — Sales, Returns and Payments

**Audience:** Sales staff, managers, accounts staff  
**Applies to:** Invoice + FBR Only, B2B, Mixed and any profile using Sales Invoice

## 1. Purpose

This guide explains non-retail/B2B sales and settlement.

Current official records are:

- ERPNext Sales Invoice;
- ERPNext Payment Entry;
- ERPNext return Sales Invoice / Credit Note.

Use these records for all current business activity.

---

## 2. Create a Sales Invoice

Use the Ledgix/ERPNext Sales Invoice workflow for invoice-led sales.

Before creating the invoice, verify:

- Customer;
- Items/services;
- quantities;
- prices;
- taxes;
- Company;
- due date/terms;
- stock behavior where applicable.

---

## 3. Customer

Choose the real Customer.

For B2B customers, maintain:

- legal/business name;
- address;
- tax information;
- credit information;
- FBR buyer details where required.

Do not use the generic walk-in customer for a business customer that needs its own legal invoice.

---

## 4. Item/service

Use ERPNext Items.

Services can be non-stock Items.

Physical goods can be stock Items.

Make sure UOM, price and tax treatment are correct before posting.

---

## 5. Price

Sales Invoice pricing follows ERPNext:

- Selling Price List;
- Item Price;
- Pricing Rule;
- Customer/UOM/date context.

If the price is wrong, correct the pricing setup or use an authorized override where the business allows it.

---

## 6. Tax

ERPNext calculates monetary tax.

Review:

- taxable amount;
- tax rows;
- grand total.

FBR classification is separate from ERPNext monetary tax.

---

## 7. Submit invoice

Once correct, submit the Sales Invoice.

After submission, the invoice becomes official business/accounting evidence.

Do not edit the accounting result through a historical Ledgix sale.

---

## 8. Stock effect

Some Sales Invoices can update stock directly.

Others may follow a separate delivery workflow.

The client implementation should use the agreed process consistently.

Do not post a manual stock adjustment just because you are unsure whether the invoice already moved stock.

---

## 9. Customer outstanding

ERPNext tracks current outstanding.

Use the invoice/receivable reports to see:

- grand total;
- paid amount;
- outstanding;
- overdue.

Do not maintain a separate spreadsheet as the official receivable balance.

---

## 10. Receive a customer payment

For a payment against invoice(s):

1. select Customer;
2. choose Mode of Payment;
3. enter amount;
4. allocate to the submitted Sales Invoice(s);
5. verify allocation;
6. submit Payment Entry.

The Payment Entry is the official receipt transaction.

---

## 11. Allocation rules

A payment allocation:

- must belong to the same Customer;
- must belong to the same Company;
- cannot exceed the invoice's current positive outstanding.

If the system rejects the allocation, check outstanding and invoice identity before changing anything.

---

## 12. Partial payment

You can receive less than the total invoice outstanding.

Example:

    Invoice outstanding: 10,000
    Payment received: 4,000
    New outstanding: 6,000

Use a normal Payment Entry allocation.

---

## 13. Full payment

When the invoice is fully settled, outstanding becomes zero.

Verify the invoice state after Payment Entry submission.

---

## 14. Multiple invoice allocation

A Payment Entry can allocate one receipt across multiple invoices when supported by the workflow.

Check total allocated amount carefully.

Do not allocate one customer's money to another customer's invoice.

---

## 15. Payment reference

For bank/card/transfer payment, enter the real reference where required.

This improves audit/reconciliation.

Do not enter fake references.

---

## 16. Unapplied advance

If a customer pays an advance that is not yet allocated to an invoice, use the native ERPNext advance/payment workflow.

Do not create a fake invoice just to attach the payment.

---

## 17. Customer statement

Use Customer Statement / ERPNext receivable reports to review:

- invoices;
- payments;
- Credit Notes;
- balance.

The report comes from ERPNext financial records.

---

## 18. Overdue

An invoice becomes overdue when:

- it still has positive outstanding;
- its due date has passed.

Use Accounts Receivable/customer statement to follow up.

---

## 19. Create a sales return / Credit Note

For a B2B return:

1. locate original submitted Sales Invoice;
2. choose the original row(s);
3. enter return quantities;
4. enter reason;
5. submit the return.

The result is a native ERPNext Credit Note (return Sales Invoice).

---

## 20. Return must reference the original invoice

Never create an unrelated negative invoice simply to represent the return.

The return should remain linked to the original sale.

This preserves:

- accounting;
- source price;
- stock;
- audit trail.

---

## 21. Return price

The return uses the original submitted line rate.

Do not replace it with today's current price.

---

## 22. Partial return

You can return part of the original quantity.

Example:

    Original: 10 units
    Return: 3 units

The Credit Note reflects the returned quantity only.

---

## 23. Credit Note vs cash refund

A Credit Note reverses/reduces the sale.

It does not automatically prove money was refunded.

If cash/bank must be returned, create the actual refund Payment Entry.

---

## 24. Refund customer

For an approved refundable Credit Note:

1. choose refund Mode of Payment;
2. enter refund amount;
3. link the Credit Note;
4. submit the ERPNext Payment Entry.

The payment type is a Pay/refund transaction.

---

## 25. Refund limit

Do not refund more than the Credit Note's refundable outstanding.

If the system blocks the amount, verify previous refunds/allocations.

---

## 26. Exchange

An exchange should be represented as:

1. Credit Note for the returned goods;
2. replacement Sales Invoice for new goods.

Any difference remains visible in the normal invoice/payment balance.

Do not use an undocumented manual net adjustment.

---

## 27. FBR on Sales Invoice

When FBR applies, the submitted Sales Invoice is the commercial source.

FBR processing is attached to the same invoice.

Do not create a second custom sale/FBR record for the same transaction.

---

## 28. FBR returns/notes

Return/note behavior must follow the client's actually certified FBR/provider workflow.

Until that is proven, do not assume every internal Credit Note has a certified outbound FBR note protocol.

---

## 29. Cancel an invoice

Cancellation of a submitted invoice is a controlled accounting action.

If the invoice has FBR history or special status, cancellation can be blocked.

Use the correct return/correction process instead.

Do not delete submitted records.

---

## 30. Reconciliation Required

If a Sales Invoice shows FBR Reconciliation Required:

- do not resubmit repeatedly;
- escalate to Ledgix Admin/System Manager;
- the FBR outcome must be reconciled externally.

The business invoice remains an ERPNext financial record.

---

## 31. Common mistake: payment looks missing

Check:

- Payment Entry is submitted;
- correct Customer;
- correct Company;
- correct Sales Invoice reference;
- allocated amount;
- invoice outstanding.

Do not create another receipt until you confirm whether the first payment posted.

---

## 32. Common mistake: outstanding is wrong

Inspect:

- invoice total;
- Payment Entries;
- Credit Notes;
- prior cancellations;
- GL/customer ledger.

Use ERPNext as authority.

---

## 33. Common mistake: return not reducing stock

Check:

- whether original invoice updated stock;
- native return configuration;
- return document;
- Stock Ledger.

Do not create a separate stock correction unless there is a genuine physical-count issue.

---

## 34. Daily/weekly review

Managers/accounts staff should review:

- unpaid invoices;
- overdue invoices;
- customer credit;
- unallocated advances;
- Credit Notes;
- refunds;
- unusual price overrides;
- failed/cancelled transactions.

---

## 35. Sales checklist

Before submission:

- [ ] correct Customer
- [ ] correct Items/services
- [ ] quantity
- [ ] rate
- [ ] discount
- [ ] tax
- [ ] due date
- [ ] stock behavior
- [ ] FBR buyer details if needed

After submission:

- [ ] print correct
- [ ] outstanding correct
- [ ] Payment Entry posted where paid
- [ ] FBR status reviewed if enabled

---

## 36. Return checklist

- [ ] original invoice selected
- [ ] exact original row selected
- [ ] return quantity correct
- [ ] reason recorded
- [ ] original rate preserved
- [ ] Credit Note submitted
- [ ] stock/accounting effect reviewed
- [ ] refund posted separately if money returned
- [ ] FBR treatment reviewed if applicable

---

## 37. What not to do

Do not:

- create current Ledgix Sale/Payment records manually;
- edit submitted invoice totals to make balances match;
- allocate payment across different Customers/Companies;
- fake refund without Payment Entry;
- use today's price for historical return;
- repeatedly retry ambiguous FBR submission;
- directly edit GL.

---

## 38. Summary

> **Use Sales Invoice for the sale, Payment Entry for money received or refunded, and a native return/Credit Note linked to the original invoice for returns; ERPNext outstanding and accounting remain the official customer balance.**
