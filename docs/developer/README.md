# Ledgix POS — Developer Documentation

**Status:** CURRENT / CANONICAL INDEX  
**Architecture baseline:** 2026-09-26 final forensic audit

This directory is the primary developer documentation for the current Ledgix POS architecture.

It describes the product as it exists now.

Historical migration/phase documents are preserved separately and are not current operating authority.

---

## 1. Read this first

Recommended order for a new developer:

1. [ARCHITECTURE.md](ARCHITECTURE.md)
2. [CODEBASE_AND_EXTENSION_POINTS.md](CODEBASE_AND_EXTENSION_POINTS.md)
3. [BUSINESS_WORKFLOWS.md](BUSINESS_WORKFLOWS.md)
4. the subsystem document for the feature being changed
5. deployment/testing/security docs before release-sensitive work

---

## 2. Core architecture

### [ARCHITECTURE.md](ARCHITECTURE.md)

High-level system authority and boundaries.

Covers:

- ERPNext vs Ledgix ownership;
- application layers;
- runtime hooks;
- transaction/FBR boundaries;
- legacy retirement;
- deployment model;
- current certification status.

### [CODEBASE_AND_EXTENSION_POINTS.md](CODEBASE_AND_EXTENSION_POINTS.md)

Repository/code organization.

Covers:

- hooks.py;
- API/service layers;
- Pages/Reports/Print Formats;
- DocTypes;
- setup/migration/patches;
- extension patterns;
- anti-patterns;
- how to trace a feature.

---

## 3. Business architecture

### [BUSINESS_WORKFLOWS.md](BUSINESS_WORKFLOWS.md)

End-to-end current workflows:

- Retail POS;
- B2B sales;
- payments;
- returns/refunds/exchanges;
- purchasing;
- inventory;
- correction principles.

### [POS_ARCHITECTURE.md](POS_ARCHITECTURE.md)

Detailed current Ledgix POS implementation over ERPNext:

- POS Profile;
- Opening/Closing Entry;
- POS Invoice;
- split tender;
- hold/resume;
- returns;
- consolidation;
- POS + FBR boundary.

### [SALES_RETURNS_AND_PAYMENTS.md](SALES_RETURNS_AND_PAYMENTS.md)

Detailed B2B/AR architecture:

- Sales Invoice;
- Payment Entry;
- receivables;
- Credit Notes;
- refunds;
- exchange;
- idempotency.

### [PURCHASE_AND_INVENTORY.md](PURCHASE_AND_INVENTORY.md)

Detailed buying/stock architecture:

- Purchase Order/Receipt/Invoice;
- supplier payment;
- purchase return;
- Stock Entry;
- Stock Reconciliation;
- Batch/Serial;
- Inventory Intelligence.

### [ACCOUNTING_AND_TAX.md](ACCOUNTING_AND_TAX.md)

Monetary/accounting authority:

- ERPNext tax rows/totals/GL;
- native tax contract;
- FBR classification vs monetary tax;
- legal taxable-base extension;
- AR/AP;
- reporting.

---

## 4. FBR and security

### [FBR_ARCHITECTURE.md](FBR_ARCHITECTURE.md)

Canonical FBR V2 architecture:

- Integration Profile;
- mappings/reference data;
- immutable snapshot;
- readiness;
- payload;
- Sandbox certification;
- Production interlocks;
- crash-window safety;
- Reconciliation Required;
- Known Offline;
- print/correction boundaries.

Current baseline:

- Software Ready for Client Certification: YES;
- Sandbox Certified: NO;
- Production Ready: NO;
- Production Active: NO;
- general network cutover: false.

### [SECURITY_AND_PERMISSIONS.md](SECURITY_AND_PERMISSIONS.md)

Security model:

- roles;
- Frappe permissions;
- product visibility vs authorization;
- sensitive FBR actions;
- secrets;
- tenant isolation;
- legacy freeze;
- current permission-policy defect.

---

## 5. Installation and operations

### [INSTALLATION_AND_CONFIGURATION.md](INSTALLATION_AND_CONFIGURATION.md)

Supported local and production installation/configuration:

- Frappe -> ERPNext -> Ledgix;
- local canonical site;
- production provisioning;
- Business Profiles;
- native ERPNext prerequisites;
- secrets.

