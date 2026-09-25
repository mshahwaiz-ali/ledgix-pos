# Ledgix POS — Codebase and Extension Points

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Documentation branch:** docs-consolidation-20260926  
**Companion authority:** docs/developer/ARCHITECTURE.md

## 1. Purpose

This document explains how the current Ledgix codebase is organized, which files are runtime authority, where extension logic belongs, and which parts of the repository are historical or compatibility-oriented.

Read this after ARCHITECTURE.md.

The goal is not to list every file mechanically. The goal is to make the repository understandable to a developer who did not participate in the original Ledgix implementation or ERPNext migration.

The central development rule remains:

> **Extend ERPNext through documented Frappe/ERPNext extension points; do not create a second business engine or modify ERPNext core to implement normal Ledgix features.**

When filenames, historical phase names, package metadata or old migration files appear to conflict with current behavior, determine runtime authority from:

1. current hooks and registered patches;
2. current API/service implementation;
3. current DocType/Page/Report metadata;
4. current tests and release gates;
5. canonical developer documentation;
6. historical migration material only for background reasoning.

---

## 2. Repository layout

At the repository level, Ledgix is organized approximately as:

    ledgix-pos/
    ├── README.md
    ├── apps/
    │   └── ledgix_saas/
    ├── deploy/
    ├── docs/
    ├── scripts/
    ├── install.sh
    ├── site_setup.sh
    ├── start.sh
    └── inspection2.md

The active custom Frappe application lives in:

    apps/ledgix_saas/

Important operational/supporting locations outside the app include:

| Location | Purpose |
|---|---|
| deploy/ | production provisioning, backup, update, restore and deployment helpers |
| scripts/ | validation, release gates, local acceptance and historical migration/FBR gates |
| docs/ | current and historical project documentation |
| install.sh | supported repository/local installation entrypoint |
| site_setup.sh | supported local site setup/ensure/reset flow |
| start.sh | local runtime helper |
| inspection2.md | final forensic audit evidence for the 2026-09-26 baseline |

The deploy/ and scripts/ directories are operational tooling, not application-domain layers.

---

## 3. Application package layout

The current app root is:

    apps/ledgix_saas/

Its main areas are:

    apps/ledgix_saas/
    ├── api/
    ├── config/
    ├── docs/
    ├── fixtures/
    ├── ledgix/
    │   ├── doctype/
    │   ├── page/
    │   ├── print_format/
    │   └── report/
    ├── migration/
    ├── patches/
    ├── public/
    ├── services/
    ├── setup/
    ├── templates/
    ├── www/
    ├── hooks.py
    ├── modules.txt
    ├── patches.txt
    ├── pyproject.toml
    └── validation.py

### Directory responsibilities

| Area | Responsibility |
|---|---|
| api/ | whitelisted APIs, compatibility endpoints, UI-facing orchestration and controlled actions |
| services/ | business/compliance service boundaries, especially ERPNext-native transaction services |
| setup/ | idempotent installation/migrate synchronization, permissions, print formats, local setup and tests |
| migration/ | migration-era probes, preflights, gates and controlled transition tooling |
| patches/ | registered Frappe database/application patches |
| ledgix/doctype/ | Ledgix DocType schema/controllers that still exist physically |
| ledgix/page/ | retained custom Ledgix Desk Pages |
| ledgix/report/ | Ledgix reports/adapters exposed through Frappe reporting |
| ledgix/print_format/ | Ledgix-managed print formats/templates |
| fixtures/ | exported repository-owned roles/workspace/custom metadata |
| public/ | browser assets loaded by Frappe |
| templates/ | Jinja/web templates |
| www/ | web routes/pages |
| hooks.py | live app integration contract with Frappe/ERPNext |
| patches.txt | ordered registered patch execution list |
| pyproject.toml | package/dependency/build metadata |
| validation.py | read-only smoke/installation validation |

---

## 4. Dependency contract

pyproject.toml declares the Frappe/ERPNext compatibility boundary:

    frappe >=15,<16
    erpnext >=15,<16

hooks.py also declares:

    required_apps = ["erpnext"]

Therefore the current Ledgix application is an ERPNext-dependent Frappe app.

A Frappe-only installation with Ledgix pretending to own Items, Customers, Sales, Purchasing, Stock and Accounting is not the supported architecture.

### Do not infer active features from package declarations alone

pyproject.toml contains explicit Python package declarations accumulated over the project's history.

Some declarations still name historical packages that have since been physically retired, including former Ledgix tax configuration models.

