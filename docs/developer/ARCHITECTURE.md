# Ledgix POS — Current Architecture

**Status:** CURRENT / CANONICAL DEVELOPER ARCHITECTURE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Baseline commit:** ae595a53d724c84f8dc78d01ec3b85d44a3f45e8  
**Documentation branch:** docs-consolidation-20260926  
**Supported application model:** Frappe + ERPNext + ledgix_saas

## 1. Purpose

This document is the canonical high-level architecture guide for the current Ledgix POS product.

It explains the system as it exists after the ERPNext-core migration and final FBR V2 software hardening. A developer should be able to read this document first and understand:

- which layer owns each business concept;
- where Ledgix extends ERPNext and where it deliberately does not;
- how the main sales, POS, purchasing, inventory, payment, accounting and FBR flows are divided;
- how compatibility with the former Ledgix business engine is contained;
- how current product pages and APIs connect to ERPNext-native records;
- what the FBR readiness states actually mean;
- which boundaries must remain fail-closed;
- how deployment, permissions, migration and historical evidence fit into the architecture.

Detailed subject-specific documents will build on this architecture rather than redefine it.

When documentation and implementation disagree, the current implementation is authoritative. Historical migration documents describe how the present architecture was reached; they are not current operating specifications.

---

## 2. Governing architecture rule

The central Ledgix design rule is:

> **One business concept must have one authoritative source of truth.**

ERPNext is the authoritative business, stock and accounting engine.

Ledgix is the product, workflow, compatibility, compliance and FBR orchestration layer around that engine.

Ledgix does not fork or modify ERPNext core to create private financial behavior.

The practical consequence is:

    Ledgix UI / APIs / product services
                  |
                  v
       ERPNext native business documents
                  |
                  v
      ERPNext stock + accounting ledgers

and, when FBR applies:

    Submitted ERPNext invoice
                  |
                  v
       Ledgix immutable FBR evidence
                  |
                  v
        FBR readiness / payload layer
                  |
                  v
       controlled FBR transport boundary

There must not be a second Ledgix monetary, receivable, payable, stock or accounting truth running beside ERPNext.

---

## 3. Current product status

The architecture baseline distinguishes software closure from external certification and Production activation.

| State | Current status | Meaning |
|---|---|---|
| ERPNext-core migration | COMPLETE | Migration phases 0–13 are closed. There is no active migration phase after Phase 13. |
| Business/accounting authority | ERPNext NATIVE | New operational business records use ERPNext-native masters, transactions and ledgers. |
| Ledgix product/UI layer | ACTIVE | Ledgix keeps focused product pages, APIs, profile logic, reporting adapters and compliance workflows. |
| Legacy Ledgix business engine | RETIRED / FROZEN HISTORY | Historical duplicate business records may remain for audit/migration evidence but are not current transaction authority. |
| FBR V2 software | READY FOR CLIENT CERTIFICATION | The inspected software-side blockers are closed sufficiently to proceed to genuine client certification. |
| Sandbox Certified | NO | No real authorized Sandbox certification is claimed by the final software audit. |
| Production Ready | NO | Real client/provider/legal/reference/certification prerequisites remain outstanding. |
| Production Active | NO | Production posting is not active. |
| General FBR V2 network cutover | DISABLED | The global cutover flag remains fail-closed. |
| Real FBR/PRAL calls during final audit | 0 | Local/static/runtime proof did not constitute external certification. |

A developer must not collapse these states into one generic "FBR ready" label.

---

## 4. System ownership model

### 4.1 ERPNext-owned concepts

ERPNext owns the normal business transaction model.

| Business concept | Authoritative ERPNext model |
|---|---|
| Company | Company |
| Item/category | Item / Item Group |
| Customer | Customer |
| Supplier | Supplier |
| Price lists and prices | Price List / Item Price / Pricing Rule |
| Retail sale | POS Invoice |
| B2B sale | Sales Invoice |
| Retail return | Return POS Invoice |
| B2B return / credit note | Return Sales Invoice |
| POS tender / split tender | Native ERPNext POS invoice payment rows |
| Customer receipt / allocation | Payment Entry |
| Customer outstanding / receivable | Sales Invoice + GL / receivable state |
| Purchase order | Purchase Order |
| Goods receipt | Purchase Receipt |
| Supplier invoice | Purchase Invoice |
| Supplier payment / payable | Payment Entry + AP / GL |
| Warehouses | Warehouse |
| Quantity on hand | Stock Ledger Entry / Bin |
| Internal stock movement | Stock Entry |
| Stock correction | Stock Reconciliation |
| Batch / serial identity | Batch / Serial No / Serial and Batch Bundle |
| POS opening / closing | POS Opening Entry / POS Closing Entry |
| Monetary tax rows | ERPNext taxes and charges structures |
| Financial posting | General Ledger and native ERPNext accounting |
| Standard financial reports | ERPNext accounting/reporting layer |

