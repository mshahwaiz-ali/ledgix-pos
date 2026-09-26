# FBR V1 / Tier-1 POS — Source Inventory and Contract Boundary

Status: initial official-source inventory. This document defines what is proven before `fbr_v1` runtime redesign begins.

## Primary official FBR sources

1. FBR Point of Sale — Technical Assistance  
   https://www.fbr.gov.pk/pos-technical-assistance/163085/163087

2. FBR POS technical documentation entry / Knowledge Base  
   https://help.fbr.gov.pk/?p=6148

3. FBR Fiscalization Solution for Retailers  
   https://download1.fbr.gov.pk/Docs/2019121116123534681FiscSolution_03-12-2019.pdf

4. FBR Point of Sale — Legal Provisions  
   https://www.fbr.gov.pk/pos-legal-provisions/163085/163086

5. FBR Point of Sale Booklet — Legal Provision  
   https://download1.fbr.gov.pk/Docs/2023919991847265Point-of-Sale%28POS%29-Booklet-%28LegalProvision%29-updated-18.09.2023.pdf

6. FBR POS Invoice Verification  
   https://www.fbr.gov.pk/pos-invoice-verification/163085/163142

7. Historical federal EFD / SDC rule source (S.R.O. 1360(I)/2018)  
   https://download1.fbr.gov.pk/SROs/2018111217115439802SRO1360%28I%292018.pdf

8. AJK PRAL Tier-1 Software Fiscal Component technical specification — useful variant/reference only, not federal production authority  
   https://e.fbr.gov.pk/SOP/AJK/AJK_POS_Technical_Document.pdf

## Contract facts established from official POS material

### 1. Tier-1 POS fiscalization is SDC/EFD based

Official POS material describes an Electronic Fiscal Device / fiscalization architecture containing a Sales Data Controller (SDC) and one or more POS components.

The SDC receives transaction data from the POS, converts/records fiscal data, creates/signs fiscal evidence, returns a fiscal invoice number to the POS, preserves data securely and transmits fiscal data to FBR.

### 2. Test integration flow is POS -> SDC

The official Fiscalization Solution states the test flow as:

- register for test;
- download the FBR Fiscal Data Controller / SDC;
- install SDC on the same computer where the POS is installed;
- consume the RESTful web service;
- send invoice data to SDC;
- receive the Fiscal Invoice Number;
- print FBR Logo, Fiscal Number and QR Code on the receipt.

### 3. Production integration has per-POS registration

The official Fiscalization Solution states the production flow as:

- register each POS on the FBR web site;
- install SDC;
- update the existing POS to a fiscal-enabled POS.

The legal material also records POS registration/identity information such as POS registration number, business/branch identity, branch address, POS identification and registration date.

### 4. POS owns the customer-facing fiscal receipt

The POS is expected to print the fiscal invoice using the FBR-generated fiscal invoice number and QR code. FBR's current POS verification page tells customers to verify using the FBR invoice number or QR code via Tax Asaan; SMS verification is also documented.

### 5. The POS transaction contract is not just the V1.2 DI payload

The POS legal/booklet material describes transaction particulars including POS registration identity, sequential invoice identity, sale date/time, buyer information where recorded, item description, price exclusive of tax, quantity, tax rate, total sales value, discount, tax charged and payment mode.

The exact current machine-readable Federal request/response schema must still be retrieved from the authoritative POS technical documentation before implementation.

## Critical boundary: POS V1 vs Digital Invoicing V1.2

The existing `fbr_v12` application implements the Digital Invoicing V1.2 line.

The FBR POS/Tier-1 sources above describe a separate fiscalization model centered on POS registration and an SDC / Software Fiscal Component.

Therefore `fbr_v1` MUST NOT inherit any of the following merely because they exist in `fbr_v12`:

- V1.2 DI gateway endpoints;
- V1.2 DI payload shape;
- V1.2 reference-data APIs;
- V1.2 sandbox scenario model;
- V1.2 Production arming/certification semantics;
- V1.2 offline workflow;
- V1.2 return/note behavior.

Every such behavior must be replaced or retained only after explicit Tier-1 POS evidence.

## Still required before runtime cutover

The following are not yet considered proven for the federal Tier-1 implementation:

1. exact current Federal local SDC REST endpoint(s);
2. exact current cloud SDC endpoint(s), if cloud mode is supported;
3. exact request JSON schema and mandatory/optional fields;
4. exact response JSON schema and error codes;
5. authentication / POS Registration Number / Access Code handling;
6. test vs production configuration;
7. invoice-number and QR generation rules;
8. return, cancellation, adjustment and refund contract;
9. day/week/month closing/event-log API requirements;
10. current offline/failure behavior and reconciliation;
11. current print-receipt mandatory fields and dimensions;
12. current legal effect of later POS SROs and the 2025 electronic-invoicing rules on the target client.

## Implementation rule

Until the missing technical contract is obtained, `fbr_v1` remains a bootstrap source tree only. No real FBR request is authorized and no inherited V1.2 network endpoint is considered valid for V1.