The source tree and runtime hooks are more authoritative than a historical packaging entry when determining whether a feature is live.

Do not reintroduce a retired DocType merely to make an old package name appear consistent.

Package-metadata cleanup belongs to the later repository-cleanup phase and must be performed only after verifying build, import, migration and packaging behavior.

---

## 5. hooks.py — the primary runtime map

hooks.py is the best single source for understanding how Ledgix attaches itself to Frappe/ERPNext.

A developer changing architecture-level behavior should inspect hooks.py before adding a new integration mechanism.

It currently defines:

- ERPNext as a required application;
- Desk and web assets;
- Jinja helper functions;
- after-migrate synchronizers;
- boot-info/product-shell extensions;
- whitelisted-method compatibility overrides;
- Payment Entry validation;
- Sales Invoice and POS Invoice FBR events;
- legacy write guards;
- scheduler policy;
- fixtures.

Each category is discussed below.

---

## 6. Frontend asset extension points

hooks.py loads Ledgix assets through standard Frappe app hooks.

Current global Desk assets include:

- public/css/ledgix_brand.css
- public/css/ledgix_v2_tokens.css
- public/js/ledgix_brand.js
- public/js/ledgix_sidebar_brand.js
- public/js/ledgix_phase10_native_surfaces.js
- public/js/ledgix_phase11_product_shell.js
- public/js/ledgix_taxable_base.js

Web branding assets are also registered through web_include_css/web_include_js.

### When to use global app assets

Use a global asset only when behavior genuinely applies across the relevant Ledgix/Frappe surface.

Do not place page-specific business logic into a global include simply because it is convenient.

Page-specific UI logic should live beside the Page implementation where possible.

### Naming note

Some browser assets retain historical phase names.

A phase number in a filename does not make the file historical if hooks.py still loads it.

Runtime registration is the deciding factor.

---

## 7. Jinja and print extension points

hooks.py exposes Jinja helpers for:

- splash/branding image resolution;
- print logo resolution;
- FBR QR data URI generation;
- ERPNext-native invoice print context.

This is an appropriate extension point for presentation-only functionality.

### Rule

Jinja helpers may prepare display context.

They must not become a hidden transaction or accounting engine.

A print helper should read authoritative invoice/compliance evidence, not mutate business state.

---

## 8. after_migrate extension model

The after_migrate hook runs a sequence of Ledgix synchronization functions.

The current chain includes:

- ERPNext extension schema;
- ERPNext-native tax foundation;
- master/schema extensions introduced during migration phases;
- selling/buying/POS/FBR extensions;
- print formats;
- optimized permission synchronization;
- product-shell synchronization;
- final legacy-retirement enforcement.

### Why historical phase names remain

Several modules are named:

    erpnext_phase5_extensions.py
    erpnext_phase6_extensions.py
    erpnext_phase7_extensions.py
    erpnext_phase8_extensions.py
    erpnext_phase9_extensions.py
    erpnext_phase10_print_formats.py
    erpnext_phase11_product_shell.py
    erpnext_phase12_legacy_retirement.py

Those names describe when the logic entered the system.

They do not mean the application is currently executing an unfinished Phase 5–12 project.

Some of this logic remains necessary on every migrate because it synchronizes the current schema/permissions/product shell or preserves retirement state.

### Requirements for new after_migrate code

New after-migrate functionality should normally be:

- deterministic;
- idempotent;
- safe to execute repeatedly;
- bounded to configuration/schema synchronization;
- explicit about destructive behavior;
- safe on fresh sites and upgraded sites;
- covered by tests;
- ordered carefully relative to permission and retirement logic.

Do not use after_migrate to:

- create arbitrary client business transactions;
- fabricate certification evidence;
- enable FBR Production;
- rewrite accounting;
- silently destroy historical evidence.

---

## 9. API layer

The api/ package is broad because it contains both current orchestration and compatibility surfaces.

At the current baseline it contains around four dozen Python modules.

Do not treat every module under api/ as equally authoritative.

A useful classification is below.

### 9.1 Current product/control APIs

Examples:

- api/client_setup.py
- api/client_readiness.py
- api/product_shell.py
- api/brand.py
- api/printing.py
- api/report_adapters.py
- api/release_acceptance.py
- api/security.py

These expose current Ledgix product behavior.

### 9.2 Current ERPNext-native/FBR V2 APIs

Examples:

- api/fbr_native.py
- api/fbr_v2_center.py
- api/fbr_v2_transport.py
- api/fbr_reference_v2.py
- api/fbr_activation.py
- api/fbr_offline.py
- api/fbr_health.py
- api/fbr_client.py