If a feature can be represented using one of these native authorities plus limited Ledgix metadata, that is the default architecture.

### 4.2 Ledgix-owned concepts

Ledgix intentionally owns product-specific capabilities not supplied by ERPNext as the Ledgix product requires them.

These include:

- Ledgix POS and focused workflow UX;
- profile-aware product navigation;
- setup/onboarding UX over existing ERPNext configuration;
- compatibility routing from historical Ledgix RPC contracts into native ERPNext services;
- Inventory Intelligence and other focused reporting presentation;
- FBR Integration Profile;
- FBR item classification/mapping;
- FBR tax-component mapping;
- official FBR reference-data cache and evidence;
- immutable FBR snapshot persistence;
- FBR payload construction from ERPNext-native source evidence;
- Sandbox certification evidence;
- FBR Submission Logs;
- Known Offline and reconciliation workflow controls;
- correction-request tracking;
- branding and product settings;
- release/readiness/UAT evidence where Ledgix needs an explicit product gate;
- legacy retirement state/digest controls.

These capabilities extend ERPNext. They do not replace ERPNext's commercial or accounting records.

---

## 5. Application layers

The ledgix_saas app can be understood as six primary layers.

### 5.1 Product/UI layer

Primary user-facing Ledgix surfaces include:

- Ledgix POS;
- Tax & FBR Center;
- Inventory Intelligence / Business Intelligence surface;
- Setup Wizard;
- the Ledgix Workspace and product navigation;
- branded print and product-shell behavior.

These pages are convenience and workflow surfaces over native authority.

A page being named "Ledgix" does not imply that it stores a parallel Ledgix ledger.

### 5.2 API and compatibility layer

Important API boundaries include:

- api/pos_compat.py
- api/selling_compat.py
- api/product_shell.py
- api/client_setup.py
- api/client_readiness.py
- api/fbr_native.py
- api/fbr_v2_center.py
- api/fbr_activation.py
- api/fbr_offline.py
- api/fbr_reference_v2.py
- api/fbr_v2_transport.py
- api/printing.py
- api/report_adapters.py

Compatibility APIs preserve stable frontend/RPC contracts where useful, but internally route current operations to ERPNext-native services.

Old method names are therefore not evidence that the old business engine is still authoritative.

### 5.3 ERPNext-native business service layer

Important current services include:

- services/erpnext_pos.py
- services/erpnext_selling.py
- services/erpnext_buying_inventory.py
- services/erpnext_payment_policy.py
- services/erpnext_tax_authority.py
- services/erpnext_taxable_base.py
- services/erpnext_reporting.py
- services/erpnext_reporting_compat.py

These modules are the normal Ledgix service boundary around ERPNext business documents.

They should coordinate native behavior, validate Ledgix-specific rules, and provide stable product APIs. They must not become a replacement financial engine.

### 5.4 FBR compliance service layer

Important current FBR services include:

- services/erpnext_fbr_identity.py
- services/erpnext_fbr_snapshot.py
- services/fbr_v2_snapshot_persistence.py
- services/fbr_v2_readiness.py
- services/fbr_v2_payload_builder.py
- services/fbr_submission_support.py
- services/fbr_v2_status.py

This layer consumes ERPNext-native invoice, identity and tax evidence and turns it into controlled compliance evidence and payload state.

It does not recalculate ERPNext accounting totals.

### 5.5 Setup, migration and release layer

The setup and migration packages contain:

- extension/custom-field synchronization;
- permission synchronization;
- print-format setup;
- product-shell synchronization;
- historical migration gates;
- legacy freeze/retirement logic;
- FBR retirement/migration guards;
- release/readiness gates;
- local acceptance-data helpers.

Many filenames retain historical phase numbers because they are part of the repository's migration lineage. Their existence does not mean the product is still running those phases as an active project plan.

### 5.6 ERPNext / Frappe platform layer

