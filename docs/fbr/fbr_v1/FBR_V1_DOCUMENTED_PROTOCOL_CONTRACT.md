# FBR V1 — Documented Federal POS / IMS Protocol Contract

**Status:** CURRENT MACHINE-CONTRACT AUTHORITY
**Date:** 2026-09-27  
**Scope:** Federal FBR Tier-1 POS / IMS V1  
**Excluded:** Digital Invoicing V1.2

## 1. Source provenance

The current FBR POS Technical Assistance page exposes:
- **Technical Documentation**; and
- **Fiscalization Solution for Retailers**.

The technical-documentation link points to the FBR Knowledge Base article:
**Technical Specification for Data Sharing through Software Fiscal Component from TIER 1 Retailer with FBR**.

Because the live Knowledge Base is intermittently unavailable, the wire details are recovered from an archived rendering of that exact FBR article and cross-checked with the official fiscalization material and later PRAL fiscal-component documents.

That source chain defines the documented wire contract implemented in code. Legal/printing obligations and external onboarding/credential issuance are separate evidence layers; they do not authorize new wire fields.

## 2. Architecture

```text
ERP / POS
   |
   v
FBR Software Fiscal Component / IMS
   |
   +--> returns fiscal invoice number
   |
   v
FBR
```

The FBR technical material describes the fiscal component as residing on the POS computer, fiscalizing each invoice in real time and later/synchronously moving fiscal data to FBR.

For a cloud-hosted Ledgix deployment the eventual workstation/local-bridge topology is separate from the wire model itself.

## 3. Endpoints

### Local component health

```
GET http://localhost:8524/api/IMSFiscal/Get
```

### Local fiscalization

```
POST http://localhost:8524/api/IMSFiscal/GetInvoiceNumberByModel
Content-Type: application/json
```

### Cloud Sandbox

```
POST https://esp.fbr.gov.pk:8244/FBR/v1/api/Live/PostData
Authorization: Bearer <token>
Content-Type: application/json
```

### Cloud Production

```
POST https://gw.fbr.gov.pk/imsp/v1/api/Live/PostData
Authorization: Bearer <token>
Content-Type: application/json
```

Old sample code disabled certificate validation. Ledgix explicitly does **not** reproduce that insecure behavior.

## 4. Header fields

| Field | Type / behavior |
|---|---|
| InvoiceNumber | varchar(30), blank on request |
| POSID | bigint, compulsory, FBR POS registration number |
| USIN | varchar(50), compulsory, taxpayer/business own unique invoice number |
| RefUSIN | varchar(50), reference business invoice for note/return |
| DateTime | datetime, compulsory |
| BuyerName | varchar(150), optional |
| BuyerNTN | optional |
| BuyerCNIC | varchar(13), optional |
| BuyerPhoneNumber | varchar(20), optional |
| TotalSaleValue | double, compulsory |
| TotalQuantity | double, compulsory in Federal model/sample |
| TotalTaxCharged | double, compulsory |
| Discount | double, optional |
| FurtherTax | double, optional |
| TotalBillAmount | double, compulsory |
| PaymentMode | int, compulsory |
| InvoiceType | int, compulsory |
| Items | list, compulsory |

**Important:** ERPNext supplies all monetary values. The V1 protocol layer serializes and validates; it does not calculate tax.

## 5. PaymentMode

| Code | Meaning |
|---:|---|
| 1 | Cash |
| 2 | Card |
| 3 | Gift Voucher |
| 4 | Loyalty Card |
| 5 | Mixed |
| 6 | Cheque |

Use Mixed where the invoice has more than one payment method.

## 6. Header InvoiceType

| Code | Meaning |
|---:|---|
| 1 | New |
| 2 | Debit |
| 3 | Credit |

## 7. Item fields

| Field | Type / behavior |
|---|---|
| ItemCode | varchar(50), compulsory |
| ItemName | varchar(150), compulsory |
| Quantity | double, compulsory |
| PCTCode | varchar(8), compulsory |
| TaxRate | float, compulsory |
| SaleValue | double, compulsory, exclusive of tax/discount |
| Discount | double, optional |
| FurtherTax | double, optional |
| TaxCharged | double, compulsory |
| TotalAmount | double, compulsory |
| InvoiceType | int, compulsory |
| RefUSIN | reference USIN where applicable |

## 8. Item InvoiceType

The Federal Tier-1 item table documents:

| Code | Meaning |
|---:|---|
| 1 | New |
| 3 | Credit |
| 11 | Third Schedule New |
| 12 | Third Schedule Credit |

The same table does not list item-level Debit = 2 although the header supports Debit. The implementation fails closed on that single ambiguity.

## 9. Response

Federal KB example shape:

```json
{
  "FBRInvoiceNumber": "11000120181112000369",
  "Response": "Invoice received successfully",
  "Code": "100"
}
```

Later PRAL fiscal-component documents use `InvoiceNumber` for the generated fiscal number.

Ledgix parser rule:
- accept `FBRInvoiceNumber` or `InvoiceNumber`;
- require `Code == "100"`;
- require a non-empty returned fiscal number;
- never fabricate success.

## 10. Code mapping

```text
fbr_v1/protocol/constants.py  -> endpoints/enums
fbr_v1/protocol/models.py     -> exact request model
fbr_v1/protocol/response.py   -> fiscal response parser
fbr_v1/protocol/transport.py  -> local/cloud transport only
```

No module makes a network request on import.

## 11. External onboarding and legal/printing boundary

POSID/token issuance, authority/activation, device onboarding, retention policy, and provider approval are external inputs recorded by the readiness model. Printing obligations are rendered from ERPNext and returned fiscal metadata. Neither layer changes the wire schema above.

The parser accepts the authoritative returned fiscal number without imposing a new regex.

## 12. Deferred contract areas

Still separate:
- current POSID/token issuance workflow;
- exact item-level Debit behavior;
- full error-code catalogue;
- duplicate-USIN server behavior;
- separate offline upload API, if applicable;
- external daily/weekly/monthly closing API, if applicable;
- alternate QR encoding or undocumented signature algorithm;
- unproven Extra Tax/FED/withheld wire fields;
- external outage/alert and Board correction APIs;
- unsupported foreign-currency and inclusive-tax discount semantics.

These are not guessed.
