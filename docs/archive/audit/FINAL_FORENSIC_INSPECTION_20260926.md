# Ledgix POS — Final Forensic Inspection 2

**Audit date:** 26 September 2026
**Repository:** `mshahwaiz-ali/ledgix-pos`
**Audit branch:** `forensic-final-audit-20260926`
**Baseline main SHA:** `597edbc3dfa61009c609766642554b6aad86b2c5`
**Preserved audit checkpoint SHA:** `558cfc2df29c2f5691addbef73b2f402914cb6f7`
**Local integration site:** `ledgix-erpnext.local`

## 1. Final status

| Status | Result |
|---|---|
| Software Ready for Client Certification | **YES** |
| Sandbox Certified | **NO** |
| Production Ready | **NO** |
| Production Active | **NO** |
| Real FBR/PRAL network calls made during this final audit | **0** |
| Production posting armed | **NO** |
| General V2 network cutover active | **NO** |

The software-level forensic blockers identified in this final review are closed by code changes and regression/runtime proof. This does **not** constitute FBR Sandbox certification, PRAL certification, legal approval, Production authorization, or proof of client-specific master-data completeness.

Production remains intentionally fail-closed.

---

## 2. Scope and safety boundaries

This inspection was performed against the dedicated forensic audit branch and the isolated local integration site.

- No Production environment access was used for this final audit.
- No real FBR or PRAL validate/POST call was made.
- No fabricated FBR token, certification result, provider approval, legal identity, or official reference evidence was introduced.
- ERPNext core was not edited.
- Accounting state was not mutated merely to make tests pass.
- Production FBR posting remained disabled and unarmed.
- Transactional runtime gates used local temporary fixtures and explicitly verified rollback.
- Historical Ledgix business records remain audit/history data rather than the active business authority.

---

## 3. Architecture conclusion

The current architecture correctly treats **ERPNext as the business/accounting authority** and Ledgix as the product, compliance and orchestration layer.

### ERPNext-native authority

ERPNext is authoritative for:

- Item and Item Group
- Customer and Supplier
- Price List, Item Price and Pricing Rule
- Sales Invoice and POS Invoice
- sales returns
- Payment Entry
- Purchase Order / Purchase Receipt / Purchase Invoice
- Stock Ledger, Batch and Serial data
- POS opening/closing
- General Ledger
- tax/accounting consequences

### Ledgix authority

Ledgix remains responsible for:

- product/user experience
- compliance metadata
- FBR V2 configuration
- FBR item mapping/reference evidence
- FBR payload orchestration
- transport safety
- submission evidence
- reconciliation state
- client readiness
- Sandbox certification workflow
- controlled operator UI
- compatibility routing from retired Ledgix workflows

No current finding requires restoring the former duplicate Ledgix business engine.

---

## 4. Legacy business-engine retirement

The intended Phase 12 architecture remains intact:

- legacy Ledgix business DocTypes are historical/audit records;
- ERPNext-native objects are the active operational authority;
- legacy business routes are guarded or compatibility-routed;
- historical rows are preserved rather than destructively deleted;
- old tax/action paths are retired;
- historical business test suites remain intentionally skipped where their fixtures exercise the pre-cutover engine.

Outside `setup/`, 13 test files were confirmed intentionally retired/skipped historical suites and 8 were empty `FrappeTestCase` shells. Active static/UI checks and the meaningful local role/permission integration module were treated separately.

---

## 5. Item, pricing, buying, selling and inventory

The codebase preserves ERPNext-native authority for catalogue, price, buying, selling and inventory behavior.

Earlier forensic fixes in the preserved audit batch removed:

1. manual stock-receipt fallback to retired `Ledgix Item.cost_price`;
2. raw Item Price fallback that ignored native effective-date behavior.

POS cost/reporting was corrected to follow consolidated native Sales Invoice GL/Stock Ledger behavior. Local forensic proof covered 337 POS rows with native cost total `147282.44`; the corrected query matched that native total exactly.

---

## 6. POS, returns, payments and accounting

The product retains a custom Ledgix POS experience while ERPNext documents remain authoritative underneath.

Corrections included:

- direct compatibility calls into retired POS code;
- B2B return argument mismatch;
- retail-return retry/reuse behavior;
- stale assumptions around legacy records.