### [DEPLOYMENT_AND_UPGRADES.md](DEPLOYMENT_AND_UPGRADES.md)

Production release model:

- immutable SHA/tag;
- single-site update;
- shared-bench cohort update;
- maintenance;
- build/migrate/smoke;
- release evidence.

### [BACKUP_RESTORE_ROLLBACK.md](BACKUP_RESTORE_ROLLBACK.md)

Recovery contract:

- verified backup set;
- checksums;
- encryption key;
- recovery target;
- restore drills;
- rollback pairing;
- Phase 12 verification.

### [MULTI_SITE_SAAS.md](MULTI_SITE_SAAS.md)

SaaS tenancy:

- one site/database per client;
- one Ledgix release per shared bench;
- tenant provisioning;
- cohort releases;
- FBR/backup isolation;
- dedicated-bench separation.

---

## 6. Quality, migration and support

### [TESTING_AND_RELEASE_GATES.md](TESTING_AND_RELEASE_GATES.md)

Evidence hierarchy:

- CI;
- static contracts;
- unit tests;
- runtime gates;
- recovery gates;
- client readiness;
- manual UAT;
- FBR certification;
- final production release gate.

### [MIGRATION_AND_LEGACY_RETIREMENT.md](MIGRATION_AND_LEGACY_RETIREMENT.md)

Completed migration/current legacy boundary:

- phases 0–13 closed;
- frozen historical business ledgers;
- deterministic snapshot;
- read-only permissions;
- controlled rollback unfreeze;
- physically retired old tax/FBR masters;
- future cleanup boundary.

### [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

Current diagnostic guide across:

- local runtime;
- transactions;
- stock/accounting;
- permissions;
- FBR states;
- deployment;
- recovery;
- legacy history.

---

## 7. Current authority order

When sources conflict, use this order:

1. current repository implementation;
2. current runtime wiring in hooks.py;
3. this developer documentation set;
4. final forensic evidence for the 2026-09-26 baseline;
5. historical migration/archive documents.

A phase-time "ACTIVE" or "PENDING" label in an archived document does not override current source.

---

## 8. Historical documentation

Historical ERPNext migration material remains under:

    docs/archive/migration/

Use it to understand:

- why a migration decision was made;
- original proof/gate structure;
- rollback reasoning;
- phase-specific design context.

Do not use archived phase instructions as current operational runbooks.

---

## 9. Final forensic evidence

The final 2026-09-26 forensic report remains:

    docs/archive/audit/FINAL_FORENSIC_INSPECTION_20260926.md

It is evidence for a point-in-time audit.

It is not the primary developer manual.

Key baseline outcome:

- software-side inspected blockers closed;
- Software Ready for Client Certification: YES;
- Sandbox Certified: NO;
- Production Ready: NO;
- Production Active: NO;
- zero real FBR/PRAL calls during final audit.

---

## 10. Known current maintenance item

Documentation consolidation identified one source inconsistency that should be corrected in a later code change:

> Ledgix FBR Submission Log JSON intends read-only Desk evidence, but setup/permissions.py retains older broad System Manager/Ledgix Admin rights and fast_permissions can synchronize that policy during migrate.

Do not manually mutate Submission Logs.

The code fix should align centralized permission policy with the read-only evidence design and add migrate-level regression coverage.

---

## 11. Development principles

Before implementing a feature:

- identify authoritative ERPNext/Ledgix object;
- avoid duplicate business/accounting/stock truth;
- prefer application extension points over ERPNext core edits;
- keep server-side authorization explicit;
- preserve idempotency where retries matter;
- keep FBR fail-closed;
- add regression tests;
- update the relevant canonical document.

---

## 12. Release principles

Before production acceptance:

- deploy immutable release;
- create verified backup;
- preserve rollback identity;
- migrate/build;
- run preflight/smoke;
- complete client readiness;
- complete profile-specific UAT;
- require real FBR evidence only when FBR Production is in scope;
- run final production release gate.

Do not claim a stronger readiness state than the evidence supports.

---

## 13. One-sentence architecture

> **ERPNext owns current business, stock, tax and accounting truth; Ledgix provides the product experience, compatibility and FBR compliance/orchestration around native ERPNext transactions, while historical duplicate Ledgix business records remain frozen evidence and Production FBR remains fail-closed until real client certification/go-live prerequisites are complete.**
