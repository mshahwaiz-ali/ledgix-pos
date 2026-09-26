# Ledgix FBR & Tax Module — Historical Reference

**Status:** DEPRECATED / HISTORICAL PRE-MIGRATION DOCUMENTATION  
**Do not use as current implementation or operations guidance.**

This compatibility file previously described the tax/FBR module when Ledgix custom sale, return, customer, retry and offline-processing paths were active.

The ERPNext-core migration replaced that operating model.

## Current documentation

Use these files instead:

- `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md` — current tax/FBR architecture and authority model
- `docs/fbr/FBR_PRODUCTION_CHECKLIST.md` — Sandbox proof, Production readiness and failure handling
- `docs/architecture/CURRENT_ARCHITECTURE.md` — overall application authority boundaries
- `docs/operations/ERP_WORKFLOWS.md` — current ERPNext-native business flows

## Current transaction sources

New FBR activity originates from supported submitted ERPNext documents:

```text
Sales Invoice
POS Invoice
native Sales/POS returns and Credit Notes
```

Historical `Ledgix Sale` and `Ledgix Sales Return` are frozen read-only migration evidence.

## Current retry policy

Historical retry/offline guidance in earlier versions of this document is retired.

Current `apps/ledgix_saas/hooks.py` deliberately has:

```python
scheduler_events = {}
```

A Production request with an ambiguous outcome becomes `Reconciliation Required`. It is not blindly retried by a scheduler.

## Production status

The application-side FBR integration and safety controls are implemented, but real client Sandbox proof and the external compliance/go-live evidence are still required.

**FBR Production is NOT YET PRODUCTION-READY until those real external gates are satisfied.**

This file is retained only to keep older repository links from becoming misleading 404s. Historical migration material belongs under `docs/archive/migration/`.