These belong to the current FBR compliance/orchestration architecture.

### 9.3 Compatibility APIs

Examples:

- api/pos_compat.py
- api/selling_compat.py
- api/inventory_intelligence_native.py

They preserve external/UI contracts while translating them to current ERPNext-native services.

Compatibility is a supported architecture technique.

Compatibility does not mean the old storage model is still authoritative.

### 9.4 Historical/retired API modules

The source tree still contains files such as older POS, selling, FBR, taxation or business-intelligence implementations.

Examples include:

- api/business_intelligence.py
- api/pos.py
- api/selling.py
- api/fbr_payload.py
- api/fbr_submission.py
- api/fbr_transport.py
- api/taxation.py

Some remain for historical compatibility, guarded behavior, import stability or audit value.

hooks.py redirects important externally reachable old methods to:

- ERPNext-native compatibility services; or
- explicit fail-closed retirement guards.

Do not call an old module directly simply because the file still exists.

Inspect the hook override and current service boundary first.

---

## 10. Service layer

The services/ package is the preferred home for reusable domain/service logic.

Current modules can be divided into three groups.

### 10.1 ERPNext-native transaction services

Primary examples:

- services/erpnext_pos.py
- services/erpnext_selling.py
- services/erpnext_buying_inventory.py
- services/erpnext_payment_policy.py
- services/erpnext_reporting.py
- services/erpnext_reporting_compat.py

These services coordinate Ledgix-specific workflow requirements while preserving native ERPNext authority.

### 10.2 ERPNext tax/FBR evidence services

Primary examples:

- services/erpnext_tax_authority.py
- services/erpnext_taxable_base.py
- services/erpnext_fbr_identity.py
- services/erpnext_fbr_snapshot.py
- services/fbr_v2_snapshot_persistence.py
- services/fbr_v2_readiness.py
- services/fbr_v2_payload_builder.py
- services/fbr_submission_support.py
- services/fbr_v2_status.py

These implement the FBR V2 compliance boundary.

They must consume ERPNext evidence rather than calculate a parallel accounting result.

### 10.3 Historical service modules

The repository also retains older generic services such as:

- services/sales.py
- services/payments.py
- services/receivables.py
- services/pricing.py
- services/stock.py
- services/tax.py

A file's presence alone does not prove that it is current transaction authority.

Before reusing one, trace:

1. its imports/callers;
2. hook overrides;
3. current compatibility layer;
4. tests;
5. migration/retirement status.

The later repository-cleanup phase will assess whether retained historical source remains necessary.

---

## 11. Preferred service-extension pattern

When adding current business functionality, prefer this shape:

    Page / UI
        |
        v
    whitelisted API
        |
        v
    Ledgix service boundary
        |
        v
    ERPNext native document/API
        |
        v
    ERPNext ledger / business state

For FBR:

    ERPNext submitted invoice
        |
        v
    Ledgix snapshot/readiness service
        |
        v
    payload builder
        |
        v
    controlled transport API
        |
        v
    submission log/status/reconciliation evidence

### Why this shape matters

It keeps:

- UI concerns separate from transaction logic;
- permissions enforceable server-side;
- ERPNext business authority intact;
- FBR logic auditable;
- compatibility logic explicit;
- tests targeted at well-defined boundaries.

---

## 12. Desk Pages

Current source directories include four custom Page implementations:

- business_intelligence_center
- ledgix_pos
- ledgix_setup
- ledgix_tax_center

Their roles differ.

### Ledgix POS

This is the focused selling experience over ERPNext-native POS/B2B services.

The Page should remain a UI/workflow layer.

It must not create a new Ledgix sale/payment/stock authority.

### Tax & FBR Center

The current Tax & FBR Center is explicitly ERPNext-native.

Its UI states that:

- ERPNext owns monetary tax and accounting;
- Ledgix manages FBR classification, reference data, certification and readiness.

It calls V2 APIs for:

- boot/context;
- item mappings;
- official reference sync;
- invoice readiness;
- Known Offline queue/declaration/upload.

The page intentionally contains no generic Production invoice-submit action.

### Setup Wizard

The setup Page calls client_setup/client_readiness APIs.

Its role is configuration and readiness.

It should not become an automatic business-master generator or a Production activation shortcut.

### Business / Inventory Intelligence

The business-intelligence surface is retained as a product UX.

Current data authority should remain ERPNext-native through the reporting adapters/services.

---

## 13. Product shell and navigation extension point

api/product_shell.py controls product navigation, not security.

