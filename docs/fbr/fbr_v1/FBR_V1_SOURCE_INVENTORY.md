# FBR V1 / Federal Tier-1 POS — Source Inventory

**Status:** canonical source register  
**Updated:** 2026-09-27

## 1. Source priority

1. current Sales Tax Act / Finance Acts / Gazette notifications and SROs;
2. current Sales Tax Rules / Chapter XIV;
3. current official FBR POS pages;
4. official FBR POS technical material;
5. archived rendering of an official FBR document when the live FBR Knowledge Base is unavailable;
6. later PRAL provincial fiscal-component material only for corroboration.

Vendor blogs/community code are never authority for adding a Federal field or rule.

## 2. Current FBR POS pages

### POS Technical Assistance
https://www.fbr.gov.pk/pos-technical-assistance/163085/163087

This remains the key current index and exposes:
- Technical Documentation;
- Fiscalization Solution for Retailers.

### POS Legal Provisions
https://www.fbr.gov.pk/pos-legal-provisions/163085/163086

Used for current legal obligations, not to infer JSON fields.

### POS Invoice Verification
https://www.fbr.gov.pk/pos-invoice-verification/163085/163142

Confirms consumer verification using FBR invoice number / QR through Tax Asaan and SMS.

### POS Integrated Retailers
https://www.fbr.gov.pk/pos-integrated-retailers/163085/163089

Confirms the Federal POS programme remains operational.

## 3. Federal technical sources

### Fiscalization Solution for Retailers

Official FBR:
https://download1.fbr.gov.pk/Docs/2019121116123534681FiscSolution_03-12-2019.pdf

Establishes:
- POS -> Software/Sales Data Controller -> FBR architecture;
- fiscal component installation;
- REST consumption;
- returned fiscal invoice number;
- QR/FBR number on receipt;
- Test and Production integration concept.

### FBR Knowledge Base technical specification

Title:
**Technical Specification for Data Sharing through Software Fiscal Component from TIER 1 Retailer with FBR**

Canonical live reference:
https://help.fbr.gov.pk/?p=6148

The live page is intermittently unavailable. An archived print/rendering of this exact FBR article is used to recover the machine contract.

Established Federal V1 contract:
- local health route;
- local fiscalization route;
- cloud Sandbox and Production routes;
- Bearer cloud authentication;
- POSID/USIN invoice schema;
- payment modes;
- invoice types;
- Third Schedule item types;
- success response.

The exact code contract is in `FBR_V1_DOCUMENTED_PROTOCOL_CONTRACT.md`.

## 4. Current legal layer

### Chapter XIV / S.R.O. 69(I)/2025
https://download1.fbr.gov.pk/Docs/2025571554338577ChapterXIV.pdf

Relevant current obligations include:
- integrated invoice generation/transmission;
- FBR invoice number;
- QR;
- POS/e-invoicing software registration identity;
- record preservation;
- electronic debit/credit notes;
- operational logs;
- offline/failure duties;
- daily/weekly/monthly closing obligations.

### S.R.O. 1413(I)/2025
https://download1.fbr.gov.pk/SROs/2025811681810559SRO1413.pdf

Controls current registration/testing rollout and onboarding obligations.

### S.R.O. 2071(I)/2025
https://download1.fbr.gov.pk/SROs/202511413114246831SRO2071%281%29.pdf

Adds current Tier-1 integration scope criteria.

## 5. Boundary with FBR V1.2 Digital Invoicing

`fbr_v12` owns DI V1.2 concepts such as:
- `di_data/v1/di/validateinvoicedata`;
- `di_data/v1/di/postinvoicedata`;
- DI reference APIs;
- DI sandbox scenario IDs;
- DI seller/buyer payload shape.

None of those may be copied into `fbr_v1` unless a V1 POS source separately documents the same behavior.

## 6. V1 protocol source lock

The following are now considered documented for development:

- `GET http://localhost:8524/api/IMSFiscal/Get`
- `POST http://localhost:8524/api/IMSFiscal/GetInvoiceNumberByModel`
- Sandbox cloud `https://esp.fbr.gov.pk:8244/FBR/v1/api/Live/PostData`
- Production cloud `https://gw.fbr.gov.pk/imsp/v1/api/Live/PostData`
- cloud Bearer token;
- exact invoice/item field model;
- PaymentMode 1..6;
- header InvoiceType 1/2/3;
- item InvoiceType 1/3/11/12;
- success Code 100;
- FBR fiscal invoice number response.

## 7. Deferred / unresolved

Do not guess:
- item-level Debit code semantics;
- current IMS installer/version;
- current credential/POSID issuance UI;
- complete error-code catalogue;
- duplicate-USIN behavior;
- separate offline upload API;
- external closing API;
- exact QR encoded payload.

Development continues with these paths fail-closed.
