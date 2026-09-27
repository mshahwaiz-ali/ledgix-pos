# FBR V1 / Federal Tier-1 POS — Authoritative Source Inventory

**Status:** canonical research register for the `fbr_v1` redesign  
**Research cut-off:** 2026-09-27  
**Repository baseline audited:** `main@17f81554a0eeea85e9a6868719a9b76c0dcf4e36`

## 1. Source hierarchy

For this redesign, source priority is:

1. Sales Tax Act, Finance Acts and official Gazette notifications/SROs.
2. Current Sales Tax Rules / Chapter XIV published by FBR.
3. Current Sales Tax General Orders and official FBR POS / Digital Invoicing pages.
4. Current official FBR technical manuals/specifications.
5. Historical official FBR technical material, used only to understand grandfathered legacy POS/SDC installations.
6. Non-official mirrors, blogs, forum copies and vendor material are **not implementation authority**.

When two FBR pages conflict, the newer Gazette notification/rule controls the design. A stale FAQ or older booklet does not override a later SRO.

## 2. Current controlling Federal Sales Tax sources

### A. Current Chapter XIV — S.R.O. 69(I)/2025

Official consolidated Chapter XIV:
- https://download1.fbr.gov.pk/Docs/2025571554338577ChapterXIV.pdf

Official SRO:
- https://download1.fbr.gov.pk/SROs/2025129141598258SRO69%28I%292025.pdf

FBR POS legal-provisions index:
- https://www.fbr.gov.pk/pos-legal-provisions/163085/163086

**Authority:** current Federal Sales Tax Rules framework for licensing, issuance of electronic sales tax invoices and integration of registered persons.

Confirmed requirements relevant to Ledgix:

- Rule 150Q applies Chapter XIV to notified registered persons using integrated hardware/software.
- The proviso to 150Q(2) expressly says persons **already registered and POS-integrated with FBR are treated as integrated under the new rules**.
- Rule 150R requires outlet/POS/e-invoicing-machine information to be provided through the Board's system.
- Every supply must be made through an integrated outlet/POS/e-invoicing machine.
- The integrated software/machine must generate/receive/record/store invoice data, digitally sign the invoice, securely transmit data to FBR, receive the unique FBR invoice number, encrypt/preserve data, generate QR from the FBR invoice number, perform daily/weekly/monthly closing, and log adjustments/modifications/cancellations and system events.
- Annexure-C is to be auto-filled from electronic invoices.
- Exempt items are also to be invoiced through the integrated system.
- The invoice must include the particulars in rule 150R(13), including FBR invoice number, 7x7 mm verifiable QR, POS/e-invoicing software registration number, FBR logo, seller/recipient particulars, date/tax period, line description/quantity/value, sales-tax rate and amount, withheld/extra/further tax, FED where applicable, total discount, invoice reference, HS code, UOM and SRO/serial where applicable.
- For a retailer selling to the general public (other than manufacturer-cum-retailer/importer-cum-retailer), the rule contains a proviso concerning extra tax, further tax, FED and SRO particulars.
- Rule 150S requires a real-time verifiable electronic invoice for taxable supply/service, six-year electronic retention, and electronic debit/credit notes.
- Rule 150T requires storage sufficient to recreate the information as it existed at original transmission.
- Rule 150XA requires operational failures/disruption/tampering and inoperative systems to be reported within 24 hours.
- Rule 150XC requires invoices issued during software/internet/power failure to be identified as offline and uploaded within 24 hours **of restoration**.
- Rules 150XE–150XL establish the licensed-integrator framework; PRAL is a deemed licensed integrator and is required to provide free integration service on demand.

### B. S.R.O. 1413(I)/2025 — current registration/testing rollout

Official:
- https://download1.fbr.gov.pk/SROs/2025811681810559SRO1413.pdf

**Authority:** supersedes S.R.O. 709(I)/2025.

Confirmed:
- Sales-tax registered persons in the notification's categories were required to complete registration and testing through a licensed integrator or PRAL and issue electronic invoices by the staged 2025 dates.
- The final category covers registered persons other than the preceding categories with an electronic-invoice issuance date of 1 December 2025.

