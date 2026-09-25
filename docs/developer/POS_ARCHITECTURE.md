# Ledgix POS — POS Architecture and Lifecycle

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Primary implementation:** services/erpnext_pos.py + api/pos_compat.py

## 1. Purpose

This document describes the current retail POS implementation behind the Ledgix POS screen.

The retained Ledgix POS experience is intentionally not a custom accounting engine.

Current authority is:

- ERPNext POS Profile;
- ERPNext POS Opening Entry;
- ERPNext Item / Customer / Price List;
- ERPNext stock state;
- ERPNext POS Invoice;
- native POS Invoice payment rows;
- ERPNext POS Closing Entry;
- standard ERPNext POS consolidation/accounting.

Historical Ledgix Sale, Payment, POS Shift and POS Hold records are not current POS transaction authority.

---

## 2. Runtime boundary

The stable frontend/API contract is primarily exposed through:

    api/pos_compat.py

The transaction/service implementation is primarily:

    services/erpnext_pos.py

hooks.py redirects historical POS V2 and shift RPC names to the compatibility layer.

This allows the product UI contract to remain stable without preserving the former Ledgix transaction engine.

---

## 3. POS lifecycle overview

    user
      -> Ledgix POS page
      -> load ERPNext POS Profile
      -> require active POS Opening Entry
      -> browse ERPNext Items / prices / stock
      -> preview
      -> tender validation
      -> submit ERPNext POS Invoice
      -> optional native return
      -> close ERPNext POS shift
      -> standard ERPNext consolidation

Each stage is described below.

---

## 4. POS Profile resolution

The service resolves the applicable ERPNext POS Profile for:

- active Company;
- current or explicitly supplied User.

If a specific POS Profile is supplied, it must belong to the same Company and be enabled.

If no valid profile is available, the service fails.

A Ledgix-only profile is not created as a fallback.

### Profile-derived behavior

The POS Profile influences:

- Warehouse;
- Selling Price List;
- default Customer;
- Modes of Payment;
- partial payment behavior;
- payment/change policy;
- native ERPNext POS behavior.

---

## 5. Warehouse resolution

The POS service uses the POS Profile warehouse where configured.

Warehouse validation delegates to the ERPNext-native buying/inventory service.

A valid warehouse must be:

- a real ERPNext Warehouse;
- active;
- non-group;
- part of the relevant Company.

If the profile does not provide a usable warehouse, current Ledgix logic resolves a valid Company leaf Warehouse through the native stock helper.

The POS must not invent a warehouse identifier.

---

## 6. Shift authority

### 6.1 Opening

Current shift authority is ERPNext POS Opening Entry.

Flow:

    open shift action
      -> resolve POS Profile
      -> check active opening
      -> create POS Opening Entry if none
      -> append native opening balances
      -> submit

If an active opening already exists for the user/profile, it is reused.

### 6.2 Opening cash

Opening cash is represented in POS Opening Entry balance details.

The service derives cash modes from the POS Profile.

If opening cash is supplied but the profile has no Cash mode, the operation fails.

### 6.3 No Ledgix POS Shift

Do not create a current Ledgix POS Shift.

That DocType is historical/frozen.

---

## 7. Shift status

shift_info derives current state from:

- active POS Opening Entry;
- unclosed/unconsolidated native POS Invoices;
- configured payment modes;
- opening cash;
- tender totals.

It reports an operational read model.

It is not a stored parallel shift ledger.

The service can calculate values such as:

- opening cash;
- cash sales;
- expected cash;
- active opening identifier;
- native invoice set.

---

## 8. Catalog loading

The POS boot/search path reads current ERPNext data.

Important sources include:

- Item;
- Item Group;
- Item Barcode;
- Price List / ERPNext pricing;
- Bin / stock state;
- Item tracking configuration.

### Tracking type

Ledgix may present a tracking type to the UI based on ERPNext Item configuration.

The authoritative tracking model remains ERPNext Batch / Serial No / related bundle behavior.

---

## 9. Customer context

The POS service resolves a native ERPNext Customer.

It may use:

- explicitly selected Customer;
- POS Profile/default customer behavior;
- compatibility mapping from historical identifiers.

The returned customer context is a presentation/read model.

Customer receivables and credit truth remain native ERPNext transaction state.

---

## 10. Price authority

Current POS pricing is ERPNext-native.

The POS service uses the selling service/native ERPNext item detail path.

Do not replace this with a raw Item Price lookup as the sole authority because that can bypass:

- effective dates;
- UOM behavior;
- pricing rules;
- customer context;
- native ERPNext pricing semantics.

### Manager rate override

Where the current product allows a rate override, it is explicit and audited through Ledgix metadata.

An override must not silently become a second pricing engine.

---

## 11. Preview

preview_checkout builds the intended native POS Invoice state without submitting it.

Preview should be used to show:

- item/rate/tax outcome;
- totals;
- customer context;
- payment requirement.

Preview is non-authoritative until the actual native document is submitted.

---

## 12. Sale idempotency

complete_sale supports a client sale identifier.

Before creating a new sale, the service:

- locks the Company transaction context;
- checks for an existing active native POS Invoice with that client identifier;
- returns the existing invoice on a retry.

This prevents an intentional duplicate native sale when a client repeats the request.

The identifier is retry metadata, not a transaction ledger.

---

## 13. Tender validation

The POS service normalizes requested tenders against the POS Profile.

For each tender:

1. resolve ERPNext Mode of Payment;
2. require that mode to be configured on the POS Profile;
3. ignore non-positive rows;
4. validate required reference number;
5. resolve configured account/type/default/change policy.

At least one positive payment row is required.

---

## 14. Partial payment

The service compares total tendered value with the native invoice total.

If tendered is less than the invoice total:

- checkout is rejected unless POS Profile permits partial payment.

This rule belongs to the native profile/product policy.

It is not represented in a parallel Ledgix balance.

---

## 15. Over-tender / change

If tendered exceeds invoice total:

- a compatible Cash payment mode must allow change.

The service sets the account used for change based on the eligible cash tender.

Over-tender is not accepted through an arbitrary non-cash mode.

---

## 16. Completing a retail sale

Current flow:

    require active opening
      -> lock Company
      -> idempotency check
      -> build native POS Invoice
      -> normalize tenders
      -> replace native payments rows
      -> set change account where needed
      -> insert
      -> submit
      -> reload
      -> return native result

The authoritative result is the submitted ERPNext POS Invoice.

No current Ledgix Sale or Ledgix Payment is created to mirror it.

---

## 17. Split payments

Split tender is represented by multiple native payment child rows.

Example:

    Cash 1000
    Card 2000

The payment child model is the native ERPNext payment child used by POS Invoice.

The Ledgix screen should render and submit those rows through the compatibility/service layer.

Do not create a separate split-payment table outside the native invoice for the same tender.

---

## 18. Print target

api/pos_compat.py decorates the completed native POS result with the ERPNext-native print target.

Current retail print authority is:

- native POS Invoice;
- Ledgix ERPNext POS Receipt print format.

The print route must not point to historical Ledgix Sale for current retail checkout.

---

## 19. Hold architecture

### 19.1 Retail hold

A held retail cart is a draft ERPNext POS Invoice carrying Ledgix hold metadata.

### 19.2 B2B hold

A held B2B cart is a draft ERPNext Sales Invoice carrying Ledgix hold metadata.

### 19.3 Metadata role

Ledgix metadata can carry:

- hold ID;
- hold status;
- request/cart data;
- source/channel information.

The draft native invoice owns the commercial values.

### 19.4 Resume

Resume resolves the draft by hold identifier and reconstructs the Ledgix cart/context.

Resume is a draft workflow, not a new transaction.

### 19.5 Cancel hold

Cancelling a hold marks the draft/hold metadata as cancelled according to the implemented workflow.

Because the document is not submitted, this is not a posted accounting reversal.

### 19.6 No current Ledgix POS Hold ledger

Do not reactivate Ledgix POS Hold as the primary hold authority.

---

## 20. Retail return source validation

The return service requires a submitted ERPNext POS Invoice.

The source must be:

- submitted;
- non-return;
- valid current native source.

A missing/invalid source fails closed.

---

## 21. Retail return idempotency

client_return_id may identify a previous native return.

If an existing active POS Invoice has the same identifier:

- it must be a return;
- it must point to the same original POS Invoice.

Otherwise the retry identifier is rejected as belonging to another transaction.

---

## 22. Active-shift requirement for returns

The current service requires an active ERPNext POS Opening Entry before posting a retail return.

This keeps return activity within the native POS shift workflow.

Do not bypass this by creating a historical Ledgix return record.

---

## 23. Return quantity selection

The request selects original source rows/items and positive quantities.

ERPNext's POS return mapper creates the native return candidate.

Ledgix then:

- selects only requested source rows;
- makes quantity negative;
- checks requested quantity does not exceed ERPNext returnable quantity;
- requires at least one matching row.

The native return mechanism remains responsible for source linkage/accounting behavior.

---

## 24. Return pricing

The return mapper carries original native sale economics.

The current service does not accept an arbitrary client-supplied replacement rate as the return authority.

This prevents a return request from rewriting the original submitted transaction economics.

---

## 25. Return metadata

The current return stores Ledgix-specific metadata such as:

- Retail sale channel;
- checkout source;
- client return identifier;
- return reason.

This metadata supports UX/audit.

It does not replace ERPNext's return_against/native source linkage.

---

## 26. Closing architecture

Current closing uses ERPNext's:

    make_closing_entry_from_opening

