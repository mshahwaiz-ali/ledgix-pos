# Ledgix — Client Acceptance, Production Provisioning and Release Hardening

**Status:** NEXT WORKSTREAM — PLANNED, NOT STARTED  
**Migration status:** ERPNext Core Migration Phases 0–13 COMPLETE  
**Final migration gate HEAD:** `d813d26d16a11665522da98c7bd542a7cc09c53f`  
**Supported stack:** Frappe `15.113.4` + ERPNext `15.121.3` + `ledgix_saas`  
**Codebase rule:** one Ledgix codebase; client differences are configuration only; no client forks.

---

## 1. Purpose

The ERPNext Core Migration is finished. This workstream does **not** add a Phase 14 and does not reopen migration architecture.

The goal now is to make the completed ERPNext-backed Ledgix product safe, repeatable and supportable for real client rollout:

- provision a clean client site from zero;
- install/update production safely;
- prove backup and rollback before live use;
- support multi-site SaaS deployment without code forks;
- onboard each client through a controlled checklist;
- select and validate the correct Business Profile;
- move FBR from Sandbox to Production only through an explicit activation gate;
- configure roles/users, printing and POS devices;
- validate accounting, warehouse and POS prerequisites;
- run profile-specific smoke/UAT tests;
- pass one consolidated production release gate.

ERPNext remains the authoritative business engine. Phase 12 historical Ledgix business data remains frozen audit history.

---

## 2. Existing foundations to preserve

The repository already contains useful deployment/runtime foundations that this workstream must harden rather than replace:

- `deploy/production_setup.sh` — production orchestration;
- `deploy/deploy_update_safe.sh` — backup + update + maintenance + dependency + exact app sync + build/migrate/restart;
- `deploy/backup_safe.sh` — site backup with files;
- `deploy/smoke_test.sh` — offline/online infrastructure smoke checks;
- `deploy/ensure_erpnext.sh` — ERPNext dependency/alignment;
- `scripts/run_ledgix_client_preflight.sh` — Frappe/ERPNext/Ledgix v15 site dependency preflight;
- `/app/ledgix-setup` — configuration-only client setup wizard;
- `docs/production/client_lifecycle.md` — operational client lifecycle runbook.

Release hardening should consolidate these paths, remove unsafe production assumptions and add missing evidence/rollback gates. It must not create a second deployment stack unless an existing helper cannot safely express the requirement.

---

## 3. Non-negotiable production rules

1. **One codebase.** No per-client implementation branches or copied application forks.
2. **Pinned release identity.** Production deploys must record and verify an explicit approved commit/tag rather than silently treating a moving `main` as release identity.
3. **ERPNext authority.** No release tooling may revive legacy Ledgix financial/stock/business writes.
4. **Phase 12 stays frozen.** Production tooling must not unfreeze historical Ledgix business DocTypes during normal deploy/update/onboarding.
5. **Per-site isolation.** Each client uses its own Frappe site/database/configuration/FBR credentials/backups.
6. **Fail closed.** Missing dependency, backup, accounting prerequisite, invalid POS configuration or unresolved FBR activation requirement blocks the corresponding production step.
7. **No secret defaults for real clients.** Demo convenience credentials must never become an implicit production credential path.
8. **Rollback is prepared before deploy.** A release is not production-ready until previous application revision plus database/public/private-files restore inputs are known.
9. **Sandbox before FBR Production.** Production submission remains an explicit operator/compliance activation, never a side effect of a Business Profile.
10. **Client evidence is retained.** Provisioning, acceptance, release SHA, backup and FBR environment state must be recorded per site.

---

## 4. Workstream R0 — Release baseline and deployment audit

### Goal

Turn the successful migration build into a clearly identified release candidate without changing business architecture.

### Work

- freeze the migration closure reference at `d813d26d16a11665522da98c7bd542a7cc09c53f`;
- audit every script under `deploy/` against the post-Phase-13 architecture;
- identify legacy-only smoke assertions and replace them with ERPNext-native/product-shell/setup/FBR checks where appropriate;
- ensure production paths never require modifying ERPNext core;
- define an immutable release identity contract: approved Git SHA/tag, Frappe version, ERPNext version and Ledgix app revision;
- remove or fail closed on production-unsafe default credentials;
- make site/domain/bench/release ref explicit inputs instead of relying on a single demo-site default where production safety requires specificity.