**Design consequence:** the current onboarding route for a new integration is not established by the old 2019 SDC slides. A new deployment must be treated as Chapter-XIV/licensed-integrator/current-DI unless FBR/PRAL gives client-specific authority for the legacy SDC route.

### C. S.R.O. 2071(I)/2025

Official:
- https://download1.fbr.gov.pk/SROs/202511413114246831SRO2071%281%29.pdf

Confirmed:
- Adds rule 150Q(3): retailers whose deductible withholding tax under sections 236G or 236H in the immediately preceding period exceeds Rs 100,000 or Rs 500,000 respectively must integrate for the relevant Tier-1 provision.

This is eligibility/compliance scope, **not** a machine protocol specification.

### D. Finance Act 2026 / current Tier-1 direction

FBR Finance Acts index:
- https://www.fbr.gov.pk/Categ/Finance-Acts/620

FBR Budget 2026-27 salient features:
- https://www.fbr.gov.pk/Budget2026-27/SalientFeatures/Salient-Feature.pdf

FBR Sales Tax Act index:
- https://www.fbr.gov.pk/categ/sales-tax-act/301

The official 2026 budget/act material records streamlining of the Tier-1 definition, including a Rs 200 million annual-turnover criterion, and electronic debit/credit-note adjustment. When implementing any Tier-1 eligibility screen, use the then-current consolidated Sales Tax Act rather than older website prose.

## 3. Current FBR operational pages

### POS legal provisions
https://www.fbr.gov.pk/pos-legal-provisions/163085/163086

This page currently links S.R.O. 69(I)/2025 Chapter XIV and S.R.O. 2071(I)/2025 alongside older POS material.

### POS technical assistance
https://fbr.gov.pk/pos-technical-assistance/163085/163087

Currently exposes:
- “Technical Documentation” -> legacy help.fbr.gov.pk article
- “Fiscalization Solution for Retailers” -> 2019 SDC presentation

The presence of these links shows that FBR still hosts the legacy material. It does **not** prove that a new 2026 taxpayer may self-onboard to the legacy SDC contract.

### POS integrated retailers
https://www.fbr.gov.pk/pos-integrated-retailers/163085/163089

As of the page titled “Upto 31-08-2026”, FBR reports ongoing POS integrations and Tier-1 branches. This confirms that the POS programme remains operational, but does not identify which transport generation a particular taxpayer is authorized to use.

### POS invoice verification
https://www.fbr.gov.pk/pos-invoice-verification/163085/163142

FBR says a customer can verify a Tier-1 integrated retailer invoice through Tax Asaan by entering the FBR invoice number or scanning the QR code, or by SMS to 9966.

## 4. Current Digital Invoicing sources — boundary with `fbr_v12`

FBR Digital Invoicing FAQ:
- https://www.fbr.gov.pk/faqs/173967/173969

Licensed integrators:
- https://www.fbr.gov.pk/list-of-license-interprator/173967/173971

Technical assistance:
- https://www.fbr.gov.pk/di-technical-assistance/173967/173970

User manual:
- https://www.fbr.gov.pk/di-technical-assistance/173967/174202

Important:
- The FAQ still references S.R.O. 709(I)/2025 for dates, while S.R.O. 1413(I)/2025 expressly superseded 709. Therefore the FAQ is useful explanatory material but is not the date authority.
- The FAQ confirms the licensed-integrator/PRAL model and says only a valid licensed integrator may configure a notified registered person's invoicing software for real-time transmission.
- The current DI technical protocol and sandbox-scenario model are the design authority for `fbr_v12`, not proof that the same endpoint/payload/token model applies to the legacy `fbr_v1` SDC path.

## 5. Historical Federal POS / SDC authority

### Fiscalization Solution for Retailers — 2019

Official FBR PDF:
- https://download1.fbr.gov.pk/Docs/2019121116123534681FiscSolution_03-12-2019.pdf

It documents the old architecture:

