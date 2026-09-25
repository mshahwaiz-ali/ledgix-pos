# FBR / Tax Redesign — Phase 0 Baseline Inventory

**Status:** STATIC REPOSITORY BASELINE COMPLETE — RUNTIME DATA EVIDENCE PENDING  
**Date:** 2026-09-23  
**Repository:** `mshahwaiz-ali/ledgix-pos`  
**Branch:** `main`  
**Baseline HEAD inspected:** `3bf0f44d2d8224f01592e9741f9753dcec0042ec`  
**Parent plan:** `docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`

---

## 1. Purpose

This document is the Phase 0 dependency and retirement inventory for the ERPNext-native tax + FBR redesign.

It answers four questions before implementation starts:

1. What is currently active in the invoice / POS / FBR runtime?
2. Which components are safe to keep?
3. Which components must be rewritten, migrated, retired, or deleted later?
4. In what order can the old tax/FBR architecture be removed without breaking current ERPNext transaction authority, historical records, FBR audit evidence, or compatibility entrypoints?

This inventory is intentionally conservative.

No old tax/FBR source file or DocType should be physically removed only because it appears obsolete. Removal occurs only after its active dependencies are extracted/replaced and runtime evidence confirms that no current site data requires it.

---

## 2. Phase 0 result

### Confirmed

The current Ledgix transaction authority is ERPNext, but the current tax calculation authority is **not yet purely ERPNext-native**.

Both current selling paths actively call the Ledgix tax foundation:

```text
Ledgix POS
  -> services/erpnext_pos.py
  -> erpnext_tax_foundation.apply_tax_plan(...)
  -> ERPNext calculate_taxes_and_totals()
```

and:

```text
Ledgix B2B / Sales Invoice
  -> services/erpnext_selling.py
  -> erpnext_tax_foundation.apply_tax_plan(...)
  -> ERPNext calculate_taxes_and_totals()
```

Native return creation also re-applies the same Ledgix tax plan before submit.

Therefore the old tax implementation is **active runtime**, not merely historical code.

### Also confirmed

The current FBR native adapter is already attached to submitted ERPNext:

- `Sales Invoice`
- `POS Invoice`

and already protects against submitting POS Closing consolidation Sales Invoices as a second FBR source.

That native transaction cutover should be preserved.

---

## 3. Current runtime dependency graph

### 3.1 Retail POS sale

```text
POS UI / compatibility API
  -> apps/ledgix_saas/api/pos_compat.py
  -> apps/ledgix_saas/services/erpnext_pos.py
  -> ERPNext item/pricing normalization
  -> erpnext_tax_foundation.apply_tax_plan()
      -> Ledgix Item Tax Profile
      -> Ledgix Tax Category
      -> Ledgix-configured Company tax accounts
      -> Ledgix tax calculations
      -> managed ERPNext Sales Taxes and Charges rows
      -> immutable Ledgix FBR snapshot JSON
  -> ERPNext calculate_taxes_and_totals()
  -> ERPNext POS Invoice
  -> submit
  -> hooks.py POS Invoice on_submit
  -> fbr_native.on_native_invoice_submit()
  -> FBR readiness / payload / transport
```

### 3.2 B2B / Sales Invoice

```text
B2B / compatibility API
  -> apps/ledgix_saas/api/selling_compat.py
  -> apps/ledgix_saas/services/erpnext_selling.py
  -> ERPNext item/pricing normalization
  -> erpnext_tax_foundation.apply_tax_plan()
  -> ERPNext calculate_taxes_and_totals()
  -> ERPNext Sales Invoice
  -> submit
  -> hooks.py Sales Invoice on_submit
  -> fbr_native.on_native_invoice_submit()
```

### 3.3 Native return

```text
ERPNext return mapper
  -> services/erpnext_selling.py
  -> select requested return rows
  -> erpnext_tax_foundation.apply_tax_plan()
  -> insert / submit ERPNext return invoice
  -> native FBR hook
```

