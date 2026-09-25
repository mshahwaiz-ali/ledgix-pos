# Ledgix POS — FBR Setup and Operations

**Audience:** Client owner, Ledgix Admin, finance/tax lead, authorized manager  
**Current software baseline:** Ready for Client Certification  
**Important:** FBR Production is not automatically active after installation.

## 1. Purpose

This guide explains how a client should prepare and operate Ledgix FBR functionality.

It covers:

- seller identity;
- Integration Profile;
- product mappings;
- reference data;
- Sandbox setup;
- certification evidence;
- Production readiness;
- invoice status;
- Reconciliation Required;
- Known Offline;
- printing/corrections.

This guide does not replace legal/tax advice.

Use current FBR/provider instructions for client-specific legal requirements.

---

## 2. Understand the four FBR states

Do not confuse these statuses.

### Software Ready for Client Certification

The software is technically prepared for real client onboarding/certification.

Current baseline:

    YES

### Sandbox Certified

Real required Sandbox Validate/POST evidence has been completed and saved.

Default/new site:

    NO

### Production Ready

All Production prerequisites are green.

Default/new site:

    NO

### Production Active

The client has explicitly switched/armed the approved Production workflow.

Default/new site:

    NO

A site can be technically healthy while all three external states remain NO.

---

## 3. What creates the business invoice

The official business invoice is ERPNext:

- Sales Invoice; or
- POS Invoice.

Ledgix does not create a second FBR sales ledger.

FBR status is attached around the same ERPNext invoice.

---

## 4. Before FBR onboarding

Complete normal client readiness first.

Confirm:

- Business Profile enables FBR;
- Company configured;
- Chart of Accounts configured;
- selling/POS flow works;
- taxes work in ERPNext;
- named users/roles exist;
- no existing FBR Reconciliation Required invoice.

Do not start FBR certification on a business setup that is still unstable.

---

## 5. Seller legal identity

FBR seller identity comes from the ERPNext Company and Company Address.

Verify real legal details including, as required:

- business/legal name;
- NTN/CNIC/tax ID;
- registered address;
- province/state;
- other provider/FBR legal details.

Do not enter placeholder legal identity.

---

## 6. Company Address

Ensure the correct Company Address is linked and available.

FBR readiness can fail when:

- address missing;
- province missing;
- tax ID missing;
- legal identity incomplete.

Fix the real Company/Address master.

---

## 7. Open Tax & FBR Center

Authorized users can open:

    Tax & FBR Center

Use this as the main client-facing FBR workspace.

It is intended for Manager/Admin oversight and configuration.

---

## 8. Create/verify FBR Integration Profile

FBR Integration Profile is company-specific.

Verify:

- Company;
- enabled state;
- mode;
- submit trigger;
- provider/integrator information;
- Business Nature;
- Sector;
- software/POS registration where applicable;
- token status;
- Production arm state;
- Known Offline policy;
- reference-sync state.

Each Company must use its own proper profile.

---

## 9. Mode

Possible profile modes include:

- Disabled;
- Sandbox;
- Production;
- Paused.

During certification, use Sandbox.

Do not select Production just because the Production token has been received.

Production activation is the final stage after all gates pass.

---

## 10. Submit trigger

The profile can use an approved trigger mode such as:

- Manual;
- On Submit;
- Validate Only.

The trigger does not bypass readiness or certification rules.

---

## 11. Sandbox token

Enter the real Sandbox token securely through the supported configuration workflow.

Do not put the token in:

- Git;
- email screenshots;
- documentation;
- command history where avoidable;
- support tickets.

The interface should normally show only whether the token is configured.

---

## 12. Production token

Do not configure/use Production casually.

When obtained, store it securely in the Production token field.

A Production token alone does not make the system Production ready.

---

## 13. Business Nature and Sector

Configure the client's real FBR classifications as required by their onboarding/provider path.

Do not guess.