`POS -> FBR Sales/Fiscal Data Controller (SDC) -> FBR central servers`

Historical flow:
1. POS prepares the invoice.
2. POS sends invoice data to the SDC.
3. SDC formats/signs/encrypts/stores fiscal data and returns a fiscal invoice number.
4. POS generates QR based on the FBR invoice number and prints the receipt.
5. SDC synchronizes with FBR central servers.
6. For test integration: register for test, download/install SDC on the POS computer, call its REST service, receive the fiscal invoice number, print FBR logo/number/QR.
7. For production: register each POS, install SDC, and use a fiscal-enabled POS.

**Classification:** historical official technical evidence. It is valid for reconstructing the architecture of a grandfathered legacy installation, but it is not sufficient by itself to authorize a new 2026 deployment.

### Historical POS booklet / former Chapter XIV-AA

Official historical booklet:
- https://download1.fbr.gov.pk/Docs/2023919991847265Point-of-Sale%28POS%29-Booklet-%28LegalProvision%29-updated-18.09.2023.pdf

It describes the former EFD/SDC model and historical POS registration fields. The old Chapter XIV-AA framework was superseded/omitted when Chapter XIV was substituted in 2025. Treat its protocol/lifecycle rules as historical unless re-confirmed by a current FBR/PRAL technical packet.

## 6. S.R.O. 428(I)/2024 is a separate Income Tax Rules integration regime

Official:
- https://download1.fbr.gov.pk/SROs/2024322153582988SRO-428.pdf

This amends Chapter VIIA of the **Income Tax Rules, 2002** for online integration of prescribed businesses and uses EFD/SDC/POS concepts.

It is listed on the FBR POS legal page, but it is **not a substitute protocol specification for Federal Sales Tax Tier-1 Chapter XIV**. Ledgix must not merge the Income Tax Chapter-VIIA and Sales Tax Chapter-XIV contracts unless a source explicitly requires that for the client.

## 7. Machine-contract status for legacy Federal SDC

The following are **UNRESOLVED** for current Federal legacy/grandfathered operation because no current authoritative FBR document was recovered that safely establishes them:

- exact local SDC base URL and port;
- exact health endpoint;
- exact POST endpoint;
- exact request JSON field names/types;
- exact response JSON field names/types;
- exact authentication/access-code handling;
- exact test vs production endpoint/configuration mechanics;
- exact current SDC binary/package version;
- exact POS registration API;
- exact invoice-type enumeration;
- exact payment-mode enumeration;
- exact return/debit-note/credit-note/cancellation machine contract;
- exact SDC retry/idempotency semantics;
- exact current closing API and request/response schema;
- exact alert/event API;
- exact offline numbering and QR behavior before later upload;
- exact QR payload encoding beyond the current rule's statement that QR is based on the unique FBR invoice number.

An old mirror of the historical FBR help article exposes localhost REST examples, but it is **not accepted as canonical evidence** because the live FBR help article is presently unavailable to this audit and currentness cannot be proven.

## 8. Canonical regime decision

`fbr_v1` is to be designed as a **legacy/grandfathered Federal POS/SDC adapter**, not as “Tier-1 means V1”.

It may be enabled only when one of these is available:

1. evidence that the taxpayer/POS was already registered/integrated under the old FBR POS system and remains covered by the grandfathering proviso; or
2. a current FBR/PRAL instruction/technical pack explicitly directing the taxpayer to use the legacy SDC interface.

Otherwise:
- keep `fbr_v1` disabled/unresolved; and
- assess the taxpayer under the current Chapter XIV / licensed-integrator / Digital Invoicing route handled by `fbr_v12`.

## 9. Research rule for implementation

No endpoint, token scheme, JSON field, enum, offline behavior or closing operation may be added to `fbr_v1` merely because it appears in:
- the inherited `fbr_v12` code;
- a forum mirror;
- a vendor blog;
- a provincial/AJK specification; or
- an old FBR document whose current applicability is not established.

Unsupported requirements stay **UNRESOLVED** until authoritative evidence is attached to the plan.