### 3.4 Native FBR payload

```text
submitted ERPNext invoice
  -> fbr_native.py
  -> custom_ledgix_fbr_snapshot_json on each invoice line
  -> fbr_payload.py shared/private payload helpers
  -> fbr_settings.py
  -> fbr_client.py
  -> FBR API
  -> fbr_submission.py shared response parser / log / lock helpers
  -> Ledgix FBR Submission Log
  -> ERPNext invoice FBR status/reference fields
```

This graph explains why old files cannot be deleted at the beginning of the redesign.

---

## 4. Critical current authority conflicts

### 4.1 `erpnext_tax_foundation.py` is active tax authority

File:

`apps/ledgix_saas/setup/erpnext_tax_foundation.py`

Current responsibilities include:

- resolving `Ledgix Item Tax Profile`;
- resolving `Ledgix Tax Category.default_rate`;
- calculating ordinary sales tax;
- calculating inclusive tax;
- calculating Third Schedule basis;
- calculating Extra Tax;
- calculating Further Tax;
- calculating FED;
- calculating sales tax withheld snapshot amount;
- mapping Ledgix tax component accounts from Company custom fields;
- inserting/replacing managed ERPNext tax rows;
- writing immutable FBR line/header snapshot JSON.

This is the primary active component to replace in Phase 1/4.

### 4.2 Checkout explicitly calls the custom tax plan

Active call sites:

- `apps/ledgix_saas/services/erpnext_pos.py`
- `apps/ledgix_saas/services/erpnext_selling.py`

These cannot simply remove `apply_tax_plan()` until native ERPNext Tax Category / Tax Rule / templates / Item Tax Template configuration is proven to produce the correct transaction.

### 4.3 `api/taxation.py` remains a second tax engine

File:

`apps/ledgix_saas/api/taxation.py`

It owns the older Ledgix-side concepts:

- Ledgix Tax Profile;
- Ledgix Tax Category;
- Ledgix Tax Rate;
- effective date/rate resolution;
- category/item fallback;
- inclusive/exclusive calculation;
- item mapping validation;
- legacy sale tax snapshots.

This module must not remain an active financial authority after cutover.

### 4.4 `services/tax.py` is another legacy tax calculation path

File:

`apps/ledgix_saas/services/tax.py`

It imports the old `api.taxation` engine and calculates:

- ordinary sales tax;
- notified retail price basis;
- Further Tax;
- Extra Tax;
- FED;
- withholding snapshot;
- legacy `Ledgix Sale` tax detail rows.

This is a legacy-business path and should not be reused for the new architecture.

### 4.5 Company contains parallel Ledgix tax-account mapping

Created by:

`apps/ledgix_saas/setup/erpnext_tax_foundation.py`

Current Company custom fields include Ledgix mappings for:

- Sales Tax Payable;
- Extra Tax Payable;
- Further Tax Payable;
- FED Payable;
- reserved Sales Tax Withheld.

Target design: native ERPNext tax templates/accounting configuration owns the financial account mapping. These custom fields become migration inputs / legacy data and should be removed from active setup after cutover.

### 4.6 Item Group also carries obsolete tax defaults

Created by:

`apps/ledgix_saas/setup/erpnext_phase5_extensions.py`

Current native `Item Group` custom fields include:

- `custom_ledgix_tax_defaults_enabled`;
- `custom_ledgix_default_tax_category` -> Ledgix Tax Category;
- `custom_ledgix_default_taxable`;
- `custom_ledgix_default_sales_type`;
- `custom_ledgix_default_uom_for_fbr`;
- `custom_ledgix_default_scenario_id`.

The tax-authority fields and item-level Sandbox scenario default are incompatible with the target architecture.

FBR classification defaults may later be redesigned separately, but they must not point to a duplicate Ledgix tax engine.

---

## 5. FBR native layer dependencies that must be split before deletion