Retain the official/reference source used to confirm them where appropriate.

---

## 14. Software/POS registration

If the client's FBR/provider process requires software/POS registration:

- enter the real registration evidence;
- verify it before Production.

Do not fabricate a registration identifier.

---

## 15. Digital Invoicing logo

Production readiness can require the authoritative FBR Digital Invoicing System logo/evidence confirmed for the client/provider.

Attach the correct approved file.

Do not use a homemade lookalike as legal evidence.

---

## 16. Customer/buyer information

For FBR transactions, buyer information may be required.

Verify Customer data such as:

- registration type;
- NTN/CNIC;
- STRN where applicable;
- province;
- FBR address.

Use the actual Customer.

Do not use fake buyer identity to make a payload pass.

---

## 17. FBR Item Mapping

Each relevant ERPNext Item can require FBR mapping.

Review:

- HS Code;
- FBR UOM;
- Sale/Transaction Type;
- FBR rate/reference description;
- tax basis;
- SRO references where applicable;
- effective dates;
- Needs Review.

Mappings are compliance classification.

They are not the monetary tax calculator.

---

## 18. Needs Review

If an Item Mapping is marked:

    Needs Review

do not simply clear it to unblock the invoice.

Verify the correct official/provider evidence first.

---

## 19. FBR Tax Component Mapping

FBR Tax Component Mapping tells Ledgix what an ERPNext tax account represents for FBR.

Examples can include:

- Sales Tax Applicable;
- Sales Tax Withheld At Source;
- Extra Tax;
- Further Tax;
- FED Payable.

ERPNext still calculates/posts the monetary tax amount.

---

## 20. Official reference data

Use the supported reference-sync function in Tax & FBR Center.

Reference families can include:

- Province;
- Document Type;
- Transaction Type;
- UOM;
- Rate;
- HS-UOM;
- SRO data.

Do not manually invent official reference IDs.

---

## 21. Sandbox readiness

Before sending a real Sandbox transaction, readiness should confirm:

- client onboarding ready;
- FBR feature enabled;
- seller identity complete;
- Sandbox mode selected;
- Sandbox token configured;
- Production unarmed;
- transport available;
- no Reconciliation Required invoice.

This state is:

    Sandbox Ready

It is not yet:

    Sandbox Proven/Certified

---

## 22. Real Sandbox exercise

Real Sandbox certification requires authorized real Sandbox traffic.

Use only the approved controlled process.

The operator must know that the action is genuinely communicating with FBR Sandbox.

Do not run certification against arbitrary test invoices with bad data.

Use representative, payload-ready native invoices.

---

## 23. Required Sandbox proof

The current readiness model expects real successful evidence for:

### Sales Invoice

- successful Sandbox Validate;
- successful Sandbox POST.

### POS Invoice

Required when POS is enabled:

- successful Sandbox Validate;
- successful Sandbox POST.

### Return/note

Only require/execute when the client's actual FBR/provider return/note contract has been confirmed and is in scope.

---

## 24. What does not count as certification

The following do not prove Sandbox certification:

- unit test;
- local mock;
- fake HTTP response;
- screenshot without persisted matching log;
- manually typed scenario status;
- setting a checkbox to Complete.

Real persisted FBR Sandbox evidence is required.

---

## 25. Sandbox Certification record

Ledgix Sandbox Certification collects the required scenario proof.

The system derives evidence from matching Submission Logs.

Status should only become Complete when the required real evidence is present.

Do not manually try to edit proof fields.

---

## 26. Production readiness

Production-switch readiness requires much more than Sandbox token.

Current prerequisites include:

- required Sandbox proof complete;
- Sandbox Certification complete;
- Production token configured;
- authoritative DI logo configured where required;
- client release/readiness evidence;
- fresh verified backup;
- approved exact software release SHA;
- zero Reconciliation Required invoices;
- Production still unarmed during readiness review.

---

## 27. Production must remain unarmed during review