Payment/accounting authority remains ERPNext-native. No accounting mutation was introduced merely to force tests green.

Return/FBR semantics remain conservative where real debit/credit-note behavior still requires external proof.

---

## 7. FBR V2 configuration authority

The company-scoped **Ledgix FBR Integration Profile** is the active configuration authority.

It carries the V2 controls required for:

- company
- enabled/disabled state
- mode
- submit trigger
- provider/integrator metadata
- protocol/version metadata
- Business Nature / Sector
- onboarding status
- IP-whitelist state
- software provider/name/version/registration metadata
- Digital Invoicing logo metadata
- technical contact
- Sandbox/Production credentials
- `production_post_armed`
- failure policy
- offline policy/window
- reference-sync state

Final runtime gates proved activation, readiness and operator state use this profile rather than the retired FBR Settings singleton.

---

## 8. Seller identity, mapping and reference evidence

Seller identity is derived from **ERPNext Company + Company Address**.

Real-state runtime gates correctly remained not-ready because local/client prerequisites are incomplete. Verified blockers include:

- Company Tax ID;
- registered/default Company Address;
- State/Province;
- Customer legal/billing address in the proof fixture;
- mapping review;
- HS Code verification;
- UOM verification;
- Transaction Type/Sale Type verification;
- cached HS-UOM proof;
- required Province/Transaction Type rate-reference context.

No official reference evidence or identity data was fabricated.

---

## 9. Payload construction and snapshots

The FBR V2 payload flow uses submitted native ERPNext documents plus persisted V2 snapshot evidence.

The native runtime gate proved for both Sales Invoice and POS Invoice:

- local submission completed;
- snapshot version persisted;
- snapshot hash verified;
- readiness source was `persisted_v2`;
- authority was `ERPNext Native`;
- payload builder was `FBR V2`;
- incomplete real configuration returned no partial payload;
- FBR transport was not reached.

The fail-closed gate separately proved that the canonical payload builder rejects an invoice when real identity/mapping/reference prerequisites are missing.

---

## 10. Transport policy

The transport policy proved:

- no profile → block without transport;
- disabled profile → block;
- mode mismatch → block;
- missing token → block;
- Sandbox validate/POST use the correct fixed endpoints;
- Production POST requires completed Sandbox certification;
- Production POST also requires explicit arming;
- timeout, HTTP 408, HTTP 503, malformed HTTP-success response, and a successful-looking body without a conclusive invoice number are treated as ambiguous;
- ambiguous Production outcomes require reconciliation;
- explicit FBR Invalid is a conclusive rejection;
- conclusive invoice number is accepted as success;
- secrets are not exposed.

All transport-policy calls were simulated. **Real FBR network calls remained zero.**

---

## 11. Blocker A — Sandbox certification evidence hardening

### Original defect

Certification completion could trust editable scenario status fields and parent completion state without re-proving linked FBR evidence.

### Fix

Certification completion is now re-derived from referenced evidence. Shared proof logic requires matching:

- reference document;
- company;
- Integration Profile;
- Sandbox mode;
- operation;
- expected FBR result;
- `network_call=true`;
- successful result.

Scenario proof fields are read-only through the normal DocType UI. Production certification checks use the same evidence-derived readiness state.

### Result

**Blocker A closed at software level.**

This does not mean real Sandbox certification has occurred.

---

## 12. Blocker B — company/profile isolation

### Original defect

Activation Sandbox proof/reconciliation evidence could scan too broadly and allow unrelated evidence to influence readiness.

### Fix

Sandbox proof is scoped to the selected company/profile and reconciliation evidence is company-scoped.

### Result

**Blocker B closed at software level.**

---

## 13. Blocker C — Production POST crash-window durability

### Original defect

The Production POST path created durable submission evidence only after the network response. A worker/process crash after remote acceptance but before local persistence could therefore create retransmission risk.

### Fix

Production POST now uses a fail-closed durable attempt flow:

1. create a pending/prepared Submission Log;
2. mark the native invoice `Reconciliation Required`;
3. explicitly commit that guard state **before** entering the Production POST network window;
4. perform the network call;
5. finalize the same durable log;
6. move the invoice to final state only on a conclusive result.