### Exit gate

- deployment helper inventory documented;
- no production command depends on an implicit weak credential;
- release SHA/tag is an explicit deploy input and recorded output;
- post-Phase-13 architecture checks are the active checks.

---

## 5. Workstream R1 — Clean fresh-client provisioning

### Goal

Prove a client can be created from a clean supported bench/site without migration-era data or manual code edits.

### Target sequence

```text
Approved Ledgix release
        |
        v
Supported Frappe/ERPNext v15 bench
        |
        v
Create isolated client site/database
        |
        v
Install ERPNext then Ledgix
        |
        v
Migrate + build
        |
        v
Run dependency/preflight checks
        |
        v
Configure ERPNext company/accounting/warehouse prerequisites
        |
        v
Run /app/ledgix-setup
        |
        v
Apply one Business Profile
        |
        v
Configure roles/users + FBR + devices/printing
        |
        v
Profile-specific UAT
```

### Required proof

- fresh site has only standard ERPNext business authority plus Ledgix extensions;
- no client-specific code edit is required;
- all five Business Profiles can be selected from the same codebase;
- setup remains configuration-only;
- dependency preflight passes;
- the chosen profile reaches readiness with only standard ERPNext configuration and Ledgix product settings.

---

## 6. Workstream R2 — Production installation and update procedure

### Goal

Have one documented, reproducible install path and one documented, reproducible update path.

### Fresh install procedure must cover

- host/OS prerequisites;
- Frappe bench preparation;
- ERPNext v15 dependency installation;
- Ledgix app installation;
- site creation;
- domain/HTTPS;
- Supervisor/Redis/Socket.IO/Nginx services;
- migrate/build/cache refresh;
- per-site dependency preflight;
- initial administrator credential handoff without repository-stored secrets;
- initial release identity capture.

### Update procedure must cover

- clean working tree check;
- exact current release SHA capture;
- verified backup before code movement;
- fetch approved target ref;
- maintenance mode;
- ERPNext dependency/version alignment;
- exact Ledgix app sync;
- asset build and site migrate;
- process restart/reload;
- dependency + online smoke checks;
- release SHA verification after deploy;
- maintenance exit only after required checks pass.

### Hardening requirement

`deploy/deploy_update_safe.sh` currently provides much of this shape. The release work should harden it around immutable target refs, backup verification, rollback metadata and per-site evidence instead of creating a competing updater.

---

## 7. Workstream R3 — Backup, restore and rollback

### Goal

A backup is not considered a release safeguard until restoration is proven.

### Backup contract

Before every production install/update/FBR Production switch/destructive maintenance action, retain:

- database backup;
- public files backup;
- private files backup;
- site config inputs required for restoration, handled securely;
- current Git SHA/tag;
- target Git SHA/tag;
- Frappe/ERPNext/Ledgix versions;
- timestamp/site/domain;
- operator/rollback owner;
- backup location and an off-host/off-server copy where appropriate.

### Restore drill

On a non-production recovery target:

1. restore database;
2. restore public/private files;
3. restore the matching application revision;
4. migrate only if required by the selected rollback strategy;
5. run dependency and offline smoke checks;
6. verify login and representative ERPNext/Ledgix reads;
7. verify Phase 12 history remains frozen on migrated client sites.

### Rollback gate

No production release is approved until the previous known-good release and its restorable site backup are identified.

---

## 8. Workstream R4 — Multi-site SaaS deployment model

### Architecture

- one shared Ledgix repository/application revision;
- one Frappe site per client;
- one database per site;
- independent site config and secrets;
- independent Business Profile;
- independent Company/POS/Warehouse configuration;
- independent FBR credentials/environment;
- independent backups and release evidence.

Small clients may share infrastructure/bench when operational limits allow. A larger client may move to a dedicated host/bench without changing application code.

### Hardening work

- make deployment/backup/smoke commands site-explicit;
- prevent accidental cross-site updates where only one site was approved;
- define shared-bench update policy when multiple client sites consume the same app revision;
- define sequencing/maintenance strategy for shared-bench upgrades;
- retain per-site preflight/UAT evidence even when application code is shared;
- document tenant add/remove/restore procedures.