The service:

1. resolves current user/profile;
2. requires active opening;
3. validates optional requested shift ID against active opening;
4. builds native closing;
5. stores Ledgix closing notes;
6. fills reconciliation closing amounts;
7. inserts;
8. submits;
9. reloads closing/opening.

The resulting POS Closing Entry is authoritative.

---

## 27. Cash closing amount

The operator supplies actual cash.

The service assigns that amount to the first applicable configured Cash mode.

Other cash/payment reconciliation rows use expected values under the current implementation.

This is an explicit POS reconciliation behavior.

It should not be duplicated in a Ledgix shift ledger.

---

## 28. Consolidation

ERPNext standard POS closing/consolidation behavior remains authoritative.

The consolidated Sales Invoice produced by native POS closing is an accounting consolidation result.

It must not become a second FBR commercial source for the original POS Invoice.

Current reporting logic also accounts for the ERPNext v15 POS consolidation model when deriving native cost/profit.

---

## 29. POS + FBR boundary

The submitted POS Invoice is the commercial FBR source where FBR applies.

Relationship:

    POS Invoice submitted
      -> immutable Ledgix FBR snapshot
      -> readiness/payload
      -> controlled transport

The consolidated Sales Invoice is excluded from acting as a duplicate FBR source.

POS checkout must remain valid ERPNext business state even if FBR is:

- Disabled;
- pending certification;
- Offline Pending;
- Reconciliation Required.

---

## 30. POS permissions

The Ledgix POS Page is exposed according to current Page roles/product-shell policy.

Server-side APIs must still enforce appropriate role access.

Business Profile visibility is not sufficient authorization.

Current role intent includes Ledgix Cashier and higher operational roles, subject to server permissions and native ERPNext access.

---

## 31. Failure behavior

The POS should fail rather than fabricate state when:

- Company is invalid;
- no active POS Profile exists;
- warehouse is invalid;
- no active opening exists for checkout/return;
- price cannot be resolved safely;
- tender mode is not configured;
- required payment reference is missing;
- payment does not meet profile policy;
- return source is invalid;
- return quantity exceeds returnable quantity.

Do not "fix" these failures by writing legacy business rows.

---

## 32. Verification after checkout

Verify:

- submitted POS Invoice exists;
- correct Company;
- correct POS Profile;
- correct Customer;
- correct item rows/rates;
- correct Warehouse/stock effect;
- correct native payment rows;
- correct change account where applicable;
- correct client sale ID;
- correct print target;
- correct FBR state only if enabled.

---

## 33. Verification after return

Verify:

- submitted return POS Invoice;
- native source relationship;
- expected negative quantities;
- no over-return;
- stock/accounting reversal;
- return reason metadata;
- client return idempotency;
- print target;
- FBR note/correction state only where that workflow is certified/in scope.

---

## 34. Verification after closing

Verify:

- POS Closing Entry submitted;
- source opening matches;
- opening lifecycle is closed according to ERPNext;
- payment reconciliation reflects intended actual/expected amounts;
- unclosed managed POS invoices are handled;
- native consolidation completes as expected;
- no duplicate active opening exists for same user/profile.

---

## 35. Legacy POS boundaries

The following must not be current authority:

- Ledgix Sale;
- Ledgix Sale Payment;
- Ledgix Payment;
- Ledgix POS Shift;
- Ledgix POS Hold;
- Ledgix Stock Movement;
- Ledgix Stock Lot;
- Ledgix Stock Serial.

hooks.py redirects active old RPC contracts into the current compatibility layer.

Physical source/history does not authorize new writes.

---

## 36. Primary source map

| Concern | Current source |
|---|---|
| POS UI contract | api/pos_compat.py |
| POS transaction engine | services/erpnext_pos.py |
| Company/customer/item/pricing helpers | services/erpnext_selling.py |
| Warehouse/stock helpers | services/erpnext_buying_inventory.py |
| Monetary tax | services/erpnext_tax_authority.py |
| POS RPC override wiring | hooks.py |
| ERPNext POS extension fields/setup | setup/erpnext_phase8_extensions.py |
| Print bridge | api/printing.py + current print formats |
| Reporting | services/erpnext_reporting.py |

---

## 37. Development rule

A future POS enhancement should normally extend:

- the Ledgix POS page for UX;
- api/pos_compat.py for stable RPC boundary;
- services/erpnext_pos.py for reusable POS behavior;
- ERPNext-native documents for transaction truth.

Do not solve a POS feature request by recreating a custom sale, payment, shift or stock ledger.

---

## 38. Summary

The current Ledgix POS architecture is:

> **a fast Ledgix retail interface over ERPNext POS Profile, Opening/Closing Entries, POS Invoice, native payment rows and native stock/accounting behavior, with compatibility and FBR metadata layered around the same ERPNext transaction rather than a second POS engine.**
