# FBR V1.2 -> Federal Legacy V1 / Tier-1 Component Matrix

**Baseline:** `main@17f81554a0eeea85e9a6868719a9b76c0dcf4e36`  
**Rule:** “DELETE” means remove from active V1 runtime/design; if a site already contains persistent records, migration is non-destructive and preserves them read-only unless a separately approved cleanup is performed.

Legend:
- **KEEP** — valid architecture/mechanism with minimal naming cleanup.
- **MODIFY** — useful base, but contract/schema/semantics must change.
- **REPLACE** — inherited behavior is wrong authority for legacy V1.
- **DELETE** — should not participate in V1 runtime.
- **UNRESOLVED** — cannot be implemented safely until authoritative evidence is obtained.

## 1. Top-level and framework

| Path / component | Disposition | Canonical action |
|---|---|---|
| `apps/fbr_v1/README.md` | MODIFY | Replace bootstrap warning with final regime boundary after implementation. |
| `apps/fbr_v1/pyproject.toml` | MODIFY | Keep Frappe/ERPNext v15 dependency; reassess `requests`/QR dependency after transport/printing design. |
| package/module `__init__.py` files | KEEP | Mechanical Frappe package scaffolding. |
| `fbr_v1/modules.txt` | KEEP | FBR V1 module remains isolated. |
| `fbr_v1/patches.txt` | MODIFY | Add only non-destructive migration patches once schema is approved. |
| `fbr_v1/hooks.py` | MODIFY | Keep ERPNext doc-event boundary; replace V2 snapshot/native orchestration hooks with V1-neutral services. |

## 2. API files

| Path | Disposition | Reason / target |
|---|---|---|
| `api/__init__.py` | KEEP | Package scaffolding. |
| `api/client_readiness.py` | MODIFY | Retain ERPNext/site/backup checks; remove V2 reference/certification assumptions; add regime/POS-device evidence. |
| `api/fbr_activation.py` | REPLACE | V2 token/sandbox/certification activation is not legacy SDC authority. Target `api/readiness.py` + explicit regime activation gate. |
| `api/fbr_native.py` | REPLACE | Main flow imports V2 builder/readiness/transport. Target `api/fiscalization.py` with adapter interface and no protocol guessing. |
| `api/fbr_offline.py` | REPLACE | Replace configurable V2 policy with Chapter-XIV offline event lifecycle; SDC upload mechanism stays unresolved. |
| `api/fbr_reference_v2.py` | DELETE | Current DI reference APIs belong to `fbr_v12`. |
| `api/fbr_transport.py` | MODIFY | Keep only low-level transport abstraction behind adapter; remove bearer/default-URL assumptions. |
| `api/fbr_v2_center.py` | REPLACE | Replace with `api/center.py` for legacy regime/POS-device/log/offline/closing readiness. |
| `api/fbr_v2_transport.py` | DELETE/REPLACE | Remove DI validate/post endpoints from V1. Target `protocol/legacy_sdc.py` remains disabled until authoritative contract. |
| `api/printing.py` | MODIFY | ERPNext-derived context retained; Chapter-XIV particulars/QR dimensions/device identity rebuilt. |

## 3. Service files

| Path | Disposition | Reason / target |
|---|---|---|
| `services/__init__.py` | KEEP | Package scaffolding. |
| `services/erpnext_fbr_identity.py` | MODIFY | ERPNext Company/Customer/Address authority retained; remove V2 wording and narrow legacy fallback fields. |
| `services/erpnext_fbr_snapshot.py` | KEEP/MODIFY | Keep native ERPNext tax collector; rename and map only supported FBR components. |
| `services/erpnext_taxable_base.py` | MODIFY | Preserve ERPNext taxable-base resolver concept; fix wrong mapping DocType name during implementation; no custom tax calculator. |
| `services/fbr_submission_support.py` | MODIFY | Keep serialization/lock/log helpers; replace DI response parser/status assumptions. |
| `services/fbr_v2_payload_builder.py` | REPLACE | DI V1.2 request shape/scenario model cannot be used for SDC. Target `protocol/schemas.py` + legacy adapter only after proof. |
| `services/fbr_v2_readiness.py` | REPLACE | Replace DI reference/token/certification checks with regime, POS-device, ERPNext, snapshot and protocol-proof readiness. |
| `services/fbr_v2_snapshot_persistence.py` | MODIFY | Keep hash/immutability pattern, move to neutral V1 fields/version and migrate old fields safely. |