Frappe and ERPNext own:

- document lifecycle;
- permissions and roles;
- database transactions;
- standard business workflows;
- stock ledger;
- GL, AR and AP;
- standard reports;
- background job infrastructure;
- site isolation;
- migrations and fixtures;
- native print/document facilities.

Ledgix should extend this platform rather than duplicate it.

---

## 6. Runtime wiring and hooks

apps/ledgix_saas/hooks.py is one of the most important architecture files because it declares the live integration boundaries.

### 6.1 Required dependency

ERPNext is a required app.

A Frappe-only Ledgix site is not the supported current business architecture.

### 6.2 After-migrate sequence

The after-migrate chain applies Ledgix ERPNext extensions, tax foundations, phase-era extension synchronizers, permissions, print formats, product-shell setup and legacy retirement enforcement.

The important architectural rule is the final retirement guard:

- normal permissions are applied;
- then the historical business DocTypes finish migration in their intended read-only/frozen state.

Migration must not silently reactivate old Ledgix business ledgers.

### 6.3 Compatibility overrides

hooks.py redirects many older RPC names to current compatibility services.

Examples include:

- old POS V2 calls -> api/pos_compat.py;
- old shift calls -> api/pos_compat.py;
- old B2B selling calls -> api/selling_compat.py;
- old inventory-intelligence/BI calls -> ERPNext-native reporting;
- retired tax actions -> fail-closed legacy tax guard;
- retired Ledgix Sale/Return FBR actions -> fail-closed legacy FBR guard.

This is a deliberate strangler/compatibility pattern: old client contracts can survive while old transaction authority remains retired.

### 6.4 Invoice document events

For Sales Invoice and POS Invoice, current hooks establish the FBR lifecycle boundary:

1. before validation: stamp approved taxable-base inputs where applicable;
2. before submit: persist the FBR V2 snapshot when the company profile requires it;
3. on submit: invoke native FBR orchestration;
4. before cancel: enforce post-FBR cancellation safety.

ERPNext submission remains the commercial/accounting event. Ledgix attaches compliance behavior around that event.

### 6.5 No blind FBR retry scheduler

scheduler_events is intentionally empty for FBR retry behavior.

An ambiguous Production POST is not solved by a background loop that blindly resends the same invoice.

This fail-closed rule is fundamental to duplicate-submission safety.

---

## 7. Retail POS architecture

The Ledgix POS screen remains a first-class Ledgix product surface, while ERPNext owns the transaction.

Current conceptual flow:

    Ledgix POS UI
        -> ERPNext POS Profile
        -> active POS Opening Entry
        -> ERPNext Item / Customer / Price List
        -> ERPNext stock availability
        -> ERPNext POS Invoice
        -> native payment rows / split tenders
        -> optional FBR workflow on that POS Invoice
        -> ERPNext POS Closing Entry
        -> native ERPNext consolidation/accounting

### Key rules

- A live retail sale is an ERPNext POS Invoice.
- Split tender is represented by native ERPNext payment rows.
- A current Ledgix Payment record is not created to mirror the same tender.
- A held retail cart is represented by an ERPNext draft POS Invoice.
- A retail return uses the native ERPNext POS return relationship.
- Return pricing derives from the authoritative original sale rather than arbitrary client replacement rates.
- POS Closing Entry remains the shift-close authority.
- The consolidated Sales Invoice created by ERPNext is accounting consolidation and must not become a second FBR source for the same POS business transaction.

The current implementation boundary is primarily services/erpnext_pos.py with api/pos_compat.py preserving the product RPC contract.

---

## 8. B2B sales, returns and receivables

B2B transaction flow:

    ERPNext Customer / Item / pricing
        -> Sales Invoice
        -> optional stock effect
        -> Payment Entry allocation
        -> ERPNext outstanding / AR / GL
        -> native Sales Invoice return / Credit Note
        -> optional refund Payment Entry
        -> optional FBR workflow on the authoritative invoice

services/erpnext_selling.py is the primary service boundary.

### Key rules

- Ledgix client IDs may support idempotency or compatibility, but they do not form a second invoice ledger.
- Customer payments use ERPNext Payment Entry and invoice references.
- Outstanding and overdue amounts come from ERPNext.
- Credit Notes use ERPNext's native return mechanism.
- Original submitted line economics remain authoritative for return construction.
- Refunds remain native accounting transactions.

---

