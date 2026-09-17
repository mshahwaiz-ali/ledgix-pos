# Ledgix FBR & Tax Layer — Historical Reference

**Status:** DEPRECATED / HISTORICAL PRE-MIGRATION DOCUMENTATION  
**Do not use as current operating guidance.**

This file previously described the FBR/tax architecture when `Ledgix Sale`, `Ledgix Sales Return`, `Ledgix Customer` and related custom business DocTypes were active transaction/master authorities.

That architecture was retired by the ERPNext-core migration.

## Current authority

For current implementation and operations use:

- `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md`
- `docs/fbr/FBR_PRODUCTION_CHECKLIST.md`
- `docs/architecture/CURRENT_ARCHITECTURE.md`
- `docs/operations/ERP_WORKFLOWS.md`

Current FBR source transactions are submitted ERPNext:

- `Sales Invoice`
- `POS Invoice`
- their native return/Credit Note documents

Historical `Ledgix Sale` / `Ledgix Sales Return` are frozen migration evidence and must not issue new FBR invoices.

## Important behavior change

Older versions of this document described retry/offline workers. That guidance is retired.

Current `apps/ledgix_saas/hooks.py` intentionally defines:

```python
scheduler_events = {}
```

An ambiguous Production POST is fail-closed as `Reconciliation Required`; it must be externally reconciled before any supported retransmission decision. Do not restore blind retry/offline schedulers from historical code or documentation.

## Why this file remains

The filename is retained temporarily so old repository links do not silently point to missing content. Historical migration rationale lives under `docs/archive/migration/`.

If no external/internal references require this compatibility filename in a later cleanup, it may be removed as a separate documentation-maintenance change.
