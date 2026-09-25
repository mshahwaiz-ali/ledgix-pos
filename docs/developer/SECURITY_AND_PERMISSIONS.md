# Ledgix POS — Security and Permissions

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit  
**Primary security authority:** Frappe / ERPNext permissions and server-side Ledgix checks  
**Companion documents:** ARCHITECTURE.md, CODEBASE_AND_EXTENSION_POINTS.md, FBR_ARCHITECTURE.md

## 1. Purpose

This document defines the current Ledgix security and authorization model.

It covers:

- user/role intent;
- Frappe/ERPNext permission authority;
- product-shell visibility vs authorization;
- current Ledgix Pages;
- server-side API role checks;
- FBR administrative boundaries;
- secret handling;
- tenant/site isolation;
- backup security;
- legacy frozen-data protection;
- current permission-policy caveats that developers must not ignore.

The central rule is:

> **UI visibility is not authorization. Frappe/ERPNext permissions plus server-side endpoint checks are the security boundary.**

---

## 2. Security layers

Ledgix security is layered.

    user
      -> authenticated Frappe session
      -> Frappe roles / User Permissions / DocPerm / Custom DocPerm
      -> Page / Report / Workspace role exposure
      -> Ledgix server-side API role checks
      -> subsystem-specific business/compliance interlocks
      -> ERPNext document permissions and lifecycle rules
      -> database/site isolation

No single layer should be treated as sufficient for every operation.

---

## 3. Core Ledgix roles

Current Ledgix operational roles are:

- Ledgix Cashier;
- Ledgix Manager;
- Ledgix Admin.

System Manager remains the Frappe/ERPNext platform-administration role.

A retired historical role:

- Ledgix Super Admin

is mapped to Ledgix Admin by current cleanup logic where encountered.

---

## 4. Role intent

### Ledgix Cashier

Intended for front-line selling/POS operations allowed by:

- current Business Profile;
- native ERPNext permissions;
- Page/API role checks.

Cashier should not be treated as a configuration or FBR administration role.

### Ledgix Manager

Intended for broader operations and read/report visibility such as:

- POS management;
- inventory/purchasing views where enabled;
- reports;
- Tax & FBR Center view/selected manager actions.

Manager is not equivalent to Ledgix Admin.

### Ledgix Admin

Intended for Ledgix application configuration and elevated operational control.

Examples include:

- setup/configuration;
- current Ledgix-specific FBR configuration;
- selected FBR operational actions;
- application-level management.

Ledgix Admin still does not bypass every subsystem safety gate.

### System Manager

Provides platform-level Frappe/ERPNext administration.

System Manager also does not automatically bypass:

- FBR certification evidence;
- Production arming;
- global network cutover;
- reconciliation rules;
- business-document lifecycle controls.

Administrative role is permission to perform an authorized action, not permission to defeat its safety preconditions.

---

## 5. Authentication

Ledgix uses normal Frappe authentication/session handling.

The application does not maintain a parallel Ledgix password/session database.

Normal security practices apply:

- unique named users;
- least privilege;
- disable departed/inactive users;
- secure administrator credentials;
- avoid shared operational accounts;
- do not use Administrator as the normal cashier identity.

---

## 6. Authorization authority

Current server authorization authority is Frappe/ERPNext.

Relevant mechanisms include:

- Role;
- Has Role;
- DocPerm;
- Custom DocPerm;
- User Permission;
- Page roles;
- Report roles;
- Workspace roles;
- native ERPNext document permission checks;
- explicit Ledgix API role checks.

Business Profile feature flags are not permissions.

---

## 7. Product shell is navigation only

api/product_shell.py explicitly states that it controls navigation only.

It can compute:

- role level;
- visible cards;
- visible links;
- visible shortcuts;
- landing route;
- curated sidebar behavior.

Its output can hide unavailable product areas.

It does not grant access.

### Example

A Business Profile can hide or expose "Purchasing".

That setting does not override ERPNext Supplier/Purchase Invoice permissions.

A direct API/form request still needs the appropriate server permissions.

---

## 8. Business Profile feature flags

Current Business Profile feature flags can influence exposure of:

- POS;
- B2B;
- buying;
- inventory;
- advanced inventory;
- accounting workspace;
- FBR.