## 9. Purchasing and inventory architecture

Current purchasing paths are ERPNext-native.

Full procurement path:

    Supplier
        -> Purchase Order
        -> Purchase Receipt
        -> Purchase Invoice
        -> Payment Entry

Direct/smaller-shop path:

    Supplier
        -> Purchase Invoice
        -> optional native stock update
        -> Payment Entry

services/erpnext_buying_inventory.py is the Ledgix compatibility/service boundary.

### Stock authority

Inventory truth comes from ERPNext:

- Stock Ledger Entry;
- Bin;
- Warehouse;
- Stock Entry;
- Stock Reconciliation;
- Batch;
- Serial No;
- Serial and Batch Bundle;
- native purchase/sale/return stock effects.

Ledgix Inventory Intelligence is a read/presentation layer. It is not a stock ledger.

Current operation must not write new Ledgix Stock Movement, Ledgix Stock Lot or Ledgix Stock Serial records as an alternative stock truth.

---

## 10. Payments and accounting architecture

ERPNext owns the monetary ledger.

This includes:

- invoice totals;
- taxes and charges;
- GL entries;
- accounts receivable;
- accounts payable;
- Payment Entry posting;
- settlement allocation;
- stock valuation and COGS;
- standard accounting reports.

Ledgix may enforce product policy around Payment Entry, tender availability or workflow context, but it must not create a separate accounting result.

When a test, UI value or historical Ledgix record disagrees with current ERPNext accounting, the correct solution is to understand the discrepancy or fix the integration. It is not acceptable to mutate ERPNext accounting merely to force a historical Ledgix expectation to pass.

---

## 11. Monetary tax architecture

ERPNext is the sole current monetary tax authority.

services/erpnext_tax_authority.py explicitly defines the current authority as ERPNext Native.

Ledgix may provide FBR/legal inputs that ERPNext generic tax structures do not fully represent, for example approved taxable-base metadata or FBR classification evidence, but:

- Ledgix must not calculate a second authoritative grand total;
- Ledgix must not silently replace ERPNext tax rows;
- FBR classification metadata must not become a hidden financial tax engine;
- financial tax outcomes must reconcile to the submitted ERPNext invoice.

The old Ledgix Tax Profile, Tax Category, Tax Rate, Item Tax Profile and global FBR Settings source models have been retired from current authority. Some historical evidence records remain intentionally preserved.

---

## 12. FBR V2 architecture

FBR is the most safety-sensitive Ledgix-specific layer.

A dedicated FBR architecture document will provide the full implementation and operational model. The high-level contract is defined here so no other module can contradict it.

### 12.1 Authoritative commercial source

Only submitted ERPNext-native source invoices are current FBR commercial sources:

- Sales Invoice;
- POS Invoice;
- their supported native return/note flows when verified.

Historical Ledgix Sale and Ledgix Sales Return records are not valid new FBR submission sources.

### 12.2 Company-scoped configuration

Ledgix FBR Integration Profile is scoped to ERPNext Company and is the authoritative FBR integration configuration container.

It contains or controls items such as:

- mode;
- onboarding state;
- provider/integrator information;
- Sandbox credential;
- Production credential;
- Production posting arm;
- reference-sync state;
- FBR-specific operating policy.

The Company link is unique so the system does not resolve one global profile across unrelated companies.

### 12.3 Seller identity

Seller identity is resolved from ERPNext Company and its linked/default Address rather than duplicated seller identity fields becoming an independent truth.

Required legal identity remains fail-closed if the actual client data is incomplete.

### 12.4 Mapping and official references

FBR Item Mapping and Tax Component Mapping translate ERPNext-native product/tax evidence into FBR classification.

Official FBR Reference Data is cached as controlled evidence.

Mappings and reference evidence are not a substitute for ERPNext monetary tax calculation.

Missing, ambiguous or stale-required evidence must block readiness rather than be guessed.

### 12.5 Immutable snapshot

Before an applicable ERPNext invoice is submitted, Ledgix can persist a V2 snapshot containing the compliance-relevant identity, item classification and tax evidence.

The snapshot is hash-verified and tied to the ERPNext source.

The purpose is to avoid reconstructing a historical legal payload later from mutable master data.

### 12.6 Payload construction

The V2 payload builder consumes:

- submitted ERPNext invoice data;
- ERPNext-authoritative seller/buyer identity;
- persisted immutable V2 snapshot;
- reviewed FBR mappings;
- official reference evidence;
- supported scenario/context.