### 5.1 `fbr_native.py`

File:

`apps/ledgix_saas/api/fbr_native.py`

**KEEP CONCEPT / HEAVY REWRITE**

Good responsibilities to preserve:

- ERPNext Sales Invoice / POS Invoice source authority;
- POS consolidation exclusion;
- official FBR status metadata on the native ERPNext source;
- idempotency;
- Production reconciliation lock;
- no blind ambiguous retransmission;
- native invoice hooks.

Current dependencies to replace:

- seller block from old global FBR Settings;
- buyer defaults from old Ledgix Tax Profile;
- monetary FBR rows read from snapshots produced by old Ledgix tax engine;
- Sandbox `scenario_id` read from item snapshots;
- private helpers from `fbr_payload.py`;
- shared log/parser/lock functions imported from legacy-heavy `fbr_submission.py`;
- hardcoded return payload terminology.

### 5.2 `fbr_payload.py`

File:

`apps/ledgix_saas/api/fbr_payload.py`

**SPLIT / REWRITE / DELETE LEGACY PORTIONS LATER**

This file currently mixes:

- legacy `Ledgix Sale` / `Ledgix Sales Return` access;
- old Ledgix tax rows;
- seller/buyer normalization;
- FBR validation helpers;
- official item JSON mapping;
- legacy Sale Invoice payload;
- legacy return payload;
- helpers reused by the native adapter.

Do not delete it wholesale until the reusable helpers are moved into clean V2 modules and `fbr_native.py` stops importing them.

### 5.3 `fbr_submission.py`

File:

`apps/ledgix_saas/api/fbr_submission.py`

**EXTRACT SHARED UTILITIES, THEN RETIRE LEGACY SUBMISSION CODE**

The public legacy sale submit endpoint is already overridden by `hooks.py` to:

`fbr_legacy_guard.reject_legacy_sale_submission`

That is good.

However `fbr_native.py` still imports shared functionality from this large module, including concepts such as:

- FBR response parsing;
- Submission Log creation;
- submission lock;
- ambiguous Production response detection/status resolution.

Therefore this file cannot be deleted until those shared native utilities are extracted to clean V2 modules.

### 5.4 `fbr_settings.py`

File:

`apps/ledgix_saas/api/fbr_settings.py`

**REPLACE THROUGH COMPATIBILITY FACADE**

Current consumers include:

- `fbr_client.py`;
- `fbr_reference.py`;
- `fbr_native.py`;
- `fbr_preflight.py`;
- `fbr_health.py`;
- `fbr_activation.py`;
- Sandbox operator tooling;
- Tax Center UI/API.

Current settings are a global Single and duplicate seller identity.

Target is a Company-scoped integration profile.

Migration should introduce the new profile first, then make old settings APIs resolve through the new profile during transition, then retire the old Single.

### 5.5 `fbr_client.py`

**KEEP / REFACTOR**

Preserve:

- Bearer-token secrecy;
- separate Sandbox/Production operations;
- timeout handling;
- safe error redaction;
- Production arming checks;
- ambiguous response safety.

Refactor toward:

- Company/profile-aware credentials;
- provider/LI transport abstraction if required;
- no dependency on global Single settings.

### 5.6 `fbr_reference.py`

**KEEP IDEA / REWRITE**

Good current direction:

- Province;
- Document Type;
- Transaction Type;
- UOM;
- Sale Type to Rate;
- HS/UOM;
- SRO;
- registration APIs.

Target:

- profile/provider-aware;
- persisted/cached official reference masters;
- controlled Desk selectors instead of free-text;
- freshness/source metadata.

### 5.7 `fbr_activation.py`

**REWRITE**

Current gate is generic successful validate/post proof.

Target gate must use:

- Company;
- Business Nature(s);
- Sector;
- required Sandbox scenarios;
- per-scenario evidence;
- real Sandbox proof;
- Production token/activation prerequisites;
- no unresolved reconciliation;
- release/backup evidence.