These are product-configuration controls.

They answer:

> "Should this client/user see this product surface?"

They do not answer:

> "Is this user authorized by the server to read/write the underlying data?"

---

## 9. Current Ledgix Pages

The current final custom Page footprint includes:

- ledgix-pos;
- ledgix-tax-center;
- business-intelligence-center.

The Setup Wizard is retained as a product shortcut/current Page implementation, although the current centralized Page-role map should be treated together with its actual Page/API authorization.

Historical pages such as older dashboard/operations/reports/quick-scan surfaces are retired by setup cleanup.

---

## 10. Page-role intent

Current centralized policy grants:

### ledgix-pos

- System Manager;
- Ledgix Admin;
- Ledgix Manager;
- Ledgix Cashier.

### ledgix-tax-center

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

### business-intelligence-center

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

Page exposure is only the first authorization layer.

Sensitive actions inside the Page still require server-side checks.

---

## 11. Workspace access

The Ledgix Workspace is intended for:

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

Cashier can receive a direct POS-oriented landing route instead of broad workspace access where product policy applies.

Workspace visibility is navigation.

It is not substitute DocType/API permission.

---

## 12. Role home pages

Current role-home intent includes:

- Ledgix Cashier -> ledgix-pos;
- Ledgix Manager -> Ledgix Workspace;
- Ledgix Admin -> Ledgix Workspace.

The product shell can also calculate the effective landing route based on Business Profile features.

---

## 13. Report roles

Current centralized Ledgix report-role policy uses:

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

The report implementation must still respect Company scope and data authorization.

A report role is not permission to bypass native ERPNext document restrictions in arbitrary APIs.

---

## 14. Server-side role helpers

api/security.py defines reusable role groups.

### Cashier or above

- System Manager;
- Ledgix Admin;
- Ledgix Manager;
- Ledgix Cashier.

### Manager or above

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

### Admin / System Manager

- System Manager;
- Ledgix Admin.

These helpers are appropriate only when the endpoint truly matches the stated role group.

---

## 15. Do not rely on browser checks

A browser button being hidden does not secure an endpoint.

Every sensitive whitelisted method must enforce its own server-side role/data checks.

This is especially important for:

- configuration writes;
- FBR actions;
- release/readiness actions;
- stock operations;
- payment operations;
- administrative setup.

---

## 16. Native ERPNext permissions still matter

Ledgix often calls native ERPNext documents through application services.

Even where a service uses controlled ignore_permissions behavior internally, the public API must first enforce the intended Ledgix permission model.

ignore_permissions is not an authorization policy.

It is an implementation tool that must only be used after authorization/business validation.

---

## 17. Central permission policy

setup/permissions.py defines application-level policy for many Ledgix DocTypes, Pages, Reports, roles and retired artifacts.

setup/fast_permissions.py is the optimized migrate-time executor.

Important distinction:

- permissions.py = policy definition;
- fast_permissions.py = efficient synchronization.

New Ledgix permission policy should not be scattered arbitrarily across unrelated setup scripts.

---

## 18. Post-migrate permission synchronization

hooks.py runs fast_permissions.after_migrate.

This means permission behavior must be evaluated not only from checked-in DocType JSON, but also from migrate-time policy.

A schema permission that conflicts with centralized synchronization may not survive a future migrate.

This is a critical maintenance rule.

---

## 19. Current Submission Log permission inconsistency

The final forensic hardening intentionally changed Ledgix FBR Submission Log JSON to read-only Desk evidence.

Current JSON grants:

### System Manager

- read/report/export/share/print/email;
- no write;
- no create;
- no delete;
- no submit/cancel/amend.

### Ledgix Admin

Same read-only evidence intent.

### Ledgix Manager

Read/print only.

However, setup/permissions.py still contains the older policy:

- System Manager -> broad/full permission;
- Ledgix Admin -> broad/full permission;
- Ledgix Manager -> read.

fast_permissions.py applies that policy during migrate.

### Security implication

The repository currently contains a real policy mismatch.

Do not document or rely on "Submission Logs are always read-only after migrate" until:

1. centralized permission policy is corrected;
2. migrate is executed in a controlled environment;
3. effective Custom DocPerm is re-verified;
4. regression coverage checks both JSON and migrate-time policy.