It does not import the retired Ledgix monetary tax engine.

Payload semantics that are not proven are expected to fail closed instead of being approximated.

### 12.7 Sandbox certification

Sandbox certification is a persisted evidence state, not a checkbox based on local mocks.

A certification can be complete only when required scenarios have matching persisted Sandbox validation and POST proof according to the implemented evidence rules.

Therefore:

- local unit tests are not Sandbox certification;
- mocked HTTP results are not Sandbox certification;
- an onboarding status label alone is not Sandbox certification;
- real authorized Sandbox evidence is required.

### 12.8 Production interlocks

Production POST requires multiple independent conditions.

At minimum the software model includes:

- a company-scoped valid Integration Profile;
- genuine completed Sandbox certification evidence;
- Production credential;
- readiness checks;
- explicit Production posting arming;
- general V2 network cutover;
- no unresolved reconciliation state.

The final forensic baseline intentionally leaves Production inactive.

### 12.9 Crash-window and reconciliation safety

Before a Production POST network call can occur, the current design persists a durable attempt/log/status guard and commits it.

The source transaction enters a reconciliation-safe condition before the network window.

If the process crashes or the remote outcome is ambiguous, retransmission is blocked until external reconciliation determines whether FBR received the invoice.

This prevents the dangerous pattern:

    send POST
        -> process dies
        -> local database thinks nothing happened
        -> blindly POST again

### 12.10 Known Offline

Known Offline is a separate controlled lifecycle from an ambiguous Production POST.

The implementation does not invent a legal offline allowance or upload window. Client/provider-specific rules must be verified.

There is no generic blind retry scheduler.

---

## 13. FBR evidence and status records

Important current Ledgix records include:

| Record | Role |
|---|---|
| Ledgix FBR Integration Profile | Company-scoped FBR configuration and credentials |
| Ledgix FBR Business Nature | FBR-specific business classification |
| Ledgix FBR Item Mapping | ERPNext Item to FBR classification |
| Ledgix FBR Tax Component Mapping | ERPNext tax-account evidence to FBR component meaning |
| Ledgix FBR Reference Data | Official-reference cache/evidence |
| Ledgix FBR Sandbox Scenario | Required certification scenario definition/evidence |
| Ledgix FBR Sandbox Certification | Company/profile Sandbox certification state |
| Ledgix FBR Submission Log | Validate/POST operational evidence and reconciliation history |
| Ledgix FBR Correction Request | Post-submission correction workflow evidence |
| ERPNext invoice custom snapshot/status fields | Compliance state attached to the authoritative source |

Submission Logs are operational evidence. Normal Desk mutation is intentionally restricted; they are not general user-editable business notes.

---

## 14. Product shell and Business Profiles

Ledgix supports one application codebase across different operating profiles rather than maintaining client-specific forks.

Current profile concepts include:

- Invoice + FBR Only;
- Small Retail;
- Full Retail;
- B2B;
- Mixed.

Profile configuration can control what the Ledgix product exposes, such as:

- POS;
- B2B;
- buying;
- inventory;
- advanced inventory;
- accounting surfaces;
- FBR surfaces.

These profile flags are product/navigation configuration.

They do not grant server authorization and they do not change the underlying ERPNext authority model.

The Setup Wizard configures and validates the Ledgix product against existing ERPNext business setup. It must not silently create a parallel set of business masters.

---

## 15. Roles, permissions and security boundary

The Ledgix product uses roles such as:

- Ledgix Cashier;
- Ledgix Manager;
- Ledgix Admin;
- System Manager.

These express product intent, but Frappe/ERPNext permissions remain the server authorization authority.

Important principles:

- UI visibility is not authorization.
- Business Profile flags are not permissions.
- API methods must enforce appropriate server-side access.
- FBR credentials remain secret Password fields.
- Production transport must not expose token material in logs/results.
- FBR Submission Logs are protected from ordinary Desk mutation.
- frozen historical Ledgix business DocTypes must not be made writable as an operational shortcut.
- client sites must not share FBR credentials or business evidence.

The current permissions architecture should be documented separately in SECURITY_AND_PERMISSIONS.md.

---

## 16. Legacy business-engine boundary

The repository still contains some historical Ledgix business DocTypes because the completed migration was designed to preserve audit/migration evidence rather than destructively erase history.

Important distinction:

### Frozen historical business models

Examples include:

- Ledgix Item;
- Ledgix Category;
- Ledgix Customer;
- Ledgix Supplier;
- Ledgix Price List;
- Ledgix Item Price;
- Ledgix Payment Method;
- Ledgix Sale;
- Ledgix Purchase;
- Ledgix Sales Return;
- Ledgix POS Shift;
- Ledgix POS Hold;
- Ledgix Payment;
- Ledgix Stock Movement;
- Ledgix Stock Lot;
- Ledgix Stock Serial.

When the retirement state is Frozen, document-event guards prevent ordinary insert/save/submit/cancel/delete behavior.

Their physical presence does not make them active authority.

### Retired tax/FBR source models

The old mixed monetary-tax/FBR architecture was retired more aggressively. Current documentation must distinguish this from the frozen business-history strategy.

Old Tax Profile/Category/Rate/Item Tax Profile/global FBR Settings are not current configuration authority.

Historical audit/detail records may remain as evidence, but current runtime must not resurrect the retired engine.

### Compatibility identifiers

Current services may resolve legacy IDs into migrated ERPNext records.

This supports historical clients/data and migration traceability.

It does not authorize a new legacy write.

---

## 17. Reporting architecture

Ledgix may expose focused reports and intelligence surfaces, but the underlying values must originate from ERPNext-native documents and ledgers.

Examples of native authorities include:

- Stock Balance;
- Stock Ledger;
- Accounts Receivable;
- General Ledger;
- Profit and Loss;
- ERPNext purchase/sales documents;
- native stock valuation/accounting entries.

Compatibility reporting adapters are acceptable when they translate native data into a stable Ledgix UI contract.

A report adapter must not become a hidden duplicate database of business truth.

---

## 18. Installation and migration model

Current installations require ERPNext.

A supported Ledgix site is not created as an independent custom ERP system.

Installation/migration logic may:

- install/synchronize Ledgix custom fields;
- synchronize permissions;
- register product workspace/surfaces;
- install print formats;
- apply safe schema extensions;
- enforce historical retirement boundaries;
- run explicit registered cleanup where the required safety authorization exists.

It must not:

- fork ERPNext core;
- revive retired Ledgix financial/stock engines;
- create a second accounting schema as the normal business authority;
- silently enable FBR Production;
- fabricate certification evidence.

Historical phase-named setup/migration modules remain part of repository lineage until a separate cleanup proves they are no longer required by hooks, patches, upgrades, tests, rollback or audit evidence.

---

## 19. Deployment and multi-site model

Ledgix follows Frappe site isolation.

A typical SaaS deployment can use:

    one approved application release
        |
        +-- client-a site -> independent DB / configuration / credentials
        +-- client-b site -> independent DB / configuration / credentials
        +-- staging site  -> independent DB / configuration / credentials

Each site owns its own:

- ERPNext business data;
- Ledgix Business Profile;
- user/role assignments;
- FBR Integration Profile and credentials;
- FBR evidence;
- release/readiness evidence;
- backups.

A shared bench means application code is shared by every tenant on that bench. Updating code for one site can therefore affect the cohort, which is why shared-bench release operations require an explicit cohort-safe update process.

Large clients can move to dedicated infrastructure without changing the application architecture.

---

## 20. Backup, restore and release boundary

Architecture readiness is not the same as release approval.

Production operations require verified recovery capability and an explicitly approved release.

Key principles:

- a fresh verified backup is required before production-changing operations;
- rollback should use a known-good data/release pair;
- schema downgrade must not be assumed safe;
- historical retirement evidence must remain valid after restore;
- release identity must be explicit rather than an uncontrolled moving branch;
- shared benches require cohort-aware release handling;
- FBR Production activation is a separate compliance/go-live decision from normal Ledgix deployment.

Dedicated deployment, backup and release documents define the operational commands and gates.

---

## 21. Testing and evidence model

Ledgix uses several kinds of evidence. They should never be conflated.

### Static/unit/contract tests

These prove source-level contracts and local behavior.

### Local runtime gates

These prove behavior against the configured local ERPNext/Frappe environment.

### Rollback-confirmed transactional gates

These may exercise database behavior while ensuring the test transaction does not remain persisted.

### Operating/acceptance dataset

The local realistic dataset provides current ERPNext-native POS, B2B, purchase, inventory, payment and return acceptance coverage.

