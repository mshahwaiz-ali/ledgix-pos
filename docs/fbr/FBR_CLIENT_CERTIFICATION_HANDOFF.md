# FBR Client Certification Handoff

**Target software status:** READY FOR CLIENT CERTIFICATION
**Sandbox Certified:** NO
**Production Ready:** NO

## Software-complete

ERPNext-only monetary authority, FBR V2 profile/mapping/reference model, immutable snapshots/readiness, guarded Sandbox transport, Known Offline lifecycle + Desk surface, reconciliation safety, print/correction foundation, client-supplied DI-logo path, Production logo blocker and legacy tax-master retirement.

## Client/operator must provide/prove

Legal Company identity/address, Business Nature/Sector/provider data, software/POS registration where required, authoritative DI logo, Sandbox token, official reference/mapping evidence, real Sandbox scenarios, return/note proof if in scope, Known Offline rule/window if enabled, final QR/print sign-off, Production token, final verified backup/release SHA and explicit Production authorization.

## Gate

```bash
bash scripts/run_fbr_client_certification_handoff_gate.sh ledgix-erpnext.local
```

Use labels only when supported by evidence:

- READY FOR CLIENT CERTIFICATION = software-side closure passed;
- SANDBOX CERTIFIED = persisted real required Sandbox evidence;
- PRODUCTION READY = all Production-switch prerequisites green;
- PRODUCTION ACTIVE = explicit authorized activation completed.