Before final activation, readiness expects Production posting to remain unarmed.

This proves the review is happening before the live switch.

Do not arm early "to test it."

---

## 28. Fresh backup before Production

FBR Production activation requires a fresh verified recovery point.

Current readiness uses a freshness window.

Coordinate with the technical administrator before activation.

Do not activate live FBR on a site that cannot be safely recovered.

---

## 29. Explicit Production authorization

Production activation is an explicit business/compliance decision.

It requires approval from the responsible authorized party.

Do not enable it automatically during:

- install;
- update;
- migration;
- readiness check;
- token entry.

---

## 30. First live transaction

When Production is finally activated:

- use an intentionally selected first transaction;
- observe it manually;
- retain the official response;
- verify FBR invoice/reference;
- verify QR/print;
- verify no duplicate submission.

Do not immediately send a large unattended batch.

---

## 31. FBR invoice status

An ERPNext sales invoice can show FBR state.

Important states include:

- Not Submitted;
- Ready;
- Submitted;
- Failed;
- Offline Pending;
- Reconciliation Required.

Review the exact status before taking action.

---

## 32. Submitted

Submitted means the accepted FBR workflow has recorded the official successful submission evidence.

Verify:

- FBR invoice number/reference;
- Submission Log;
- print/QR where applicable.

Do not manually type an FBR invoice number into the invoice.

---

## 33. Failed

Failed can mean the request was conclusively rejected or did not succeed.

Review:

- error code/message;
- Submission Log;
- data/readiness issue.

Correct the real issue.

Do not change the status directly.

---

## 34. Reconciliation Required

This is the most important stop state.

It means a Production request may have reached FBR but the local system cannot safely prove the final remote result.

When this appears:

> DO NOT RETRY THE FBR POST.

Reconcile externally with:

- FBR;
- PRAL/provider;
- official portal/evidence as appropriate.

---

## 35. Why repeated retry is dangerous

If FBR actually received the first POST but Ledgix lost the response, another POST can create duplicate legal submission risk.

That is why Ledgix deliberately blocks blind retry.

---

## 36. Release after reconciliation

If external investigation confirms:

> the invoice was NOT received by FBR

an authorized Admin/System Manager can use the supported reconciliation release workflow.

The exact confirmation used by the system is:

    CONFIRMED NOT RECEIVED BY FBR

This release does not itself send the invoice.

It only returns the invoice to a state where a controlled retry can later be considered.

---

## 37. Do not release if FBR received it

If FBR/provider confirms the invoice was received:

- do not use the "not received" confirmation;
- resolve the local status using the approved reconciliation/correction process.

Never use a false confirmation.

---

## 38. Known Offline

Known Offline is a controlled workflow for a confirmed offline condition allowed by the client's current provider/legal rule.

It is not a generic retry feature.

It must be configured only after the real offline rule/window is known.

---

## 39. Known Offline policy

Before using Known Offline, verify:

- FBR Production is legitimately configured;
- Sandbox certification complete;
- Production token exists;
- Production posting armed;
- offline policy is Operator Confirmed;
- approved upload window configured;
- no previous Production POST attempt exists for the invoice.

---

## 40. Declare Known Offline

Authorized action requires exact confirmation:

    DECLARE KNOWN OFFLINE

Also record the real reason.

This marks the invoice Offline Pending.

Declaration itself does not send an FBR POST.

---

## 41. Offline Pending

Offline Pending means:

- invoice was deliberately issued under the approved Known Offline process;
- it still needs controlled upload within the configured window.

Use the Tax & FBR Center queue to monitor deadlines.

---

## 42. Upload Offline invoice

Authorized controlled upload requires exact confirmation:

    UPLOAD OFFLINE INVOICE

Use only for an invoice still in Offline Pending and eligible under the configured policy.

---

## 43. Never use Known Offline after a POST attempt

If a Production POST was already attempted, Known Offline is not the recovery path.