### Rule

Feature differences are expressed through Business Profile, ERPNext permissions/settings and Ledgix configuration — never a client fork.

---

## 9. Workstream R5 — Client onboarding checklist

Every new client gets a single provisioning record/checklist.

### Identity and release

- client/site/domain;
- approved release SHA/tag;
- installed Frappe/ERPNext/Ledgix versions;
- timezone/currency/country;
- administrator handoff owner.

### ERPNext business prerequisites

- Company;
- fiscal/accounting configuration and Chart of Accounts;
- required receivable/payable/cash/bank/payment accounts;
- taxes/accounts/templates required by the client flow;
- Selling Price List;
- Mode(s) of Payment with correct account mappings;
- Customer defaults, including walk-in customer when POS is used;
- Warehouse(s) for stock-enabled profiles;
- stock settings/valuation/opening stock where applicable;
- POS Profile for POS-enabled profiles;
- suppliers/purchasing prerequisites when buying is enabled.

### Ledgix product configuration

- Business Profile selected;
- Setup Wizard readiness is green;
- setup audit metadata recorded;
- Ledgix branding/print settings;
- Ledgix FBR Settings present;
- no legacy business write path enabled.

### Operational setup

- users created individually;
- roles assigned by job function;
- printer/device mapping recorded;
- scanner flow checked where required;
- backup destination confirmed;
- support/escalation contacts recorded.

---

## 10. Business Profile acceptance matrix

### Invoice + FBR Only

Required operational proof:

- Sales Invoice;
- receivable/payment flow;
- Credit Note/return where used;
- A4 print;
- FBR Sandbox flow;
- no POS/inventory prerequisite forced by Ledgix.

### Small Retail

Required proof:

- POS Opening;
- item search/barcode scan;
- POS Invoice;
- payment/change/split tender as configured;
- POS return;
- POS Closing;
- stock effect;
- thermal print;
- FBR Sandbox flow.

### Full Retail

Small Retail plus:

- buying/receipt/valuation;
- Stock Entry/Reconciliation;
- Batch/Serial workflows where the client uses them.

### B2B

Required proof:

- customer/receivable flow;
- Sales Invoice;
- partial/full payment;
- Credit Note/return;
- B2B/A4 print;
- FBR Sandbox flow;
- no POS requirement unless the profile is changed.

### Mixed

Run both Retail and B2B paths and confirm the same ERPNext business authority under both UX paths.

---

## 11. Roles and users

### Production rules

- no shared Administrator account for daily operations;
- create named users;
- use ERPNext/Frappe permissions as authorization authority;
- Business Profile/product shell only curates navigation;
- verify Ledgix Cashier, Ledgix Manager and Ledgix Admin behavior relevant to the client;
- System Manager remains a platform-administration role, not a cashier shortcut;
- test denied access for at least one role boundary as part of UAT;
- credential/MFA/session policy follows the deployment environment and client policy without hard-coding secrets in the repository.

---

## 12. FBR Sandbox -> Production activation checklist

Production activation is a separate release/compliance gate.

### Sandbox prerequisites

- seller identity fields complete;
- Sandbox environment selected;
- valid Sandbox token/credentials configured securely;
- representative Sales Invoice tested;
- representative POS Invoice tested when POS is enabled;
- applicable return/Credit Note tested;
- FBR Submission Log evidence retained;
- official reference/QR persistence and print verified;
- retry/idempotency/reconciliation behavior checked for the exercised flow;
- no real Production call is made during Sandbox/UAT.

### Production switch prerequisites

- client/compliance owner approves activation;
- Production seller identity and credentials verified;
- fresh backup captured and verified;
- approved release SHA recorded;
- no ambiguous/unreconciled FBR submission state exists;
- Product Profile and native ERPNext source document flow are already accepted;
- environment switch is explicit;
- first live submission is observed and its official response/reference recorded;
- rollback/disable procedure is known before the switch.

The Business Profile enabling FBR is not, by itself, permission to submit to Production.

---

## 13. Printing and POS device acceptance

### Printing

For the actual client printer/browser/device combination verify:

- Sales Invoice/Credit Note A4 format;
- thermal POS Invoice format and configured paper width;
- FBR official reference visibility;
- QR renders and scans where applicable;
- company branding/header/footer;
- tax totals and legal snapshot fields;
- return/credit-note identification;
- no legacy Ledgix Sale print target is used for active business transactions.

### POS devices

Where used, record and test:

- cashier workstation/browser;
- receipt printer;
- barcode scanner (keyboard-wedge/other supported client mode);
- cash drawer integration only if the chosen printer/workflow supports it;
- network stability/reconnect behavior relevant to the deployment;
- barcode scan -> item selection -> quantity -> checkout path;
- user sign-in/role behavior on each device.

No device-specific code fork should be introduced for normal hardware differences.

---

## 14. Smoke and UAT strategy

Use two layers.

### Automated release smoke

The hardened consolidated release gate should verify at minimum:

- repository validation/local CI;
- exact release SHA/tag;
- Frappe/ERPNext/Ledgix installed versions;
- ERPNext required-app contract;
- target site exists and is reachable;
- migration/build state is current;
- `/login`, `/app`, Ledgix assets and Socket.IO respond;
- `/app/ledgix-setup` is installed;
- selected Business Profile/setup readiness state is valid;
- Phase 12 freeze remains intact on migrated sites;
- no legacy business write route is active;
- FBR environment is reported explicitly;
- backup metadata exists for production updates.

### Manual/profile-specific UAT

Run only the workflows relevant to the selected Business Profile using client configuration/devices. Record pass/fail and transaction references. Do not manufacture irrelevant modules for an invoice-only client.

---

## 15. Consolidated production release gate

The target is one release command/gate, not a collection of unrelated manual checks.

Planned interface (exact implementation may reuse/extend existing helpers):

```bash
bash scripts/run_ledgix_production_release_gate.sh <site> --url <https-url> --release <git-ref>
```

The final implementation should fail closed if any required release criterion is missing.

### Required final evidence

- `release_ref` resolves to the deployed Git SHA;
- supported Frappe/ERPNext major versions and expected pinned release versions are recorded;
- `ledgix_saas` is installed;
- client dependency preflight passes;
- backup/rollback checkpoint is identified;
- selected Business Profile is recorded;
- setup readiness is green for that profile;
- online/offline smoke checks pass;
- profile-specific UAT evidence is attached/recorded;
- FBR environment is explicit and Production activation evidence is required only when Production is intended;
- print/device checks relevant to the client are recorded;
- Phase 12 historical freeze is unchanged on migrated sites;
- release record contains site/domain/date/operator/previous SHA/new SHA;
- no per-client code fork exists.

Production release closes only when the consolidated gate plus client UAT are green.

---

## 16. Implementation order

Execute this workstream in coherent batches, with one consolidated gate after each meaningful boundary:

1. **R0 + R2:** audit and harden the existing install/update/deploy helpers around immutable release identity and production-safe inputs;
2. **R3:** backup verification, restore drill and rollback evidence;
3. **R1 + R4:** clean fresh-client provisioning and multi-site-safe site parameterization;
4. **R5:** onboarding/readiness evidence and role/accounting/warehouse prerequisites;
5. **FBR activation:** Sandbox-to-Production gate and runbook hardening;
6. **printing/devices/UAT:** real client hardware and profile-specific acceptance matrix;
7. **final consolidated production release gate:** combine automation + recorded UAT without rerunning obsolete migration gates individually.

Do not ask operators to rerun Phases 10–13 as separate production steps. The migration gates are historical architecture/cutover evidence; the production release gate should verify the current release/site invariants that matter for deployment.

---

## 17. Definition of done

This workstream is complete when:

- a clean client can be provisioned from an approved release with no code changes;
- an existing client can be updated through a safe, repeatable, rollback-ready flow;
- a backup has been restoration-tested;
- multi-site operation is explicit and site-isolated;
- all supported Business Profiles have a production acceptance checklist;
- FBR Sandbox -> Production activation is controlled and auditable;
- roles/users/printing/POS devices are included in onboarding evidence;
- accounting/warehouse/POS prerequisites fail closed when missing;
- one consolidated production release gate exists and passes on the intended release candidate;
- the product remains one codebase with ERPNext as the authoritative business engine and no client forks.
