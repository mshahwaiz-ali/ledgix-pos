# Ledgix Documentation Archive

**Status:** HISTORICAL / EVIDENCE ONLY

This directory preserves point-in-time evidence and completed migration history.

It is **not** the current operating or development authority.

## Current documentation

Use:

- `docs/developer/README.md` for software architecture, operations, deployment and release engineering;
- `docs/client/README.md` for client/operator instructions;
- root `README.md` as the repository front door.

## Archive areas

### `audit/`

Point-in-time audit and acceptance evidence:

- `FINAL_FORENSIC_INSPECTION_20260926.md` — final software forensic audit baseline;
- `LOCAL_OPERATING_ACCEPTANCE_DATASET_20260917.md` — verified local ERPNext-native operating/acceptance dataset evidence.

### `migration/`

Completed ERPNext-core migration plans, phase notes and progress evidence for phases 0–13.

### `historical/fbr-v2/`

Preserved design/phase evidence from the FBR V2 redesign. These documents explain how the current architecture was reached and can contain phase-time wording that is no longer current.

## Authority rule

When archive material conflicts with current documentation or current source:

1. current repository implementation wins;
2. current `docs/developer/` or `docs/client/` guidance wins for its audience;
3. archived material is used only for historical reasoning/evidence.

Do not use archived status labels as current certification or Production approval.
