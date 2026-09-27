# FBR V1 / Federal Tier-1 POS Workspace

This directory is the canonical design authority for the Ledgix `fbr_v1` app.

## Current status

The application under `apps/fbr_v1` is a **bootstrap clone of `fbr_v12`**, not a finished Federal Tier-1/V1 integration.

A complete forensic audit and current-source review has established a critical regime boundary:

- Current Chapter XIV grandfathers POS systems that were **already** registered/integrated with FBR.
- Current registration/testing of registered persons is through a licensed integrator or PRAL.
- Therefore `fbr_v1` is being redesigned only as a **legacy/grandfathered POS/SDC compatibility adapter**.
- A new Tier-1 taxpayer must not be routed to old SDC merely because it is Tier-1.
- Exact legacy SDC endpoint/auth/request/response details remain **UNRESOLVED** until authoritative current FBR/PRAL evidence is obtained.

## Canonical documents

1. [FBR_V1_SOURCE_INVENTORY.md](FBR_V1_SOURCE_INVENTORY.md)  
   Current Federal legal/technical source hierarchy and unresolved machine-contract inventory.

2. [FBR_V1_FORENSIC_AUDIT.md](FBR_V1_FORENSIC_AUDIT.md)  
   Complete audit of the bootstrap clone and inherited V1.2 assumptions.

3. [FBR_V12_TO_V1_COMPONENT_MATRIX.md](FBR_V12_TO_V1_COMPONENT_MATRIX.md)  
   KEEP / MODIFY / REPLACE / DELETE / UNRESOLVED matrix for the inherited app.

4. [FBR_V1_CANONICAL_REDESIGN_PLAN.md](FBR_V1_CANONICAL_REDESIGN_PLAN.md)  
   Target architecture, DocTypes, ERPNext fields/hooks, migrations, tests, acceptance gates and phased implementation sequence.

## Non-negotiable constraints

- ERPNext remains the accounting, stock, payment and tax authority.
- No ERPNext/Frappe core edits.
- No production access/change as part of V1 redesign.
- No real FBR network calls while designing/implementing offline gates.
- No guessed endpoint, token, JSON field, enum or legal workflow.
- No branch creation; project work remains on `main` as explicitly requested.
- Persistent inherited data is migrated non-destructively.
- Production transport is fail-closed by default.

## Next step

Review the canonical redesign plan. No runtime implementation begins until the plan is accepted and the legacy-regime / machine-contract Gate 0 and Gate 1 evidence is available.
