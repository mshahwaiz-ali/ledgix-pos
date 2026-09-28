# Federal Tier-1 POS / IMS V1 Unresolved External Contracts

These are contracts Ledgix intentionally does not guess, not omissions from the proven implementation:

- item-level Debit serialization;
- unproven V1 wire fields for Extra Tax, FED Payable, and Sales Tax Withheld at Source;
- automatic external offline/batch upload;
- external closing, outage-reporting, and alert-message APIs;
- a Board/PRAL correction API;
- an undocumented digital-signature algorithm;
- a complete authoritative error catalogue and duplicate-USIN semantics;
- unsupported foreign-currency and ambiguous inclusive-tax discount semantics;
- client POSID/token issuance processes that depend on FBR/PRAL/provider evidence.

The runtime must block, use internal/manual evidence, or report these unresolved until authoritative evidence extends the contract. Digital Invoicing V1.2 is not authority for filling these gaps.