This should be fixed as a code-maintenance defect.

Do not weaken the JSON to match the old policy.

The intended direction is read-only evidence.

---

## 20. Why Submission Logs should be evidence-only

Submission Logs can contain:

- transport attempt history;
- FBR response;
- error state;
- official FBR invoice number;
- Known Offline evidence;
- reconciliation state.

Ordinary Desk mutation would undermine audit value.

Application code may create/finalize logs through controlled server workflows.

Users should not manually rewrite historical transport evidence.

---

## 21. FBR Integration Profile permissions

Current Integration Profile schema permits:

### System Manager

Configuration read/write/create/delete and related standard rights.

### Ledgix Admin

Equivalent application-level configuration rights.

### Ledgix Manager

Read/report/print only.

This matches the intended distinction:

- Admin configures FBR;
- Manager can observe;
- Cashier does not administer integration credentials.

---

## 22. FBR credential fields

Integration Profile stores:

- Sandbox token;
- Production token

as Password fields.

Token values must not appear in:

- Git;
- logs;
- screenshots;
- support tickets;
- exported evidence;
- readiness result payloads.

Only credential presence/state should be surfaced where possible.

---

## 23. FBR Item Mapping permissions

Current schema permits mapping maintenance by:

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

This is operational classification data.

Because mappings influence compliance readiness, changes must remain traceable and reviewed.

A Manager's ability to edit mapping does not authorize Production activation.

---

## 24. FBR Tax Component Mapping permissions

Current schema similarly allows System Manager, Ledgix Admin and Ledgix Manager to maintain FBR tax-component classification.

These mappings are classification only.

They do not grant permission to alter ERPNext monetary accounting.

---

## 25. FBR Reference Data permissions

Current reference-cache schema permits:

- System Manager -> administrative rights;
- Ledgix Admin -> administrative rights;
- Ledgix Manager -> read/report/print.

Most source-evidence fields are read-only.

Official sync is controlled through server API, not ordinary manual field entry.

---

## 26. Sandbox Certification permissions

Current certification schema permits:

- System Manager -> configuration lifecycle;
- Ledgix Admin -> configuration lifecycle;
- Ledgix Manager -> read/report/print.

Critical proof fields are read-only and re-derived by controller logic.

A user cannot safely certify by manually typing a successful Validate/POST status into child rows.

---

## 27. Sandbox Scenario fields

The Sandbox Scenario child table exposes description/selection fields, but evidence outputs are read-only:

- Validate status;
- validation log;
- POST status;
- POST log;
- FBR invoice number;
- completed time;
- last error.

Controller logic regenerates evidence from matching persisted logs.

This is an important integrity control.

---

## 28. FBR API role gates

Current native FBR API role rules generally distinguish:

### View / preview

Allowed roles can include:

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

### Submit / reconciliation release

Restricted to:

- System Manager;
- Ledgix Admin.

This is enforced server-side in fbr_native.

---

## 29. Known Offline roles

Current Known Offline API defines:

### View queue

- System Manager;
- Ledgix Admin;
- Ledgix Manager.

### Declare / upload

- System Manager;
- Ledgix Admin.

Actions also require exact confirmation text and full business/compliance policy readiness.

Role alone is insufficient.

---

## 30. FBR activation-readiness roles

api/fbr_activation.py requires:

- System Manager;
- Ledgix Admin.

The readiness function is read-only.

It:

- does not read token values;
- does not send network requests;
- does not arm Production.

This prevents a "readiness check" from becoming an activation backdoor.

---

## 31. Production authorization is multi-factor policy

Production POST is not authorized merely because the user is an admin.

Current technical interlocks include:

- correct Company profile;
- profile enabled;
- Production mode;
- genuine complete Sandbox Certification;
- Production token;
- production_post_armed;
- readiness;
- global V2 network cutover;
- no unresolved reconciliation;
- appropriate request/source state.

The user role is only one condition.

---

## 32. Production posting arm

production_post_armed is an explicit final interlock on the Integration Profile.

Install, migrate, restore or readiness evaluation must not silently arm it.

It should only be enabled through the authorized go-live process after evidence review.

---

## 33. General FBR network cutover

At the baseline:

    V2_NETWORK_CUTOVER_ACTIVE = False

