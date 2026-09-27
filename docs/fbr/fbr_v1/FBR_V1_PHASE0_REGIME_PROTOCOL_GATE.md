# FBR V1 Phase 0 — Legacy Regime & Protocol Evidence Gate

**Status:** BLOCKED ON CLIENT/FBR EVIDENCE  
**Audit date:** 2026-09-27  
**Repository baseline:** `main@8b6b73a112e37af18b6ba8a984e72b9154f25635`  
**Runtime changes authorized:** none

## 1. Purpose

Phase 0 decides one question before any legacy SDC code is written:

> Is this taxpayer/POS actually authorized to use the grandfathered Federal POS/SDC integration, and what exact current machine contract applies to it?

Being a Tier-1 retailer alone is **not** sufficient evidence for selecting the old SDC protocol.

## 2. Repository evidence result

A full current-tree and Git-history inspection found no authoritative legacy SDC implementation in Ledgix.

### Current `apps/fbr_v1`
It is the documented bootstrap clone of `fbr_v12` and therefore contains DI V1.2 transport/reference/sandbox behavior rather than a legacy SDC implementation.

### Historical `apps/ledgix_saas`
The pre-redesign FBR client history was also inspected.

At historical revisions, including the July/August 2026 implementation, Ledgix was already using:
- `gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata[_sb]`;
- `gw.fbr.gov.pk/di_data/v1/di/postinvoicedata[_sb]`;
- Bearer tokens;
- Sandbox/Production DI modes.

Therefore Ledgix Git history cannot be used as evidence of a Federal legacy SDC contract.

## 3. Official-source result

FBR's current POS Technical Assistance page still links:
- the legacy POS “Technical Documentation” article at `help.fbr.gov.pk/?p=6148`; and
- the official 2019 Fiscalization Solution for Retailers.

The official 2019 FBR fiscalization document establishes the historical architecture and still links the historical SDC package:
- POS -> FBR Software/Sales Data Controller -> FBR;
- local SDC installation;
- REST consumption;
- FBR fiscal invoice number returned to POS;
- QR/FBR number printed by POS;
- automatic synchronization to FBR.

However, the live FBR Knowledge Base article does not currently expose its machine-contract contents reliably to this audit.

A third-party archived copy of that old FBR article exposes specific localhost routes and old installer behavior. It is **forensic reference only** and is not accepted as implementation authority.

No endpoint, port, JSON schema or access-code behavior from that mirror may enter production V1 code until confirmed by current FBR/PRAL or the client's authorized installed package.

## 4. Gate 0 evidence required from the client

At least one authority path must be proven.

### Path A — grandfathered existing POS

Collect evidence that this taxpayer/outlet/POS was already registered/integrated with FBR:

- FBR POS registration certificate/screen;
- POS Registration Number;
- taxpayer STRN/NTN and outlet identity matching the client;
- POS integration/registration date if shown;
- current FBR portal status showing the POS/outlet as integrated;
- one genuine historical FBR-verified invoice from that POS, showing FBR invoice number and POS identity;
- current working or previously installed FBR fiscalization software/SDC evidence.

### Path B — current FBR/PRAL instruction

Collect a current written instruction/package from:
- FBR;
- PRAL; or
- the client's authorized/licensed integrator,

explicitly directing this taxpayer/POS to use the legacy Software Fiscal Component / SDC interface.

## 5. Existing-machine technical evidence

If the client has the old integrated Windows POS machine, capture the following **read-only** evidence.

### Installed service/application
- installed FBR/PRAL fiscalization application name;
- Windows service name;
- file/product version;
- installation directory;
- executable names and file hashes;
- service start mode/status.

### Configuration — redact secrets
- Test vs Production setting;
- POS Registration Number;
- outlet/POS identifier;
- configured local host/port if visible;
- target/storage folder;
- SDC/Fiscalization service version;
- configuration-file names and non-secret keys.

**Do not copy access codes, passwords, tokens, private keys or secrets into Git or chat.**
A screenshot/config extract must redact secret values while preserving field names and structure.

### Runtime topology
Record whether the existing POS communicates with:
- SDC on the same workstation;
- SDC on another LAN host;
- an external PRAL/FBR endpoint;
- a local bridge/service.

### Existing application behavior
Capture:
- request sample with customer/commercial values anonymized;
- response sample with identifiers anonymized;
- invoice number format;
- QR payload if it can be decoded safely;
- sale and return behavior;
- behavior when internet/SDC is unavailable;
- any daily/weekly/monthly close action.

## 6. FBR invoice evidence

For one old invoice that verifies successfully in FBR/Tax Asaan, record:

- source POS invoice number;
- FBR invoice number;
- POS registration/software number printed;
- invoice timestamp;
- QR decoded value;
- payment mode shown;
- return/reference behavior if a return receipt is available.

Customer names, CNICs, phone numbers and other personal data should be redacted.

## 7. Gate 1 machine-contract evidence

Before implementing `protocol/legacy_sdc.py`, all applicable items below must be resolved from authoritative/client-authorized evidence:

1. exact transport topology;
2. exact Test configuration;
3. exact Production configuration;
4. exact service base address and route(s);
5. authentication/access-code handling;
6. request schema and field types;
7. response schema and field types;
8. FBR invoice-number semantics;
9. QR payload rule;
10. POS/device identity fields;
11. invoice type enum;
12. payment mode enum;
13. sale request;
14. debit/credit note or return request;
15. cancellation/adjustment behavior;
16. duplicate/idempotency semantics;
17. offline issuance behavior;
18. restoration/upload behavior;
19. daily/weekly/monthly closing behavior;
20. error codes and retry rules.

Any missing item remains `UNRESOLVED` and its runtime path stays disabled.

## 8. What may proceed before Gate 0/1 closes

Safe work:
- documentation;
- no-network static tests;
- adapter interfaces with a mock implementation;
- non-destructive schema design;
- ERPNext-native snapshot tests;
- security/idempotency scaffolding.

Not yet allowed:
- hard-coding localhost routes from mirrors;
- copying old access-code logic from third parties;
- real SDC/FBR request;
- installing old SDC packages blindly;
- enabling Production;
- interpreting DI V1.2 tokens as SDC credentials.

## 9. Gate decision

Current result:

```text
CLIENT LEGACY AUTHORITY EVIDENCE: MISSING
CURRENT LEGACY MACHINE CONTRACT: MISSING
LEDGIX REPO LEGACY SDC IMPLEMENTATION: NOT FOUND
REAL FBR NETWORK AUTHORIZATION: NO
V1 TRANSPORT IMPLEMENTATION: BLOCKED
```

### Next action

Inspect the client's existing/old FBR-integrated POS machine and FBR registration evidence.

Once that evidence is captured, update this document with:
- `PASS` or `FAIL` for grandfathered regime;
- exact technical source/package/version;
- resolved machine-contract table;
- authorization for Phase 1/3 implementation.