If the result is uncertain:

    Reconciliation Required

must be used instead.

---

## 44. No automatic offline uploader

Ledgix does not automatically retry/upload offline invoices in the background.

This is intentional.

The operator must use the controlled workflow.

---

## 45. Returns / Credit Notes

ERPNext returns remain the business/accounting authority.

FBR outbound note semantics must only be used if the actual client's FBR/provider workflow has been proven.

Do not assume that every ERPNext Credit Note automatically has an approved FBR outbound note process.

---

## 46. Cancellation after FBR

Once FBR history exists, normal invoice cancellation can be blocked.

Use the approved:

- return;
- correction;
- note;
- reconciliation

workflow for the client's certified process.

Do not force-cancel/delete the record.

---

## 47. Printing

Before Production sign-off, verify the real print contains the required accepted information.

Depending on client/provider:

- seller identity;
- software/POS registration;
- FBR invoice/reference;
- QR;
- authoritative DI logo;
- return/offline wording.

Test actual A4/thermal output.

---

## 48. QR

Only genuine accepted FBR invoice evidence should be treated as official QR/reference proof.

Do not fabricate a QR to pass UAT.

---

## 49. Correction workflow

Post-submission correction rules can depend on official FBR/provider/legal procedure.

Retain required external evidence.

Do not mark a correction complete only because an internal Ledgix record exists.

---

## 50. Daily FBR monitoring

Authorized Manager/Admin should review:

- Failed;
- Offline Pending;
- Reconciliation Required;
- invoices missing expected FBR number;
- approaching offline upload deadline.

Do not wait until month-end to investigate exceptions.

---

## 51. FBR client checklist — before Sandbox

- [ ] normal business workflows work
- [ ] Company legal identity complete
- [ ] registered Company Address complete
- [ ] Business Nature/Sector confirmed
- [ ] provider/onboarding details confirmed
- [ ] Items mapped/reviewed
- [ ] ERPNext monetary tax correct
- [ ] official references synced/reviewed
- [ ] Sandbox mode selected
- [ ] real Sandbox token stored securely
- [ ] Production unarmed
- [ ] no Reconciliation Required invoices

---

## 52. FBR client checklist — before Production

- [ ] genuine Sandbox Sales Invoice Validate proof
- [ ] genuine Sandbox Sales Invoice POST proof
- [ ] POS proof if POS enabled
- [ ] return/note proof if actually required/in scope
- [ ] Sandbox Certification Complete from real evidence
- [ ] Production token secure
- [ ] DI logo confirmed/attached
- [ ] software/POS registration confirmed if required
- [ ] Known Offline rule/window confirmed if enabled
- [ ] final print/QR tested
- [ ] fresh verified backup
- [ ] approved exact release
- [ ] no Reconciliation Required invoices
- [ ] explicit Production authorization
- [ ] first live invoice observation planned

---

## 53. What never to do

Never:

- paste tokens into source code;
- fabricate seller/buyer identity;
- clear Needs Review without evidence;
- mark fake Sandbox success;
- arm Production before approval;
- blindly retry Reconciliation Required;
- use Known Offline after an attempted POST;
- invent an offline deadline;
- fabricate FBR invoice number/QR/logo;
- manually rewrite Submission Logs.

---

## 54. Current baseline reminder

At the software baseline used to create this documentation:

- Software Ready for Client Certification: YES;
- Sandbox Certified: NO;
- Production Ready: NO;
- Production Active: NO;
- general FBR network cutover: disabled;
- final audit real FBR/PRAL network calls: zero.

Your client site must earn its own certification/readiness evidence.

---

## 55. Summary

> **Complete real seller/mapping/reference data, prove the required native Sales/POS flows in genuine Sandbox, preserve that evidence, take a fresh verified backup, and activate Production only with explicit approval; if a live POST becomes ambiguous, stop and reconcile instead of retrying.**