If the worker exits after the pre-network commit, the persisted reconciliation state blocks automatic retransmission.

If transport conclusively reports that no network request occurred, the same log can be finalized Failed and state normalized.

If finalization fails after the remote call, the already-committed reconciliation guard remains fail-closed.

### Submission Log permissions

Normal DocType permissions were hardened:

- rename disabled;
- System Manager create/write/delete disabled;
- Ledgix Admin create/write/delete disabled;
- Ledgix Manager remains read-only.

This is normal Desk/application immutability, not cryptographic immutability or protection from DB/console superuser access.

### Result

**Blocker C closed at software level.**

---

## 14. Reconciliation, offline and correction/cancellation

Ambiguous Production POST outcomes are not blindly retried. Reconciliation is required where the remote outcome may exist but cannot be proven locally.

Offline behavior remains fail-closed. The audit did not invent an FBR offline legal allowance/window.

Post-FBR correction/cancellation, debit-note and credit-note behavior remains conservative until verified against the client’s real FBR/PRAL workflow.

---

## 15. Print, QR and legal presentation

No local mock, placeholder or static template is treated as legal certification evidence.

Client certification still needs real verification of:

- accepted FBR invoice number placement;
- QR content/encoding;
- Digital Invoicing logo requirements;
- required seller/provider/integrator wording;
- return/note presentation if in scope;
- exact print behavior required by the client’s onboarding path.

---

## 16. Security and permissions

The audit confirmed or hardened:

- Production POST requires completed Sandbox certification evidence;
- Production POST requires explicit arming;
- Production remains disabled/unarmed locally;
- general V2 network cutover remains hard-disabled;
- legacy transport fails closed;
- Submission Log Desk mutation is blocked for ordinary System Manager/Ledgix Admin roles;
- certification scenario proof fields are read-only in normal UI;
- transport outputs redact credential/token material;
- ambiguous Production outcomes force reconciliation;
- there is no generic blind FBR retry scheduler.

---

## 17. Frontend/product shell

Native Frappe/ERPNext page chrome remains authoritative. Surviving Ledgix product pages are focused surfaces:

- Ledgix POS
- Tax & FBR Center
- Inventory Intelligence
- Setup Wizard

Static/UI regression coverage verifies retirement of obsolete navigation/mode concepts and ERPNext-native workspace targets.

---

## 18. Fresh-install and migration safety

The audit preserves these principles:

- ERPNext is the required operational dependency;
- after-migrate ownership remains ordered;
- legacy retirement is controlled rather than destructive;
- fresh-site tax-master retirement guards were corrected;
- historical business test suites are explicitly marked retired where their pre-cutover assumptions are no longer authoritative.

Write/commit-heavy Phase 9/12/13 gates were not rerun merely for cosmetic proof after prior controlled execution and contract coverage. Final runtime proof favored read-only, in-memory or rollback-confirmed gates.

---

## 19. Test and gate evidence

### Focused forensic suite

- **19 tests**
- **19 passed**
- **0 failed**

### Full setup suite

- **472 tests**
- **472 passed**
- **0 failed**

### User/role integration module

- **9 total**
- **7 passed**
- **2 intentionally skipped**
- **0 failed**

### Read-only/in-memory FBR runtime gates

All passed:

1. V2 health/client status
2. V2 activation profile
3. V2 client setup/readiness
4. V2 transport policy

Each reported **0 real FBR network calls**.

### Rollback-confirmed transactional gates

Both passed:

1. Native V2 runtime cutover
2. V2 payload fail-closed

Both confirmed:

- `database_persistence = ROLLBACK_CONFIRMED`
- `fbr_network_calls = 0`
- no persisted gate invoices
- rollback clean

---

## 20. Defects addressed by the forensic audit

The preserved forensic batch plus final hardening addressed:

- transport response/token redaction;
- submission-lock cleanup defect;
- stale Ledgix cost-price fallback;
- unsafe raw Item Price fallback;
- POS cost/reporting mismatch with native consolidated accounting behavior;
- reporting monkey-patch/import-order dependency;
- direct compatibility calls into retired POS code;
- B2B return argument mismatch;
- retail-return retry/reuse behavior;
- fresh-site tax retirement rename guard;
- stale architecture documentation;
- editable/trusted Sandbox certification flags;
- cross-company/global Sandbox proof;
- Production POST crash-window durability;
- Submission Log normal Desk mutability.

