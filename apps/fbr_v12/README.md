# FBR V1.2

Standalone Frappe/ERPNext application for the current Ledgix FBR Digital Invoicing V1.2 implementation.

## App identity

- Technical app name: `fbr_v12`
- Desk title: **FBR V1.2**
- Runtime dependencies: **Frappe 15 + ERPNext 15**
- `ledgix_saas` is intentionally **not** a required app.

## Extraction status

This branch starts the extraction from `ledgix_saas` without changing the active FBR runtime yet.

The migration is intentionally staged:

1. establish an independently installable app package;
2. move FBR-owned DocTypes, services, API endpoints, print helpers and setup code;
3. replace `ledgix_saas.*` imports with `fbr_v12.*` ownership;
4. move ERPNext invoice hooks to this app;
5. validate schema/data continuity for existing sites;
6. only then remove the old FBR source from `ledgix_saas`.

Until the ownership cutover is complete, `ledgix_saas` remains authoritative for production FBR behavior.