It computes role/profile-aware visibility for:

- workspace cards;
- links;
- shortcuts;
- landing route;
- curated sidebar behavior.

Current Business Profile feature flags may hide/show product areas.

### Critical rule

Visibility is not authorization.

If a link is visible, the target DocType/Page/API still requires appropriate Frappe permissions and server-side authorization.

Do not add a permission-sensitive feature by editing only product_shell.py.

The correct implementation usually requires:

1. navigation policy;
2. Page/DocType/Report role configuration;
3. API permission enforcement;
4. tests.

---

## 14. Security helper extension point

api/security.py centralizes simple Ledgix role checks for:

- cashier-or-above;
- manager-or-above;
- admin/System Manager.

This helper can be used for Ledgix product APIs where those exact role groups are appropriate.

Do not overgeneralize it.

For sensitive features—especially FBR Production actions—use the subsystem's stricter evidence and permission rules in addition to role checks.

A user having Ledgix Admin or System Manager is not, by itself, authorization to bypass certification/readiness interlocks.

---

## 15. Permission synchronization

setup/permissions.py defines the broad Ledgix permission policy.

setup/fast_permissions.py is the optimized post-migrate executor that avoids unnecessary rewrites when permissions already match.

Important responsibilities include:

- Custom DocPerm synchronization;
- Page roles;
- report roles;
- role home pages;
- workspace roles;
- retirement of obsolete pages/roles;
- limited migration of old presentation settings.

### Why two modules exist

permissions.py is the policy/source definition.

fast_permissions.py applies that policy more efficiently during migrate.

New permission policy should be defined centrally rather than scattered across unrelated setup scripts.

### Legacy permission caveat

permissions.py still contains policy entries for historical Ledgix business DocTypes because those DocTypes may physically remain as frozen evidence.

The later Phase 12 retirement hook ensures the effective runtime state remains read-only/frozen where required.

Do not interpret a historical permission-row definition in isolation from the retirement guard.

---

## 16. DocType layer

The current source tree contains roughly forty Ledgix DocType directories.

They are not all active business entities.

For understanding the codebase, classify them by role.

### 16.1 Current product/configuration DocTypes

Examples include:

- Ledgix Brand Settings;
- Ledgix Business Profile;
- Ledgix User Profile;
- Ledgix Legacy Retirement State.

These support Ledgix product configuration/metadata.

### 16.2 Current FBR/compliance DocTypes

Examples include:

- Ledgix FBR Integration Profile;
- Ledgix FBR Business Nature;
- Ledgix FBR Item Mapping;
- Ledgix FBR Tax Component Mapping;
- Ledgix FBR Reference Data;
- Ledgix FBR Sandbox Scenario;
- Ledgix FBR Sandbox Certification;
- Ledgix FBR Submission Log;
- Ledgix FBR Correction Request.

These extend ERPNext with FBR-specific compliance evidence and workflow.

### 16.3 Historical frozen business DocTypes

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

These may remain physically present for historical/audit/migration reasons.

They must not be used to implement new current business behavior.

### 16.4 Historical tax evidence DocTypes

Examples include:

- Ledgix Tax Audit Log;
- Ledgix Invoice Tax Detail;
- Ledgix Return Tax Detail.

These are evidence/history boundaries rather than the current monetary tax engine.

---

## 17. Adding a new DocType

Before adding a new Ledgix DocType, answer:

1. Does ERPNext already have an authoritative model for this concept?
2. Is this actually product configuration/compliance metadata rather than a business ledger?
3. Could a Custom Field or child field on the native ERPNext document solve the problem?
4. Would the new DocType create a second balance, quantity, invoice, payment or accounting truth?
5. Does the data need independent lifecycle/permissions/auditability?
6. Is it site-wide, Company-scoped, transaction-scoped or user-scoped?
7. How will fresh install, migrate, backup, restore and multi-site isolation behave?
8. What permission policy and tests are required?

A new duplicate commercial ledger should normally be rejected.

A tightly scoped Ledgix configuration/evidence DocType may be appropriate.

---

## 18. Reports

Current Ledgix report directories include:

- inventory_intelligence_report;
- ledgix_current_stock;
- ledgix_customer_statement;
- ledgix_item_full_cycle;
- ledgix_low_stock;
- ledgix_purchase_report;
- ledgix_sales_report;
- ledgix_sales_return_report;
- ledgix_stock_movement_report.

Some report names predate the ERPNext cutover.

The name is not the authority.

A current report should source operational values from ERPNext-native documents/ledgers or current adapters.

### Report extension rule