This is an additional fail-closed application-level boundary.

Do not change it as a side effect of:

- setup;
- migrate;
- documentation;
- profile save;
- token entry;
- Sandbox certification record creation.

---

## 34. Reconciliation safety

A Production POST with ambiguous remote outcome enters Reconciliation Required.

While in that state:

- generic submission is blocked;
- Known Offline is blocked;
- blind retry is blocked.

Manual release requires explicit administrative action and exact external-reconciliation confirmation.

This is both a business-safety and security-integrity control.

---

## 35. No automatic retransmission scheduler

hooks.py has no generic FBR retry/offline scheduler.

This prevents background automation from turning a network ambiguity into a duplicate legal submission.

Do not introduce a scheduled retry worker without redesigning the reconciliation model.

---

## 36. Secret handling — repository

Never commit:

- Sandbox token;
- Production token;
- API keys;
- user/admin passwords;
- DB credentials;
- private keys/certificates;
- .env secrets;
- site_config.json with credentials/encryption material;
- raw private backup archives;
- evidence bundles containing secrets.

The repository has a secret-scan script that should be used as part of release hygiene.

---

## 37. Secret handling — local/production

Current documented storage pattern keeps per-site credentials outside source control.

Production/site secrets should be owner-readable only and separated from the repository.

Historical plaintext helper artifacts are not the current credential contract.

---

## 38. Transport redaction

FBR transport/submission helpers redact evidence before storage/output.

Returned result structures intentionally advertise that they contain no secrets.

This reduces leakage risk but does not eliminate the need for operational caution.

Do not assume every external exception/library log is automatically safe.

---

## 39. Error messages

Sensitive API errors should:

- explain what is missing;
- avoid printing token values;
- avoid raw secret-bearing configuration;
- avoid exposing unrelated tenant data.

Prefer states such as:

- token configured: yes/no

instead of:

- token: actual value.

---

## 40. Tenant isolation model

Ledgix follows native Frappe site isolation.

Recommended client model:

    client A -> own Frappe site/database
    client B -> own Frappe site/database
    staging  -> own Frappe site/database

Do not share between tenants:

- database;
- site_config;
- encryption material;
- FBR tokens;
- seller legal identity;
- backups;
- client-specific certification evidence.

A shared bench can share application code, not business data/secrets.

---

## 41. Company isolation inside a site

Even within a site, many workflows are Company-scoped.

Sensitive code must ensure:

- Warehouse belongs to Company;
- Account belongs to Company;
- FBR Integration Profile belongs to Company;
- FBR mappings belong to Company;
- source invoice belongs to Company;
- certification proof belongs to profile/Company.

Never let a convenient global lookup cross Company boundaries.

---

## 42. Backup security

Backups can contain:

- financial data;
- user data;
- private files;
- FBR evidence;
- credentials/configuration;
- encryption-related material.

Security rules:

- do not commit backups to Git;
- do not put them in public storage;
- protect local/off-host copies;
- verify checksums;
- control access;
- restore using correct application release and encryption material.

Backup availability and backup confidentiality are both required.

---

## 43. Deployment service boundary

Production should use controlled Frappe production services such as the supported Nginx/Supervisor deployment model.

Do not use a development server as the normal production process manager.

Keep database/Redis/network exposure restricted according to production architecture.

Use HTTPS before live sensitive integrations.

---

## 44. Immutable release principle

Production deployments should use an explicit approved release identity.

Avoid uncontrolled moving code on client sites.

Security benefits include:

- reproducibility;
- rollback clarity;
- known source provenance;
- auditability;
- easier incident response.

---

## 45. Shared bench risk

A shared bench means application code is common to every site on that bench.

Updating code for one client can affect all cohort sites.

Therefore:

- release scope must be explicit;
- backup must be cohort-aware;
- migration effects must be understood for every site;
- client-specific secrets/data must remain site-separated.

---

## 46. Legacy frozen DocTypes

Historical business DocTypes remain physically present on migrated sites where required for audit/migration evidence.

Current hooks install write guards on frozen legacy models.

Protected lifecycle events include:

- before_insert;
- before_save;
- before_submit;
- before_cancel;
- on_trash.

Do not unfreeze a historical DocType to bypass current ERPNext permissions or workflows.