### 5.8 `fbr_preflight.py`

**REWRITE**

Current preflight directly imports private `tax_center` helpers and scores:

- Ledgix Item Tax Profile counts;
- HS coverage;
- UOM coverage;
- item-level Sandbox scenario coverage;
- old Tax Profile state.

This is tightly coupled to the old model.

Target readiness must evaluate:

- native ERPNext tax configuration;
- FBR Item Mapping;
- reference-data validity;
- Company FBR profile;
- Sandbox certification scenarios.

### 5.9 `fbr_health.py`

**REFACTOR**

Current health checks know the old global Settings and deliberately disabled retry/offline workers.

Target health should expose:

- Company/profile health;
- provider/reference sync;
- offline queue health;
- reconciliation count;
- credential-configured booleans without secrets.

---

## 6. DocType inventory

### 6.1 KEEP / EVOLVE

#### Ledgix FBR Submission Log

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_submission_log/`

Decision:

**KEEP and evolve.**

Reason:

This is valid compliance/audit state, not a duplicate accounting ledger.

Must eventually distinguish operation/environment and offline/reconciliation context cleanly.

#### Ledgix FBR Correction Request

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_correction_request/`

Decision:

**KEEP / REFACTOR.**

It should remain external correction workflow tracking, never an invented FBR correction API.

### 6.2 REPLACE + MIGRATE

#### Ledgix FBR Settings

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_fbr_settings/`

Decision:

**REPLACE with Company-scoped FBR Integration Profile.**

Migrate:

- token configuration securely;
- software registration identifier;
- legitimate activation state where applicable;
- any verified provider/onboarding information.

Do not blindly preserve duplicated seller identity when ERPNext Company/legal masters should become canonical.

#### Ledgix Item Tax Profile

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_item_tax_profile/`

Decision:

**REPLACE with FBR-only Item Mapping.**

Migrate only verified compliance data such as:

- ERPNext Item link;
- HS code;
- FBR UOM;
- Sale Type;
- SRO fields;
- notified-value metadata where legally required;
- FBR rate/reference description where still needed.

Do not migrate its monetary-tax authority as the new calculation engine.

### 6.3 RETIRE FROM ACTIVE PRODUCT

#### Ledgix Tax Profile

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_tax_profile/`

Decision:

**RETIRE after migration.**

Its current business/tax defaults duplicate ERPNext/FBR-profile responsibilities.

#### Ledgix Tax Category

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_tax_category/`

Decision:

**RETIRE as financial authority.**

Native ERPNext Tax Category / tax templates become financial authority.

#### Ledgix Tax Rate

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_tax_rate/`

Decision:

**RETIRE as financial authority.**

Native ERPNext tax configuration and official FBR reference data replace its active roles.

#### Ledgix Tax Audit Log

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_tax_audit_log/`

Decision:

**KEEP historical rows, retire old-tax CRUD dependency.**

After new architecture, decide whether a new FBR configuration audit log is needed or Frappe Version + compliance evidence is sufficient.

### 6.4 HISTORICAL / DELETE-LATER CANDIDATES

