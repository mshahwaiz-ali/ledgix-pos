# FBR V1 Phase 0 — Documentation & Protocol Source Lock

**Status:** PASS FOR DEVELOPMENT  
**Date:** 2026-09-27  
**Real FBR network authorization:** NO  
**Production authorization:** NO

## 1. Corrected project direction

Ledgix is **building** the Federal FBR Tier-1 POS / IMS V1 integration from the FBR documentation.

The client does not need to provide an old POS computer in order for us to implement the documented protocol.

The existing `apps/fbr_v1` tree is only a bootstrap copy of `fbr_v12`; inherited DI V1.2 behavior has no protocol authority.

## 2. Source lock

Development authority:

1. current FBR POS Technical Assistance page;
2. official FBR Fiscalization Solution for Retailers;
3. FBR Knowledge Base article titled  
   **Technical Specification for Data Sharing through Software Fiscal Component from TIER 1 Retailer with FBR**;
4. archived rendering of that exact FBR KB article where the live KB is unavailable;
5. current Sales Tax legislation/rules for legal, printing, retention and operational obligations.

Later PRAL/AJK/PRA/BRA fiscal-component manuals can corroborate common IMS behavior, but they cannot silently add a Federal field or route.

## 3. Core V1 machine contract locked

### Local IMS / Software Fiscal Component

```
GET  http://localhost:8524/api/IMSFiscal/Get
POST http://localhost:8524/api/IMSFiscal/GetInvoiceNumberByModel
```

### Cloud V1

```
Sandbox:    https://esp.fbr.gov.pk:8244/FBR/v1/api/Live/PostData
Production: https://gw.fbr.gov.pk/imsp/v1/api/Live/PostData
Auth:       Bearer token
```

### Header model

- InvoiceNumber
- POSID
- USIN
- RefUSIN
- DateTime
- BuyerNTN
- BuyerCNIC
- BuyerName
- BuyerPhoneNumber
- TotalBillAmount
- TotalQuantity
- TotalSaleValue
- TotalTaxCharged
- Discount
- FurtherTax
- PaymentMode
- InvoiceType
- Items

### PaymentMode

1 Cash  
2 Card  
3 Gift Voucher  
4 Loyalty Card  
5 Mixed  
6 Cheque

### Header InvoiceType

1 New  
2 Debit  
3 Credit

### Item InvoiceType

1 New  
3 Credit  
11 Third Schedule New  
12 Third Schedule Credit

The Federal item table does not explicitly list item-level Debit = 2. Ledgix therefore leaves that exact item-level mapping fail-closed instead of guessing.

### Fiscal response

The Federal KB example uses:

- `Code = 100`
- `FBRInvoiceNumber`

Later PRAL fiscal components may return `InvoiceNumber`; the parser accepts either number key but never synthesizes a value.

## 4. Gate result

```text
DOCUMENTED CORE V1 CONTRACT          PASS
LOCAL IMS ROUTES                     PASS
CLOUD SANDBOX/PRODUCTION ROUTES      PASS
PAYMENT ENUM                         PASS
HEADER INVOICE TYPES                 PASS
SALE/CREDIT/THIRD-SCHEDULE ITEM TYPES PASS
REAL SANDBOX CALL                    NOT AUTHORIZED
REAL PRODUCTION CALL                 NOT AUTHORIZED
OFFLINE/CLOSING MACHINE API          UNRESOLVED/DEFERRED
```

This is enough to develop the V1 sale/credit fiscalization path using mocks.

## 5. Activation boundary

The taxpayer still needs the appropriate FBR/PRAL registration, POS identity and credentials before live use. That is a later setup/activation task, not a blocker for building the app.

## 6. Next

Phase 1B:
- derive POSID/USIN/date/buyer/payment/tax/item data from ERPNext;
- build the exact V1 payload;
- reconcile V1 totals against ERPNext;
- remain completely non-networked in tests.