### Manual/device UAT

Physical printers, scanners, terminals and business workflow acceptance require real manual evidence where applicable.

### Real FBR Sandbox evidence

Only genuine authorized Sandbox validate/POST evidence can satisfy the implemented Sandbox certification contract.

### Production evidence

Production readiness additionally depends on genuine client/provider/legal prerequisites, release/backup state, explicit authorization and unresolved-reconciliation state.

The final forensic audit recorded:

- 19/19 focused forensic tests passed;
- 472/472 setup tests passed;
- the user/role integration module passed its active tests with two intentionally retired legacy cases skipped;
- read-only/in-memory FBR runtime gates passed with zero real FBR network calls;
- rollback-confirmed V2 transactional gates passed with no persisted gate invoices.

These results establish software evidence, not external certification.

---

## 22. Known intentional limitations and fail-closed boundaries

The current architecture intentionally does not guess in several areas.

Examples include:

- Production remains inactive until real external/client prerequisites are complete.
- The general V2 network cutover remains disabled at the forensic baseline.
- Mocks/local tests cannot mark Sandbox certification complete.
- Unsupported or unproven FBR payload semantics must fail closed.
- Return/debit-note/credit-note behavior must be verified for the client's real FBR/PRAL path before being represented as certified.
- Known Offline legal allowance/window is not invented by Ledgix.
- Ambiguous Production POST outcomes require reconciliation rather than blind retry.
- Post-FBR cancellation/correction behavior is conservative.
- Final print/QR/legal presentation needs real client/provider verification.
- Legacy historical business models remain frozen evidence until a separate cleanup/retirement decision proves removal safe.

These are safety properties, not unfinished permission to improvise.

---

## 23. Rules for future development

Before adding a new Ledgix DocType, service or ledger for a business concept, answer these questions:

1. Does ERPNext already own this concept?
2. Can the requirement be implemented by configuring/extending ERPNext plus small Ledgix metadata?
3. Is the real requirement a better Ledgix UX over a native ERPNext document?
4. Will this design create a second total, balance, stock quantity, receivable, payable, payment history or accounting truth?
5. Will this design make FBR evidence depend on mutable masters after invoice submission?
6. Does the change weaken a fail-closed Production/Sandbox/reconciliation boundary?
7. Does it require editing ERPNext core?

If the design creates competing financial or stock authority, it is inconsistent with the current architecture.

If the design weakens FBR certification or retransmission safety, it requires explicit redesign and proof rather than a convenience exception.

If the feature requires ERPNext changes, prefer documented Frappe/ERPNext extension mechanisms before considering core modification.

---

## 24. Documentation authority after consolidation

This document owns the high-level current architecture.

The consolidated developer pack will separate detailed concerns into companion documents:

- CODEBASE_AND_EXTENSION_POINTS.md
- BUSINESS_WORKFLOWS.md
- POS_ARCHITECTURE.md
- SALES_RETURNS_AND_PAYMENTS.md
- PURCHASE_AND_INVENTORY.md
- ACCOUNTING_AND_TAX.md
- FBR_ARCHITECTURE.md
- SECURITY_AND_PERMISSIONS.md
- INSTALLATION_AND_CONFIGURATION.md
- DEPLOYMENT_AND_UPGRADES.md
- BACKUP_RESTORE_ROLLBACK.md
- MULTI_SITE_SAAS.md
- TESTING_AND_RELEASE_GATES.md
- MIGRATION_AND_LEGACY_RETIREMENT.md
- TROUBLESHOOTING.md

The client documentation will describe operation and setup without requiring the reader to understand the migration history or internal implementation.

Until consolidation is complete, older documents remain in the repository as source material or historical evidence. Their phase-time status statements must not override this current architecture or the current implementation.

---

## 25. Current source-of-truth summary

For day-to-day engineering decisions, use this order:

1. current repository implementation;
2. this canonical architecture document;
3. dedicated current developer documentation for the specific subsystem;
4. final forensic evidence for the 2026-09-26 baseline;
5. archived migration/redesign documents for historical reasoning only.

The architecture in one sentence is:

> **ERPNext owns business and accounting truth; Ledgix owns the product experience, controlled extensions and FBR compliance/orchestration around ERPNext-native transactions, while historical duplicate Ledgix business records remain non-authoritative evidence and all real FBR Production behavior remains fail-closed until genuine certification and go-live prerequisites are satisfied.**