## 4. Setup / migration files

| Path | Disposition | Reason / target |
|---|---|---|
| `setup/__init__.py` | KEEP | Package scaffolding. |
| `setup/erpnext_fbr_schema.py` | MODIFY | Preserve useful generic fields, introduce neutral V1 fields/POS-device link, deprecate V2 snapshot fields non-destructively. |
| `setup/erpnext_phase9_extensions.py` | MODIFY | Keep runtime metadata concept; change offline deadline semantics and add restoration/upload evidence. |
| `setup/fbr_v2_component_mappings.py` | MODIFY | Rename V1-neutral; keep ERPNext-account semantic mapping without tax calculation. |
| `setup/install.py` | KEEP/MODIFY | Preserve no-network install/migrate behavior; call new schema sync modules. |
| `setup/print_formats.py` | KEEP | Force-sync mechanism remains useful; target templates change. |
| `setup/test_fbr_v1_offline_runtime.py` | REPLACE | New rule-150XC + mock-adapter tests. |
| `setup/test_fbr_v1_payload_runtime.py` | REPLACE | No payload contract test until authoritative SDC fixture exists; use schema-stub/mocks meanwhile. |
| `setup/test_fbr_v1_snapshot_runtime.py` | MODIFY | Keep immutable hash tests, rename to V1-neutral fields/version. |
| `setup/test_fbr_v1_transport_runtime.py` | REPLACE | Test allowlist/mock/no-network/idempotency; no DI URLs/tokens. |

## 5. DocTypes

| Component/files | Disposition | Canonical action |
|---|---|---|
| `Ledgix FBR Business Nature` JSON/PY/init | DELETE from V1 active model | DI onboarding artifact; preserve records if installed. |
| `Ledgix FBR Correction Request` JSON/PY/test/init | REPLACE | Remove unsupported 72-hour/Commissioner workflow. New lifecycle is ERPNext return/debit/credit note + append-only fiscal event evidence; external correction API unresolved. |
| `Ledgix FBR Integration Profile` JSON/PY/init | MODIFY | Add integration regime, grandfathering evidence, POS/device model and hard-disabled unresolved protocol. Remove DI protocol default/reference/certification semantics. |
| `Ledgix FBR Item Mapping` JSON/PY/init | MODIFY | Retain HS/UOM/tax basis/SRO only where source/ERP tax setup requires; DI sale-type/rate metadata cannot be inherited automatically. |
| `Ledgix FBR Reference Data` JSON/PY/init | DELETE from V1 active model | DI reference cache; no proven legacy SDC reference API. |
| `Ledgix FBR Sandbox Certification` JSON/PY/init | DELETE from V1 active model | DI scenario certification. Historical SDC “test registration” is a different concept. |
| `Ledgix FBR Sandbox Scenario` JSON/PY/init | DELETE from V1 active model | Same reason; no authoritative legacy scenario catalogue. |
| `Ledgix FBR Submission Log` JSON/PY/JS/tests/init | MODIFY | Preserve core audit object; make append-only semantics, protocol/POS identity/hash/attempt/outcome fields, secret redaction. |
| `Ledgix FBR Tax Component Mapping` JSON/PY/init | KEEP/MODIFY | ERPNext account semantic mapping remains useful; align options to current invoice particulars. |

### Proposed new V1 DocTypes

| New component | Purpose |
|---|---|
| `Ledgix FBR POS Device` | Company/outlet/POS Profile link, FBR/POS software registration identity, transport topology, mode, onboarding/grandfathering evidence, active state. |
| `Ledgix FBR Fiscal Event Log` | Append-only system/offline/restoration/error/adjustment/cancellation/closing events required for audit. |
| `Ledgix FBR Fiscal Closing` | Daily/weekly/monthly closing evidence and aggregates. External closing request/response fields remain unused until protocol is known. |

## 6. Page / workspace

| Path | Disposition | Canonical action |
|---|---|---|
| `page/__init__.py` | KEEP | Scaffolding. |
| `page/fbr_v1_center/__init__.py` | KEEP | Scaffolding. |
| `page/fbr_v1_center/fbr_v1_center.css` | KEEP/MODIFY | Reuse layout styling; remove V2-specific class naming over time. |
| `page/fbr_v1_center/fbr_v1_center.js` | REPLACE | It directly calls V2 center/reference/certification/offline APIs. |
| `page/fbr_v1_center/fbr_v1_center.json` | KEEP/MODIFY | Keep page and roles; content contract changes. |
| workspace package init files | KEEP | Scaffolding. |
| `workspace/fbr_v1/fbr_v1.json` | MODIFY | Replace Reference Data/Sandbox/Correction shortcuts with POS Devices, Fiscal Events, Closings, Logs and Readiness. |

