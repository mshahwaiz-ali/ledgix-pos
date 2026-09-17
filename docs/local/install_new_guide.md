# Installer Redesign Notes — Historical Reference

**Status:** SUPERSEDED / HISTORICAL PLANNING DOCUMENT  
**Do not use as current installation instructions.**

This file captured an earlier installer redesign plan. The planned architecture has since been implemented and refined in the repository.

## Current installation authority

Use:

```text
docs/local/LOCAL_INSTALLATION.md
install.sh
site_setup.sh
start.sh
```

Production deployment is documented under:

```text
docs/production/
```

## Current implemented local model

The current repository now uses:

- `install.sh --local` for dependency/bench preparation;
- Frappe v15 plus required ERPNext v15;
- `site_setup.sh --ensure` for the canonical local site;
- canonical site `ledgix-erpnext.local`;
- standard stack `Frappe -> ERPNext -> ledgix_saas`;
- `site_setup.sh --reset` with an exact destructive confirmation phrase;
- `.secrets/sites/` for local credential files outside Git;
- `start.sh` for development runtime/status/stop/smoke functions;
- production deployment delegated to the `deploy/` workflow.

The old planning ideas about arbitrary app selection, a Ledgix-only site, generic `ledgix.local`, or treating installer design decisions as future work are no longer current.

## Why this file remains

The filename is retained temporarily to avoid breaking old internal links and to preserve the design history that led to the current scripts.

For current work, make decisions from the actual scripts and `docs/local/LOCAL_INSTALLATION.md`, not from the historical plan below this point.
