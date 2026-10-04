# Federal Tier-1 POS / IMS V1 — Current Authority

This directory is the current operating and machine-contract authority for `frappe-bench/apps/fbr_v1`.

See the [corrective verification report](../../production/final_corrective_verification.md) for current local test and migration evidence. Both network gates remained off. Real client evidence, Sandbox acceptance, and Production activation remain external and pending.

## Current protocol authority

- [Documented protocol contract](FBR_V1_DOCUMENTED_PROTOCOL_CONTRACT.md)
- [Source inventory](FBR_V1_SOURCE_INVENTORY.md)

## Current runtime and operations

- [Runtime architecture](FBR_V1_RUNTIME_ARCHITECTURE.md)
- [Setup and activation](FBR_V1_SETUP_AND_ACTIVATION.md)
- [Production checklist](FBR_V1_PRODUCTION_CHECKLIST.md)
- [Unresolved external contracts](FBR_V1_UNRESOLVED_EXTERNAL_CONTRACTS.md)

## Historical implementation records

These explain how the implementation was designed and audited. They are not current operating/setup authority:

- [Canonical redesign plan](FBR_V1_CANONICAL_REDESIGN_PLAN.md)
- [Forensic audit](FBR_V1_FORENSIC_AUDIT.md)
- [V1.2-to-V1 component matrix](FBR_V12_TO_V1_COMPONENT_MATRIX.md)
- [Phase-0 protocol gate](FBR_V1_PHASE0_REGIME_PROTOCOL_GATE.md)

ERPNext remains the sole accounting, stock, tax, payment, receivable, return, and total authority. Federal V1 is an integration/evidence layer. Production remains fail-closed until every independent gate and external approval is complete.