---

## 47. Why legacy freeze is a security concern

A writable historical Sale/Payment/Stock DocType could create:

- conflicting financial truth;
- unauthorized alternate workflows;
- audit confusion;
- data-exfiltration/reporting ambiguity;
- future migration corruption.

The freeze protects architecture integrity as well as business correctness.

---

## 48. Retired pages and roles

Current permission setup removes known retired Pages and historical role artifacts where appropriate.

Do not reintroduce obsolete Page/role concepts merely to restore an old screenshot/workflow.

Reintroducing an old surface can also expose a retired backend contract.

---

## 49. ERPNext core integrity

Ledgix must not solve authorization problems by editing ERPNext core source.

Use:

- roles;
- DocPerm/Custom DocPerm;
- User Permissions;
- hooks;
- app APIs;
- document events;
- extension fields;
- application services.

Core patching increases upgrade and security drift.

---

## 50. ignore_permissions usage

The codebase contains controlled insert/update operations with ignore_permissions=True inside application services.

This is acceptable only when:

1. the public entrypoint has authorized the user;
2. business validation has passed;
3. the operation is deliberately owned by the application;
4. the target document is the correct native/compliance record.

Do not expose a generic "create anything with ignore_permissions" helper.

---

## 51. Server-side validation over client payload

Never trust the browser for:

- Company;
- account;
- Warehouse;
- Customer/Supplier ownership;
- payment outstanding;
- return quantity;
- FBR mode;
- certification state;
- token;
- Production arm;
- reconciliation state.

Resolve/revalidate authoritative data on the server.

---

## 52. Idempotency as a security/safety control

Current transaction services use client identifiers to reduce duplicate writes.

Examples include:

- client sale ID;
- client payment ID;
- client return ID;
- client purchase ID;
- client stock ID.

Idempotency protects against repeated browser/network requests.

Do not allow an idempotency key to be reused across unrelated parties/Companies without validation.

---

## 53. Concurrency locking

Current services use:

- Company-level locking on several business write paths;
- FBR submission locks for invoice submission.

These controls reduce race conditions.

They do not replace permission checks.

---

## 54. Production crash-window durability

FBR Production POST deliberately commits reconciliation evidence before the external network call.

This is an exceptional explicit transaction boundary.

It protects against duplicate submission after process failure.

Do not remove or move that commit without a full failure-mode review.

---

## 55. Audit integrity

Important security evidence includes:

- ERPNext transaction history;
- GL/stock ledgers;
- FBR Submission Logs;
- Sandbox Certification proof;
- release/backup evidence;
- legacy retirement state;
- tracked configuration changes.

Do not casually delete or rewrite audit evidence.

Where cleanup is required, preserve the required provenance first.

---

## 56. Track changes

Several current Ledgix configuration/compliance DocTypes enable Frappe track_changes.

This improves administrative traceability.

Track changes do not replace immutable transport evidence.

---

## 57. Role assignment changes

Role assignment is security-sensitive.

Production role changes should be intentional and reviewable.

Do not normalize or delete legitimate client roles merely because they were absent from an old baseline.

When migrating/upgrading, preserve valid current production access as the floor unless a deliberate access-removal decision is made.

---

## 58. User/profile distinction

Ledgix User Profile is product/profile metadata.

Frappe User + roles/permissions remain authentication/authorization authority.

Do not treat a Ledgix profile flag as a role grant.

---

## 59. Printing and data leakage

Print formats can expose:

- customer identity;
- seller legal identity;
- prices/tax;
- FBR invoice number/QR.

Print access must therefore follow document permissions and operational need.

Do not expose regulatory/customer data through a public route without explicit authorization design.

---

## 60. Reporting and export

Report/export rights can expose large datasets.

Manager/Admin report roles should still be constrained by:

- site isolation;
- Company scope;
- ERPNext data permissions;
- report implementation filters.

A report that ignores Company/permission boundaries is a security defect even if its Page is role-restricted.

---

## 61. FBR official evidence

Do not fabricate:

- FBR invoice numbers;
- QR;
- Sandbox success;
- certification evidence;
- official reference responses;
- DI logo;
- provider confirmation.

Security/integrity includes preventing false compliance records.

---

## 62. Known Offline integrity