Prefer:

    report UI/query
        -> ERPNext-native reporting service/query
        -> native documents/ledger

Avoid:

    report UI/query
        -> frozen Ledgix business tables
        -> presented as current stock/sales/accounting

Historical audit reports are a separate use case and should be labeled explicitly if retained.

---

## 19. Print formats

Current print-format source directories include:

- ledgix_b2b_invoice;
- ledgix_erpnext_pos_receipt;
- ledgix_erpnext_tax_invoice;
- ledgix_thermal_receipt.

Names such as thermal_receipt or b2b_invoice may have historical lineage.

For current transactions, print logic must use ERPNext-native invoice authority.

FBR print requirements additionally depend on accepted FBR evidence and real client/provider certification where required.

Do not infer legal certification from a template merely existing in the repository.

---

## 20. Fixtures

hooks.py registers repository-owned fixtures for:

- Ledgix roles;
- Ledgix Workspace;
- Ledgix Custom Fields;
- Ledgix Property Setters.

fixtures/ also contains exported Role and Workspace data.

### Fixture design rule

Use fixtures for stable application-owned metadata that should follow the app.

Do not use fixtures to ship client-specific business data, FBR credentials or live transaction evidence.

### Do not duplicate setup ownership

If metadata is already safely synchronized through an explicit setup/after_migrate service, avoid creating an uncontrolled second synchronization mechanism without a clear reason.

Fixtures and setup code should have intentionally defined ownership.

---

## 21. Patches

patches.txt currently registers post-model-sync application patches.

The registered sequence includes historical schema/data fixes such as:

- tax-rate field rename;
- V2 commerce contract bootstrap;
- payment-method normalization;
- seller snapshot backfill;
- print-format synchronization;
- sale-item identity/receipt synchronization;
- ERPNext extension schema sync;
- retired legacy tax-configuration cleanup.

### Patch rules

A Frappe patch should be:

- versioned;
- deterministic;
- safe to run exactly once under Frappe patch semantics;
- narrowly scoped;
- explicit about destructive actions;
- tested against fresh and upgraded-site expectations where applicable.

A patch is not an ordinary runtime service.

Do not call a data-migration patch from a normal API request.

### Source file vs registered patch

The patches/v1_0 directory may contain patch modules that are not currently listed in patches.txt.

Only the registered patch list determines normal patch execution.

Do not assume every file under patches/ executes automatically.

---

## 22. Setup package

The setup/ package contains a mixture of:

- current synchronization logic;
- acceptance/local-data tooling;
- permission logic;
- recovery helpers;
- FBR operator/setup helpers;
- a large contract/regression test suite.

Important current setup modules include:

- erpnext_extensions.py;
- erpnext_tax_foundation.py;
- erpnext_phase5_extensions.py through phase9 extensions;
- erpnext_phase10_print_formats.py;
- erpnext_phase11_product_shell.py;
- erpnext_phase12_legacy_retirement.py;
- permissions.py;
- fast_permissions.py;
- fbr_sandbox_operator.py;
- fbr_v2_component_mappings.py;
- phase12_read_only.py;
- recovery.py;
- retail_v15_compat.py.

### setup/ is not a dumping ground

Put code here when its primary responsibility is installation, migration synchronization, setup, recovery, validation or test support.

Normal checkout/selling/FBR transaction orchestration should live in api/ or services/.

---

## 23. Migration package

migration/ is large because Ledgix underwent a controlled ERPNext-core migration and later FBR redesign.

It contains:

- capability probes;
- behavioral spikes;
- migration preflights;
- phase gates;
- reconciliation checks;
- FBR redesign gates;
- FBR retirement gates;
- payload/readiness/transport gates.

Most of these files are not day-to-day product services.

### Do not import migration gates casually into runtime code

Migration/gate modules may:

- depend on test fixtures;
- assume controlled local environments;
- perform write-heavy validation;
- exist only for historical proof;
- include rollback logic;
- encode a one-time transition sequence.

Before reusing migration code, determine whether the behavior belongs in a permanent current service instead.

### Why these files are retained now

Documentation consolidation is happening before repository cleanup.

Historical gate files may still provide:

- audit evidence;
- regression contracts;
- upgrade safety;
- rollback reasoning;
- source references for tests;
- proof of previous architectural decisions.

Their cleanup will be a separate dependency-aware project.

---

## 24. validation.py

validation.py exposes a read-only Ledgix application validation entry point.

It checks items such as:

- required roles;
- required DocTypes/fields;
- importability of important current modules;
- scheduler expectations.