## 7. Print formats

| Path | Disposition | Canonical action |
|---|---|---|
| print-format package init files | KEEP | Scaffolding. |
| `print_format/ledgix_erpnext_pos_receipt/...json` | REPLACE template / KEEP format identity | Current receipt QR is 25.4 mm; Chapter XIV says 7x7 mm. Rebuild mandatory particulars and state gates. |
| `print_format/ledgix_erpnext_tax_invoice/...json` | REPLACE template / KEEP format identity | Rebuild mandatory particulars while preserving ERPNext totals/tax authority. |

## 8. Protocol concepts inherited from V1.2

| Inherited behavior | Disposition | Reason |
|---|---|---|
| DI `validateinvoicedata[_sb]` | DELETE | Not legacy SDC authority. |
| DI `postinvoicedata[_sb]` | DELETE | Not legacy SDC authority. |
| Bearer sandbox/production tokens | DELETE/UNRESOLVED | Legacy auth not proven. |
| `scenarioId` | DELETE | DI sandbox concept, not proven legacy SDC concept. |
| DI province/UOM/rate/SRO reference APIs | DELETE from V1 | Belong current DI unless proven otherwise. |
| Production “arming” safety concept | KEEP/MODIFY | Keep an explicit human safety gate, but it must require legacy-regime proof rather than DI certification. |
| immutable invoice snapshot | KEEP/MODIFY | Protocol-neutral audit feature. |
| submission lock | KEEP | Necessary for idempotency/concurrency. |
| ambiguous-result “do not blind retry” | KEEP | Safety invariant. |
| configurable offline upload hours | DELETE | Current rule is 24 hours after restoration. |
| 72-hour correction window | DELETE | Unsupported by current authoritative sources recovered. |
| sandbox scenario certification DocType | DELETE | Wrong protocol. |
| QR based on FBR invoice number | KEEP/MODIFY | Current rule supports the basis; exact encoded payload verification remains a gate. |
| local QR image generation | UNRESOLVED/MODIFY | Allowed only after QR payload and verification behavior are proven. |
| FBR response `validationResponse.invoiceStatuses` parser | DELETE | DI response shape, not legacy SDC authority. |
| ERPNext tax authority | KEEP | Required design invariant. |
| separate Ledgix tax arithmetic | DELETE/forbidden | ERPNext remains monetary/tax authority. |

## 9. Machine-level V1 contract matrix

| Requirement | Status |
|---|---|
| Historical architecture: POS -> local/network SDC -> FBR | KEEP as historical/grandfathered architecture evidence |
| Current authorization of legacy SDC for a **new** taxpayer | UNRESOLVED / not established |
| Client grandfathered status | UNRESOLVED until evidence supplied |
| Test registration mechanics for current legacy SDC | UNRESOLVED |
| Current SDC download/version | UNRESOLVED |
| Local SDC host/port | UNRESOLVED |
| Health endpoint | UNRESOLVED |
| Fiscalization POST endpoint | UNRESOLVED |
| Auth/access code | UNRESOLVED |
| Request schema | UNRESOLVED |
| Response schema | UNRESOLVED |
| POS/device registration API | UNRESOLVED |
| Payment-mode enum | UNRESOLVED |
| Invoice-type enum | UNRESOLVED |
| Credit/debit-note endpoint/schema | UNRESOLVED |
| Cancellation endpoint/schema | UNRESOLVED |
| Offline submission mechanics | UNRESOLVED |
| Offline deadline | KEEP: 24h after restoration under current Chapter XIV |
| Daily/weekly/monthly closing obligation | KEEP |
| Closing endpoint/schema | UNRESOLVED |
| FBR invoice number printed | KEEP |
| Current number format | KEEP: `XXXXXX-DDMMYYHHMMSS-0001` validation |
| QR dimension | KEEP: 7x7 mm |
| Exact QR encoded data | UNRESOLVED beyond “based on unique FBR invoice number” |
| Six-year electronic retention | KEEP |
| Adjustment/modification/cancellation + system logs | KEEP |