Known Offline declaration requires:

- admin action role;
- exact confirmation;
- valid Production configuration;
- no prior Production POST;
- explicit reason;
- configured provider/client upload window.

This prevents an operator from converting an ambiguous network event into a false "offline-issued" story.

---

## 63. Reconciliation release integrity

Reconciliation release requires exact confirmation that external reconciliation established the invoice was not received by FBR.

The action makes no network call.

It only permits the system to return to a retry-eligible Pending state.

Do not automate this confirmation.

---

## 64. Sandbox evidence integrity

Sandbox Certification proof fields are server-derived.

Production checks re-derive evidence.

This protects against:

- UI checkbox manipulation;
- manually entered fake status;
- cross-company proof;
- mock-only evidence.

---

## 65. Security review checklist for a new API

Before exposing a new whitelisted method:

- [ ] Is login required?
- [ ] Which exact roles are allowed?
- [ ] Does native DocType permission also matter?
- [ ] Is Company scope resolved on server?
- [ ] Is party/account/warehouse ownership validated?
- [ ] Can the request be replayed?
- [ ] Is idempotency needed?
- [ ] Can it expose credentials?
- [ ] Can it mutate audit evidence?
- [ ] Does it use ignore_permissions?
- [ ] Is that usage justified?
- [ ] Does it bypass an FBR safety interlock?
- [ ] Does it create a parallel business authority?
- [ ] Are failure responses sanitized?
- [ ] Is there focused regression coverage?

---

## 66. Security review checklist for migrations

Before changing after_migrate/setup/permissions:

- [ ] Is the operation idempotent?
- [ ] Does it preserve legitimate existing roles?
- [ ] Does it accidentally broaden sensitive permissions?
- [ ] Does DocType JSON agree with centralized permission policy?
- [ ] Does it preserve frozen legacy data?
- [ ] Does it expose/modify credentials?
- [ ] Does it activate FBR Production?
- [ ] Does it affect every site on a shared bench?
- [ ] Has fresh-site behavior been tested?
- [ ] Has upgraded-site behavior been tested?

---

## 67. Security review checklist for FBR

- [ ] Token values remain secret.
- [ ] Company profile is unique/correct.
- [ ] Sandbox evidence is real and re-derived.
- [ ] Production is not armed by readiness/install/migrate.
- [ ] General cutover is intentional.
- [ ] Ambiguous POST becomes Reconciliation Required.
- [ ] No blind retry is introduced.
- [ ] Known Offline cannot follow a prior Production POST.
- [ ] Submission logs/evidence are protected.
- [ ] Return/note semantics are not overstated.
- [ ] Print/QR legal evidence is genuine.
- [ ] Release/backup evidence is present before Production activation.

---

## 68. Current known security-maintenance defect

As of this documentation baseline, the one concrete source-level permission inconsistency identified during consolidation is:

> Ledgix FBR Submission Log JSON is read-only for normal Desk roles, but setup/permissions.py still defines broader System Manager/Ledgix Admin rights and fast_permissions.py can synchronize that broader policy during migrate.

This should be corrected in code and proven with a migrate-level regression before the control is considered durable.

No documentation should conceal this mismatch.

---

## 69. Source map

| Concern | Current source |
|---|---|
| Basic Ledgix role helpers | api/security.py |
| Product visibility | api/product_shell.py |
| Permission policy | setup/permissions.py |
| Permission synchronization | setup/fast_permissions.py |
| Hook registration | hooks.py |
| FBR native role checks | api/fbr_native.py |
| Known Offline role checks | api/fbr_offline.py |
| Activation admin check | api/fbr_activation.py |
| FBR credential schema | Ledgix FBR Integration Profile |
| Submission evidence schema | Ledgix FBR Submission Log |
| Sandbox proof controller | Ledgix FBR Sandbox Certification |
| Legacy write guard | api/legacy_retirement.py |
| Production security runbook source | docs/production/SECURITY.md |

---

## 70. Summary

The Ledgix security model in one sentence is:

> **Frappe/ERPNext roles and permissions are the authorization foundation, Ledgix adds server-side product/compliance checks and fail-closed FBR interlocks, site/company boundaries protect tenant data, and sensitive evidence/credentials must remain protected independently of whatever the UI happens to display.**