The current scheduler expectation explicitly contains no legacy blind retry/offline recovery worker.

### Intended use

Use this kind of validation for smoke/readiness confirmation.

Do not turn a validation method into a repair routine that silently changes production state.

A validator should report truth.

A setup/repair workflow should be explicit and separate.

---

## 25. Public assets and branding

public/ contains:

- brand CSS;
- shared design tokens;
- branding scripts;
- sidebar/product-shell JS;
- taxable-base browser integration;
- Ledgix brand SVG assets.

Brand assets are application resources.

They are distinct from client-supplied regulatory evidence.

For example, a Ledgix logo shipped in public/images is not a substitute for an authoritative FBR Digital Invoicing logo/evidence required by the client's real compliance path.

---

## 26. Configuration vs business data

When deciding where a new value belongs, first classify the data.

### Application configuration

Examples:

- Ledgix brand settings;
- Business Profile;
- feature flags;
- product navigation configuration.

Ledgix may own these.

### ERPNext business master

Examples:

- Item;
- Customer;
- Supplier;
- Warehouse;
- Price List;
- Account.

ERPNext owns these.

### Transaction data

Examples:

- POS Invoice;
- Sales Invoice;
- Purchase Invoice;
- Payment Entry;
- Stock Entry.

ERPNext owns these.

### Compliance metadata/evidence

Examples:

- FBR Item Mapping;
- FBR Integration Profile;
- immutable FBR snapshot;
- Submission Log.

Ledgix may own these because they extend the ERPNext transaction with domain-specific compliance behavior.

This classification prevents schema duplication.

---

## 27. Custom Fields and ERPNext extensions

Ledgix uses ERPNext Custom Fields and related synchronization to attach product/compliance metadata to native documents.

This is preferred when:

- ERPNext remains the lifecycle authority;
- the value naturally belongs to the native record;
- the field does not need a separate independent document lifecycle.

Examples include Ledgix/FBR state on ERPNext invoice structures.

### Good extension

    Sales Invoice
        + custom Ledgix/FBR metadata
        + ERPNext remains invoice authority

### Bad extension

    Sales Invoice
        mirrored into a second Ledgix Invoice
        with separate total/outstanding/payment state

The second pattern recreates the architecture that was retired.

---

## 28. Whitelisted API design

A Ledgix whitelisted method should normally:

1. enforce server-side authorization;
2. validate inputs;
3. resolve Company/site context explicitly;
4. call a reusable service;
5. return a stable response contract;
6. avoid leaking credentials/internal secrets;
7. preserve native transaction semantics;
8. be idempotent where retries are reasonably expected;
9. fail closed for safety-sensitive ambiguity.

### Sensitive FBR methods

For FBR actions additionally:

- do not accept arbitrary tokens from the browser when profile-bound credentials are the authority;
- do not bypass Sandbox certification;
- do not bypass Production arming;
- do not bypass global cutover policy;
- do not silently retransmit an ambiguous POST;
- persist required attempt/evidence state at the correct transaction boundary.

---

## 29. Transaction and commit boundaries

Most Ledgix business APIs should let Frappe manage request transaction boundaries unless a carefully designed safety case requires otherwise.

An explicit commit is unusual and must have a documented reason.

The current Production FBR POST crash-window guard is one such deliberate case:

- durable attempt/reconciliation evidence is written;
- the state is committed;
- only then may the external Production network window occur.

Do not copy this pattern casually into normal business flows.

Explicit transaction management should be justified by a specific failure model.

---

## 30. External network boundary

Ledgix has a very small class of legitimate external network operations, most notably FBR reference/validate/post traffic.

Network-facing code should be isolated from:

- monetary calculation;
- payload construction;
- invoice lifecycle decisions;
- credential storage;
- certification-state evaluation.

For FBR V2 the intended separation is:

    ERPNext invoice
        -> snapshot/readiness
        -> payload builder
        -> transport policy
        -> HTTP call
        -> parsed response
        -> status/log/reconciliation

This makes the network layer testable and prevents HTTP behavior from becoming business authority.

---

## 31. No ERPNext core edits

Ledgix should extend ERPNext using:

- Frappe hooks;
- Custom Fields;
- Property Setters where appropriate;
- whitelisted APIs;
- document events;
- custom Pages/Reports/Print Formats;
- fixtures;
- patches;
- application services;
- standard ERPNext public APIs/document APIs.

Do not patch ERPNext source files in site-packages/apps/erpnext as the normal solution.

A core modification creates:

- upgrade risk;
- tenant inconsistency;
- deployment drift;
- difficult rollback;
- hidden coupling to a specific ERPNext revision.

If native ERPNext lacks a required extension point, document the gap and design the smallest maintainable application-level extension.

---

## 32. Testing placement

Most current regression tests live under setup/ and are named test_*.py.

This is historical repository organization, not a recommendation that all future tests must conceptually be "setup" tests.

When extending the application:

- add focused unit/contract coverage close to the current test convention;
- test hook/permission/static contracts where relevant;
- add runtime gates only when integration behavior genuinely requires a site/database;
- keep real external-network tests explicitly opt-in;
- never make CI/local tests look like genuine FBR certification.

Test naming should describe the contract being protected.

---

## 33. How to trace a feature

When investigating an unfamiliar Ledgix feature, use this sequence.

### Step 1 — Find the UI entry point

Look under:

- ledgix/page/;
- workspace fixture/product shell;
- report/;
- print_format/.

### Step 2 — Find the whitelisted method

Search api/ for the method invoked by the UI.

### Step 3 — Check hook overrides

Before assuming that method executes its own file implementation, inspect hooks.py.

The call may be redirected to a current compatibility service or retirement guard.

### Step 4 — Find the service boundary

Trace from API to services/.

Determine which ERPNext DocType/API is actually authoritative.

### Step 5 — Identify document events

If the feature touches Sales Invoice, POS Invoice, Payment Entry or frozen legacy DocTypes, inspect hooks.py doc_events.

### Step 6 — Inspect setup/migration ownership

If fields/permissions/schema are involved, inspect setup/, patches.txt and relevant patch modules.

### Step 7 — Read tests

Tests often encode fail-closed and migration boundaries that are easy to miss by reading only the happy path.

### Step 8 — Read historical docs last

Use migration phase documents to understand why a design exists, not to override current code.

---

## 34. How to add a feature safely

For a normal new feature, use this decision sequence.

### A. Define authority

Identify the authoritative ERPNext or Ledgix object.

If the feature changes a business balance/transaction, ERPNext will usually be the authority.

### B. Define the service

Place reusable logic in services/.

Avoid embedding substantial transaction logic directly in browser JavaScript or a whitelisted wrapper.

### C. Define API boundary

Create/extend a whitelisted method only where the UI or external consumer needs one.

Enforce server-side authorization.

### D. Define UI

Add product-shell/page/report integration without treating visibility as permission.

### E. Define metadata

Use Custom Fields or a Ledgix-specific configuration/evidence DocType only when justified.

### F. Define installation/migration

If schema/configuration must be synchronized, use idempotent setup or a registered patch with explicit upgrade behavior.

### G. Define tests

Cover:

- authority;
- permissions;
- idempotency;
- failure behavior;
- migration/fresh-site behavior if relevant;
- legacy non-regression if the area overlaps retired code.

### H. Define documentation

Update the canonical subsystem document, not an old phase plan.

---

## 35. Anti-patterns

The following patterns are inconsistent with the current architecture.

### Parallel invoice engine

Creating a new Ledgix transaction that duplicates a Sales Invoice/POS Invoice total, outstanding amount and settlement lifecycle.

### Parallel stock ledger

Maintaining current quantity in Ledgix Stock Movement/Lot/Serial records independently of ERPNext Stock Ledger/Bin.

### UI-only permission

Showing/hiding a button without server-side authorization.

### Direct call into retired code

Importing an old legacy module because its function appears convenient while hooks intentionally redirect that public contract elsewhere.

### Unregistered migration assumption

Assuming a file under patches/ or migration/ runs automatically.

### Mutable historical FBR reconstruction

Building a legal payload later from current Item/Customer/tax masters instead of the persisted source snapshot/evidence.

### Blind network retry

Automatically retrying an ambiguous Production POST.

### Core patching

Editing ERPNext core source to avoid implementing a clean Ledgix extension.

### Test-driven accounting mutation

Changing accounting configuration/data merely so a historical Ledgix expectation passes.

---

## 36. Historical names in current code

The repository contains many names like:

- phase8;
- phase9;
- phase10;
- legacy;
- v2;
- compat.

Do not classify code by filename alone.

Use these questions:

1. Is the module imported by current hooks/services?
2. Is it registered in patches.txt?
3. Is it referenced by current DocType events?
4. Is it exercised by current regression tests?
5. Is it a compatibility boundary?
6. Is it intentionally fail-closed?
7. Is it retained only as historical evidence?

A "legacy" guard can be an important current runtime control.

A "phase10" asset can still be actively loaded.