---

## 21. Final uncommitted hardening paths

Before adding this report, the final hardening diff was limited to 9 paths:

1. `apps/ledgix_saas/api/fbr_activation.py`
2. `apps/ledgix_saas/api/fbr_native.py`
3. `apps/ledgix_saas/api/fbr_v2_transport.py`
4. `apps/ledgix_saas/ledgix/doctype/ledgix_fbr_sandbox_certification/ledgix_fbr_sandbox_certification.py`
5. `apps/ledgix_saas/ledgix/doctype/ledgix_fbr_sandbox_scenario/ledgix_fbr_sandbox_scenario.json`
6. `apps/ledgix_saas/ledgix/doctype/ledgix_fbr_submission_log/ledgix_fbr_submission_log.json`
7. `apps/ledgix_saas/services/fbr_submission_support.py`
8. `apps/ledgix_saas/services/fbr_v2_readiness.py`
9. `apps/ledgix_saas/setup/test_forensic_safety.py`

Normalized code diff:

- **9 files changed**
- **618 insertions**
- **73 deletions**

`inspection2.md` is the final report artifact added after that code inventory.

---

## 22. Remaining software defects

No unresolved software defect from the final A/B/C blocker set is known after focused regression, full setup regression and final runtime gates.

This statement is limited to the inspected scope and is not a claim that every future ERPNext/FBR version or integration combination is defect-free.

---

## 23. Remaining client / external blockers

The product is **not** ready for real Sandbox certification or Production activation until genuine client/provider evidence is supplied and validated.

Known prerequisites include:

- Company Tax ID / NTN-CNIC identity;
- complete registered/default Company Address;
- State/Province;
- Customer legal/billing address data where required;
- review of pending active FBR mappings;
- active official FBR reference-data evidence;
- genuine Sandbox token;
- genuine Production token when appropriate;
- provider / Licensed Integrator details;
- Business Nature / Sector;
- software/POS registration details where required;
- Digital Invoicing logo evidence;
- IP whitelist/onboarding evidence;
- genuine Sandbox validate/POST certification evidence;
- final QR/print/legal-format confirmation;
- return/debit-note/credit-note proof if in scope;
- confirmed offline issuance rule/window if required;
- verified release/backup/deployment evidence;
- explicit Production authorization.

These must not be inferred or fabricated.

---

## 24. Final certification interpretation

### Software Ready for Client Certification — YES

The inspected software controls, regression suite and local runtime gates are sufficiently closed to proceed to genuine client certification/onboarding.

### Sandbox Certified — NO

No real authorized Sandbox certification was performed in this final audit.

Mocks, simulated HTTP results, local fixtures and in-memory gates are not certification evidence.

### Production Ready — NO

Client identity, mappings/reference evidence, credentials, legal/provider onboarding proof and genuine Sandbox certification remain outstanding.

### Production Active — NO

Production posting remains disabled/unarmed and the general V2 network cutover remains `False`.

---

## 25. Recommended next operational phase

Do not enable Production.

Proceed in this order:

1. review and commit final forensic hardening on the audit branch;
2. review/merge only after the final diff is accepted;
3. complete client ERPNext legal identity/master data;
4. review FBR item mappings;
5. populate/verify official FBR reference evidence through the authorized workflow;
6. configure genuine Sandbox credentials;
7. perform controlled real Sandbox certification;
8. preserve real validate/POST logs as certification evidence;
9. verify final invoice print/QR/legal presentation;
10. resolve return/offline requirements where applicable;
11. complete provider/onboarding/whitelist/software-registration prerequisites;
12. obtain explicit Production authorization;
13. only then evaluate Production mode and Production POST arming.

---

## 26. Final forensic conclusion

> Ledgix POS has completed the inspected software-side ERPNext-native/FBR V2 hardening required to proceed to **client certification**. The system remains intentionally fail-closed for real FBR operation. No real Sandbox or Production certification is claimed, and Production must remain disabled until outstanding client, provider, legal, reference-data and genuine Sandbox-evidence prerequisites are completed.