#### Ledgix Invoice Tax Detail

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_invoice_tax_detail/`

#### Ledgix Return Tax Detail

Path:

`apps/ledgix_saas/ledgix/doctype/ledgix_return_tax_detail/`

Decision:

**Historical legacy tax snapshot data.**

Do not use for new ERPNext-native invoices.

Physical removal should be part of a later legacy-schema retirement only after historical `Ledgix Sale` / `Ledgix Sales Return` evidence is no longer dependent on them.

---

## 7. ERPNext custom-field inventory

### 7.1 KEEP / REFACTOR native invoice FBR status fields

Created mainly in:

- `setup/erpnext_extensions.py`;
- `setup/erpnext_phase9_extensions.py`.

Preserve the concept of fields on Sales Invoice / POS Invoice for:

- FBR status;
- official FBR invoice number/reference;
- submitted timestamp;
- error code/message;
- reconciliation-required flag;
- QR/reference metadata;
- Submission Log link;
- immutable snapshot version/data.

These are compliance metadata on the authoritative ERPNext invoice and are valid.

### 7.2 KEEP / REFACTOR buyer FBR fields

Current Customer fields include:

- registration type;
- NTN/CNIC;
- STRN;
- province;
- FBR address;
- verification status/date.

Decision:

**KEEP concept, normalize against ERPNext standard fields and official FBR references.**

Avoid unnecessary duplicate identity where `Customer.tax_id`, Address, or other native/legal data is authoritative.

### 7.3 REFACTOR invoice-line snapshot fields

Current fields include:

- old `Ledgix Item Tax Profile` link;
- HS;
- UOM;
- Sale Type;
- rate description;
- scenario ID;
- SRO;
- tax basis;
- notified value;
- special tax amounts;
- snapshot JSON.

Decision:

**KEEP immutable compliance snapshot concept, change its source.**

Target snapshot source:

- ERPNext native invoice/tax values;
- new FBR Item Mapping;
- new FBR Tax Component Mapping;
- versioned official reference data.

Remove the permanent dependency on old `Ledgix Item Tax Profile`.

Scenario ID must be certification context rather than a permanent production item tax value.

### 7.4 RETIRE Company custom tax account fields

Fields created by `erpnext_tax_foundation.py` should become obsolete after native tax template/account mapping is proven.

Do not remove them until migration compares their existing configured accounts with the new native tax setup.

### 7.5 RETIRE obsolete Item Group tax defaults

The current Item Group fields that point to `Ledgix Tax Category` or permanent Sandbox scenario defaults should be removed from active runtime/UI after new FBR mappings and native tax configuration are live.

---

## 8. Desk/UI inventory

### 8.1 Tax & FBR Center

Files:

- `apps/ledgix_saas/api/tax_center.py`;
- `apps/ledgix_saas/ledgix/page/ledgix_tax_center/ledgix_tax_center.js`;
- `apps/ledgix_saas/ledgix/page/ledgix_tax_center/ledgix_tax_center.css`;
- `apps/ledgix_saas/public/js/ledgix_fbr_native_center.js`.

Decision:

**REWRITE the page/API around native tax + FBR V2.**

Current page explicitly exposes:

- “Tax engine” enabled state;
- Ledgix Tax Profile;
- Ledgix Tax Categories;
- Ledgix Tax Rates;
- Ledgix Item Tax Profiles;
- category rollout into item mappings.

Those are old-architecture surfaces.

Target page:

- native ERPNext Tax Setup links/readiness;
- FBR Integration Profile;
- FBR Item Mapping;
- reference-data sync;
- Sandbox certification;
- live FBR operations;
- Submission Logs;
- corrections;
- offline/reconciliation queues.

### 8.2 Native FBR Center JS patch

`public/js/ledgix_fbr_native_center.js`

Decision:

**KEEP UX concept / rewrite calls.**

Good:

- select native Sales Invoice/POS Invoice;
- payload preview;
- validate;
- explicit Production confirmation.

Refactor for new profile/certification model.

---

## 9. Hooks / migrate inventory

### 9.1 Current after_migrate tax hook

`hooks.py` currently runs:

`ledgix_saas.setup.erpnext_tax_foundation.after_migrate`

This continually provisions the old Company tax-account fields.

Decision:

Remove/replace only after Phase 1/2 migration is implemented.

### 9.2 Native FBR invoice events

Current:

- Sales Invoice `on_submit -> fbr_native.on_native_invoice_submit`;
- POS Invoice `on_submit -> fbr_native.on_native_invoice_submit`;
- before_cancel -> FBR cancellation guard.

Decision:

**KEEP concept.**

Handler internals will change, but ERPNext-native event ownership is correct.

### 9.3 Legacy submission override

Current override:

`ledgix_saas.api.fbr_submission.submit_sale_to_fbr -> fbr_legacy_guard.reject_legacy_sale_submission`

Decision:

**KEEP until old endpoint/module is physically removed.**

It prevents accidental resurrection of legacy `Ledgix Sale` FBR authority during transition.

### 9.4 Scheduler

Current:

`scheduler_events = {}`

Decision:

Keep fail-closed ambiguous Production retransmission behavior.

A future true offline upload worker must be separately designed; it must not be implemented as a generic blind retry queue.

---

## 10. Printing inventory

Files:

- `apps/ledgix_saas/api/printing.py`;
- `setup/erpnext_phase10_print_formats.py`;
- `Ledgix ERPNext Tax Invoice` print format;
- `Ledgix ERPNext POS Receipt` print format.

Decision:

**KEEP / compliance review later.**

Good:

- source is native ERPNext invoice;
- FBR reference/QR come from persisted FBR metadata.

Refactor:

- seller identity source;
- official DI asset;
- note terminology;
- offline markers;
- final QR/display rules after Sandbox/LI confirmation.

Legacy print formats tied to `Ledgix Sale` remain historical and are separate from current ERPNext-native print authority.

---

## 11. Readiness / release inventory

### 11.1 Client readiness

`api/client_readiness.py`

Currently knows the global `Ledgix FBR Settings`.

Decision:

**REFACTOR** to Company FBR profile and onboarding requirements.

### 11.2 FBR activation

`api/fbr_activation.py`

Decision:

**REWRITE** from generic invoice proof to actual Business Nature/Sector scenario certification.

### 11.3 Release acceptance

`api/release_acceptance.py`

Decision:

**KEEP framework / update FBR gate.**

It should consume the new scenario-based production readiness result.

---

## 12. Scripts / gates inventory

### Current operational FBR scripts

- `scripts/configure_fbr_sandbox_local.sh`;
- `scripts/run_fbr_sandbox_exercise_local.sh`;
- `scripts/run_fbr_activation_readiness_gate.sh`;
- `scripts/run_fbr_activation_static_gate.sh`.

Decision:

**REWRITE or retire as appropriate.**

Normal client configuration must become Desk-first.

Scripts may remain for:

- development diagnostics;
- automated validation;
- explicit operator evidence.

They must not be the canonical client business-configuration mechanism.

### Historical phase gates

- `scripts/run_erpnext_phase4_final_gate.sh`;
- `scripts/run_erpnext_phase9_final_gate.sh`;
- `apps/ledgix_saas/migration/erpnext_phase4_tax_parity_*.py`;
- `apps/ledgix_saas/migration/erpnext_phase9_fbr_*.py`.

Decision:

**KEEP as historical migration/regression evidence until replacement gates exist.**

Do not treat Phase 4’s custom tax architecture as target behavior.

After new V2 gates cover equivalent safety, these old gates can be archived more explicitly or removed from current CI if they enforce obsolete architecture.

---

## 13. Documentation inventory

### Current plan authority

`docs/fbr/FBR_ERPNext_NATIVE_REDESIGN_PLAN.md`

Decision:

**KEEP — redesign source of truth.**

### Existing current docs to rewrite during implementation

- `docs/fbr/FBR_ARCHITECTURE_AND_OPERATIONS.md`;
- `docs/fbr/FBR_PRODUCTION_CHECKLIST.md`;
- `docs/production/fbr_sandbox_production_activation.md`;
- `docs/architecture/CURRENT_ARCHITECTURE.md`;
- root `README.md`.

### Deprecated old tax docs

- `docs/fbr/FBR_TAX_LAYER.md`;
- `docs/fbr/FBR_TAX_MODULE.md`.

Decision:

Historical/deprecated only. Remove or archive once no current references require the filenames.

### Migration archive

`docs/archive/migration/`

Decision:

**DO NOT rewrite historical phase evidence as current architecture.**

---

## 14. Keep / Rewrite / Migrate / Retire matrix

| Component | Phase 0 decision | Why |
|---|---|---|
| ERPNext Sales Invoice | KEEP | Financial/FBR source authority |
| ERPNext POS Invoice | KEEP | Retail financial/FBR source authority |
| ERPNext native return | KEEP | Commercial/accounting authority |
| POS consolidation exclusion | KEEP | Prevents duplicate FBR submission |
| `fbr_native.py` | HEAVY REWRITE | Correct native source, wrong old tax/settings dependencies |
| `fbr_client.py` | KEEP + REFACTOR | Good guarded transport |
| `fbr_reference.py` | REWRITE/EXPAND | Correct reference API direction |
| `fbr_settings.py` | REPLACE/MIGRATE | Global Single; target Company profile |
| `fbr_activation.py` | REWRITE | Must become scenario-based |
| `fbr_preflight.py` | REWRITE | Coupled to old tax profiles/item scenario |
| `fbr_health.py` | REFACTOR | Must support new profile/offline health |
| `fbr_payload.py` | SPLIT/REWRITE | Mixes legacy/native helpers |
| `fbr_submission.py` | EXTRACT + RETIRE LEGACY | Native still uses shared utilities |
| FBR Submission Log | KEEP/EVOLVE | Valid compliance audit |
| FBR Correction Request | KEEP/REFACTOR | Valid external workflow tracking |
| Ledgix FBR Settings | REPLACE | Wrong global config boundary |
| Ledgix Item Tax Profile | REPLACE/MIGRATE CLASSIFICATION | Mixes FBR + tax authority |
| Ledgix Tax Profile | RETIRE | Duplicate tax/business defaults |
| Ledgix Tax Category | RETIRE | Duplicate ERPNext financial tax master |
| Ledgix Tax Rate | RETIRE | Duplicate financial rate authority |
| Ledgix Tax Audit Log | HISTORICAL / REVIEW | Old-tax audit evidence |
| Invoice/Return Tax Detail | HISTORICAL / DELETE LATER | Legacy sale snapshots |
| `api/taxation.py` | RETIRE | Second tax engine |
| `services/tax.py` | RETIRE with legacy sale | Second/legacy tax engine |
| `erpnext_tax_foundation.py` | REPLACE ACTIVE CALCULATION | Current active custom tax authority |
| Company Ledgix tax account fields | MIGRATE THEN RETIRE | Native templates should own accounts |
| Item Group Ledgix tax defaults | RETIRE/REDESIGN | Old tax engine + wrong scenario placement |
| Customer FBR fields | KEEP/REFINE | Useful FBR buyer metadata |
| Invoice FBR status fields | KEEP/REFINE | Valid compliance metadata |
| Invoice line snapshot fields | KEEP CONCEPT / RE-SOURCE | Must come from native tax + FBR mapping |
| Tax & FBR Center | REWRITE | Currently exposes old tax engine |
| ERPNext FBR print formats | KEEP/REVIEW | Correct native source |
| Production arm interlock | KEEP | Strong safety control |
| Reconciliation Required | KEEP | Strong duplicate-prevention control |
| automatic blind retry | KEEP DISABLED | Unsafe for ambiguous POST |
| true offline upload | BUILD NEW | Separate legal workflow |

---

## 15. Required extraction order

This order is mandatory to avoid hidden conflicts.

### Step A — build native tax authority before removing old tax calculation

1. Define native ERPNext tax templates/rules/item-tax behavior.
2. Prove native Sales Invoice/POS/return totals and GL.
3. Add a native-tax-only checkout path behind tests/migration control.
4. Only then remove `apply_tax_plan()` from active transaction construction.

### Step B — introduce FBR V2 masters

Create:

- Company-scoped FBR Integration Profile;
- FBR Item Mapping;
- FBR Tax Component Mapping;
- FBR Reference Data;
- FBR Sandbox Certification.

### Step C — migrate verified classification/config

Migrate safe data from old:

- FBR Settings;
- Item Tax Profile;
- Company tax mappings for comparison;
- existing FBR metadata.

Do not turn old monetary rates into new authority automatically.

### Step D — replace snapshot source

Create immutable V2 FBR snapshots from:

- ERPNext native tax result;
- new FBR mapping;
- official reference data.

Keep old submitted invoice snapshots immutable.

### Step E — extract native shared FBR utilities

Move native-safe utilities out of legacy-heavy modules:

- response parser;
- Submission Log writer;
- locking;
- safe status helpers;
- common schema normalization.

Then make `fbr_native.py` independent of legacy `fbr_submission.py` and legacy sale helpers in `fbr_payload.py`.

### Step F — rewrite Desk/readiness/certification

Replace Tax Center + old item-level scenario coverage.

### Step G — freeze old tax masters

Once current runtime no longer reads them:

- remove active UI;
- remove write paths/permissions;
- mark historical/migration-only;
- verify no new records can be produced.

### Step H — physical deletion only after final reference/data proof

Do a repository-wide and runtime DB dependency audit.

Delete only components that have no required historical/audit role.

---

## 16. Phase 0 runtime evidence still required

Because this Phase 0 pass is being performed directly against GitHub without the local bench/site running, the following **runtime-only** evidence remains pending.

This is not a design blocker, but it must be captured before destructive schema retirement.

On `ledgix-erpnext.local`, later collect read-only counts / examples for:

- Ledgix Tax Profile existence/settings;
- Ledgix Tax Categories;
- Ledgix Tax Rates;
- Ledgix Item Tax Profiles;
- Item Profiles linked to ERPNext Items;
- Company Ledgix tax account fields;
- Item Group old tax defaults;
- historical Ledgix Invoice Tax Detail rows;
- historical Ledgix Return Tax Detail rows;
- FBR Settings state without exposing tokens;
- FBR Submission Logs by native vs legacy reference;
- FBR Correction Requests;
- submitted ERPNext invoices containing snapshot version 2;
- current FBR statuses;
- Reconciliation Required records.

Also capture the current baseline test status before the first transaction-authority code change.

No Production server is required for this design phase.

---

## 17. Phase 0 safety state

Until the redesign reaches the appropriate gates:

- do not arm FBR Production for redesign testing;
- do not fabricate Sandbox evidence;
- do not delete old tax tables/data;
- do not modify ERPNext core;
- do not blindly remove old custom fields from existing sites;
- do not introduce a second V2 tax calculator.

Legacy `Ledgix Sale` official submission remains guarded and must stay guarded during transition.

---

## 18. Phase 0 conclusion

The static repository baseline is sufficient to begin **Phase 1 — ERPNext-native tax authority design/implementation**.

The key cutover boundary is now explicit:

```text
CURRENT
Ledgix custom tax config/calculation
  -> writes ERPNext taxes
  -> ERPNext totals/GL
  -> FBR snapshot

TARGET
ERPNext native tax config/calculation
  -> ERPNext totals/GL
  -> Ledgix reads authoritative tax result
  -> FBR classification + immutable snapshot
  -> FBR transport
```

The old tax/FBR code will not be allowed to coexist as a second active authority after cutover.

Physical deletion happens only after dependency extraction, data migration, runtime proof and full regression.

---

## 19. Next implementation step

Proceed to **Phase 1** in a separate coherent change set:

1. inspect exactly how ERPNext v15 native Tax Category / Tax Rule / Sales Taxes and Charges Template / Item Tax Template should be applied in Ledgix-created POS Invoice and Sales Invoice;
2. define the native configuration contract;
3. build native-tax transaction behavior without deleting the old path first;
4. add regression coverage;
5. cut checkout/return over only after parity is proven.