A generic-looking services/tax.py can be historical while erpnext_tax_authority.py is current.

Runtime wiring wins.

---

## 37. Repository cleanup boundary

This documentation effort does not authorize source deletion.

After documentation consolidation, cleanup will separately inspect:

- historical API/service files;
- stale package declarations;
- migration probes/gates;
- old scripts;
- unused reports/print formats;
- obsolete public assets;
- duplicate setup helpers;
- generated evidence/artifacts.

Before deleting any candidate, verify:

- imports;
- hook references;
- patches;
- migration/upgrade dependencies;
- tests;
- rollback/audit value;
- documentation links;
- historical-site compatibility.

Do not clean the codebase by age or filename.

---

## 38. Current codebase map for new developers

A new developer should usually begin here:

| Need | Start with |
|---|---|
| Understand overall system | docs/developer/ARCHITECTURE.md |
| Understand runtime wiring | apps/ledgix_saas/hooks.py |
| POS transaction path | api/pos_compat.py + services/erpnext_pos.py |
| B2B sales/returns | api/selling_compat.py + services/erpnext_selling.py |
| Buying/stock | services/erpnext_buying_inventory.py |
| Monetary tax | services/erpnext_tax_authority.py |
| FBR seller identity | services/erpnext_fbr_identity.py |
| FBR immutable snapshot | services/fbr_v2_snapshot_persistence.py |
| FBR readiness | services/fbr_v2_readiness.py |
| FBR payload | services/fbr_v2_payload_builder.py |
| FBR transport | api/fbr_v2_transport.py |
| FBR orchestration/status | api/fbr_native.py |
| Official FBR references | api/fbr_reference_v2.py |
| Known Offline | api/fbr_offline.py |
| Client setup | api/client_setup.py |
| Client readiness | api/client_readiness.py |
| Navigation/profile behavior | api/product_shell.py |
| Permission policy | setup/permissions.py |
| Efficient permission sync | setup/fast_permissions.py |
| ERPNext extension schema | setup/erpnext_extensions.py and related current synchronizers |
| Legacy freeze | api/legacy_retirement.py + setup/erpnext_phase12_legacy_retirement.py |
| Registered upgrade patches | patches.txt |
| Read-only smoke validation | validation.py |
| Final forensic evidence | inspection2.md |

---

## 39. Code ownership summary

The repository is easiest to reason about using four ownership classes.

### Current runtime

Files actively wired into hooks, current Pages/APIs/services, DocTypes, reports, print formats, setup and production operation.

### Compatibility runtime

Files that preserve old RPC/UI contracts while routing into current ERPNext-native implementation or explicit retirement guards.

### Upgrade/migration runtime

Files used by after_migrate, registered patches, upgrade checks or still-supported historical-site transitions.

### Historical/audit evidence

Files retained because they explain/prove the previous migration or architecture but are not normal application runtime.

A later cleanup may move/remove items only after proving the ownership class accurately.

---

## 40. Extension checklist

Before merging a code change, confirm:

- [ ] ERPNext remains authoritative for standard business/accounting concepts.
- [ ] No duplicate stock/payment/receivable/accounting truth was introduced.
- [ ] The correct service layer is used.
- [ ] API authorization is server-side.
- [ ] Business Profile visibility is not treated as permission.
- [ ] hooks.py changes are necessary and documented.
- [ ] after_migrate logic is idempotent.
- [ ] patches are registered only when intended.
- [ ] fresh install and upgrade behavior are considered.
- [ ] legacy frozen data remains protected.
- [ ] no ERPNext core source is modified.
- [ ] FBR credentials/evidence remain protected.
- [ ] FBR ambiguity fails closed.
- [ ] tests cover the new contract.
- [ ] canonical current documentation is updated.
- [ ] Production enablement is not silently changed.

---

## 41. Source-of-truth rule

For repository structure and extension decisions, use:

1. hooks.py for runtime registration;
2. current API/service code for behavior;
3. DocType/Page/Report/Print metadata for schema/UI definition;
4. patches.txt for normal patch execution;
5. current setup code for install/migrate synchronization;
6. current tests/gates for protected contracts;
7. canonical developer documentation for explanation;
8. archived migration material for history.

The codebase in one sentence is:

> **Ledgix is a Frappe application whose current APIs, services, Pages and compliance DocTypes extend ERPNext-native business authority; hooks, setup synchronizers and explicit compatibility guards keep that boundary enforceable while historical migration code and frozen Ledgix business models remain available only where upgrade, audit or compatibility requirements still justify them.**
