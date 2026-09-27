# FBR V1 / Federal Tier-1 POS Workspace

This folder is the design authority for the Ledgix `fbr_v1` app.

## Direction

`fbr_v1` is being built as a **fresh Federal FBR Tier-1 POS / IMS V1 implementation from the FBR POS technical documentation**.

The app originally started as a copy of `fbr_v12` only to reuse safe Frappe/ERPNext structure. DI V1.2 payloads, reference APIs, scenario certification and DI endpoint semantics are not V1 authority.

We are **not** recovering or cloning an old client installation to define V1.

## Canonical documents

1. `FBR_V1_SOURCE_INVENTORY.md` — legal/technical source boundary.
2. `FBR_V1_DOCUMENTED_PROTOCOL_CONTRACT.md` — exact documented V1 wire contract used by code.
3. `FBR_V1_FORENSIC_AUDIT.md` — bootstrap-clone audit.
4. `FBR_V12_TO_V1_COMPONENT_MATRIX.md` — KEEP/MODIFY/REPLACE/DELETE/UNRESOLVED matrix.
5. `FBR_V1_CANONICAL_REDESIGN_PLAN.md` — phased implementation plan.
6. `FBR_V1_PHASE0_REGIME_PROTOCOL_GATE.md` — Phase-0 source lock and remaining activation boundaries.

## Non-negotiable constraints

- ERPNext remains the accounting, stock, payment and tax authority.
- No ERPNext/Frappe core edits.
- No production changes during redesign.
- No real FBR network calls until explicitly authorized.
- No V1.2 behavior imported into V1 unless the V1 documentation independently proves it.
- No new git branches; work remains on `main`.
- Production transport remains fail-closed.

## Current phase

**Phase 1A complete:** pure documented V1 protocol foundation.

Implemented under `fbr_v1/protocol/`:
- local IMS health/fiscalize endpoints;
- Federal cloud V1 Sandbox/Production endpoints;
- exact POSID/USIN invoice model;
- documented payment modes;
- documented header/item invoice types including Third Schedule;
- fiscal-response parser;
- fake transport tests.

Next: **Phase 1B — map immutable ERPNext Sales Invoice / POS Invoice evidence into this exact V1 wire contract.**
