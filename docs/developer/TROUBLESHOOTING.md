# Ledgix POS — Troubleshooting

**Status:** CURRENT / CANONICAL DEVELOPER GUIDE  
**Architecture baseline:** 2026-09-26 final forensic audit

## 1. Purpose

This guide provides current diagnostic paths for Ledgix.

The most important troubleshooting rule is:

> **Diagnose the authoritative ERPNext/Ledgix layer first; do not repair current operation by reviving frozen legacy ledgers or modifying ERPNext core.**

---

## 2. Start with the failure domain

Classify the issue first.

### Local runtime

- site not opening;
- bench process;
- host resolution;
- assets.

### Dependency/schema

- app missing;
- import error;
- migrate failure;
- DocType/field missing.

### Business transaction

- sale/payment;
- return;
- purchase;
- stock.

### Permission/UI

- Page missing;
- button missing;
- permission denied;
- wrong role exposure.

### FBR

- readiness;
- payload;
- token/mode;
- Offline Pending;
- Reconciliation Required.

### Deployment/recovery

- update refused;
- smoke failed;
- maintenance mode;
- backup/restore.

Use the subsystem-specific current document after classification.

---

## 3. Local site does not open

Run:

    ./start.sh --status
    ./start.sh --smoke --site ledgix-erpnext.local

Check:

- canonical site exists;
- /etc/hosts mapping if required;
- port 8000 belongs to the intended bench;
- Frappe/ERPNext/Ledgix installed.

Repair with:

    ./site_setup.sh --ensure

before considering reset.

---

## 4. Do not reset too early

Local reset destroys active local site data.

Use only when deliberate:

    ./site_setup.sh \
      --reset \
      --site ledgix-erpnext.local \
      --confirm "RESET ledgix-erpnext.local"

If the canonical acceptance dataset matters, verify whether reset is appropriate first.

---

## 5. Required app missing

Check:

    bench --site <site> list-apps
    bench version --format plain

Required stack:

- frappe;
- erpnext;
- ledgix_saas.

If ERPNext is missing, do not install Ledgix as a standalone business engine.

Use the supported local or production provisioning path.

---

## 6. Python import error

Check:

- repository app exists at apps/ledgix_saas;
- bench app path is synchronized;
- editable package install is healthy;
- correct bench Python is used.

Local safe repair:

    ./site_setup.sh --ensure

Run:

    bash scripts/ci_local.sh

---

## 7. Migration failure

Do not rerun blindly without reading the first real exception.

Check:

- current release SHA;
- framework versions;
- patches.txt;
- after_migrate traceback;
- database/schema state;
- whether the site is fresh or migrated.

Local after correction:

    bench --site <site> migrate

Production should use approved updater/recovery procedure, not manual experimentation.

---

## 8. Asset/UI stale after successful migrate

Run in appropriate environment:

    bench build --app ledgix_saas
    bench --site <site> clear-cache
    bench --site <site> clear-website-cache

Then refresh browser.

Production should do this through release tooling where possible.

---

## 9. Page not visible

Check three different layers:

1. Business Profile/product shell visibility;
2. Page role assignment;
3. user roles/permissions.

A hidden Page is not always a permission error.

A visible Page is not proof of API authorization.

---

## 10. Permission denied

Inspect:

- current Frappe user;
- assigned roles;
- DocPerm/Custom DocPerm;
- Page/Report roles;
- User Permissions;
- endpoint-specific role checks.

Do not fix by assigning System Manager broadly.

Do not fix by disabling server checks.

---

## 11. FBR Submission Log unexpectedly editable after migrate

Known source inconsistency at this documentation baseline:

- DocType JSON intends read-only evidence;
- setup/permissions.py still contains older broad System Manager/Ledgix Admin rights;
- fast_permissions can apply centralized policy during migrate.

If effective permissions are broader than intended:

- do not manually edit Submission Logs;
- inspect Custom DocPerm after migrate;
- treat this as the known code-maintenance defect;
- fix centralized policy and add migrate-level regression in a dedicated code change.

Do not weaken the JSON.

---

## 12. Business Profile looks wrong

Inspect:

- Ledgix Business Profile singleton;
- setup_company;
- selected profile;
- setup_complete;
- resolved Selling Price List/Warehouse/POS Profile;
- client_setup evaluation;
- client_readiness blockers.

Business Profile affects product exposure/configuration.

It does not change business authority.

---

## 13. POS cannot open shift

Check:

- active Company;
- enabled POS Profile for user;
- valid Warehouse;
- configured Modes of Payment;
- existing active POS Opening Entry;
- user permissions.

Do not create a Ledgix POS Shift manually.

---

## 14. POS checkout says no active shift

Current retail checkout requires active ERPNext POS Opening Entry.

Open the native Ledgix/ERPNext shift workflow.

Do not bypass the check.

---

## 15. POS price unexpected

Inspect:

- POS Profile Selling Price List;
- ERPNext Item Price effective dates/UOM;
- Pricing Rules;
- Customer context;
- manager override audit where applicable.

Do not treat a raw historical Ledgix Item Price as current authority.

---

## 16. POS stock unexpected

Inspect ERPNext:

- Bin;
- Stock Ledger Entry;
- Warehouse;
- purchase receipts/invoices;
- sales/returns;
- Stock Entry/Reconciliation.

Do not write Ledgix Stock Movement to compensate.

---

## 17. Split payment rejected

Check:

- Mode of Payment is on POS Profile;
- amount positive;
- required reference number supplied;
- Company account mapping exists;
- partial payment setting;
- over-tender/change requires eligible Cash mode.

---

## 18. POS duplicate sale concern

Check client sale ID on native POS Invoice.

Current service is idempotency-aware.

Do not create another sale until you know whether the first request committed.

---

## 19. POS return fails

Inspect:

- original is submitted POS Invoice;
- original is not itself a return;
- active POS opening exists;
- return reason supplied;
- selected source rows match;
- requested quantity <= returnable quantity.

Do not create Ledgix Sales Return as workaround.

---

## 20. POS closing fails

Inspect:

- active POS Opening Entry;
- requested shift ID;
- unclosed POS Invoices;
- payment reconciliation;
- cash mode;
- ERPNext POS Closing Entry traceback.

Do not manually mark the historical Ledgix shift closed.

---

## 21. B2B invoice price/tax issue

Inspect native:

- Customer;
- Selling Price List;
- Item/UOM;
- Pricing Rule;
- Tax Category;
- Sales Taxes and Charges Template;
- Item Tax Template;
- tax accounts.

Run/evaluate current native tax contract.

Do not reintroduce legacy managed tax rows.

---

## 22. Customer payment rejected

Check:

- amount > 0;
- Customer/Company match;
- invoice submitted;
- invoice positive outstanding;
- allocation <= outstanding;
- Mode of Payment exists;
- Company payment account exists;
- required reference number present.

For unapplied advance, use native ERPNext Payment Entry rather than fake allocation.

---

## 23. Outstanding looks wrong

Authoritative fields/evidence:

- Sales Invoice.grand_total;
- Sales Invoice.outstanding_amount;
- Payment Entry references;
- Credit Notes;
- GL.

Do not calculate current AR from Ledgix Sale/Payment history.

---

## 24. Refund fails

Check:

- source is submitted return Sales Invoice;
- Credit Note has refundable outstanding;
- requested refund <= refundable outstanding;
- ERPNext mapper resolves Payment Type Pay;
- Mode of Payment account exists.

A Credit Note alone does not mean refund has been paid.

---

## 25. Exchange mismatch

Current exchange is:

- Credit Note;
- replacement Sales Invoice.

Inspect each separately.

Any monetary difference remains native outstanding/payment state.

Do not search for a hidden custom exchange ledger.

---

## 26. Purchase Order/Receipt/Invoice issue

Inspect native chain:

    Purchase Order
      -> Purchase Receipt
      -> Purchase Invoice
      -> Payment Entry

Check:

- Supplier;
- Item;
- quantity;
- Warehouse;
- source document submitted;
- client idempotency ID.

---

## 27. Direct purchase stock duplicated

If Purchase Invoice used update_stock=1, do not also create a duplicate receipt for the same physical receipt.

Inspect Stock Ledger Entry vouchers to identify double posting.

Correct through native lifecycle.

---

## 28. Supplier payment rejected

Check:

- Purchase Invoice submitted/non-return;
- outstanding positive;
- payment <= outstanding;
- Mode of Payment account configured for Company.

---

## 29. Stock mismatch

Inspect:

- Stock Ledger Entry;
- Bin;
- Warehouse;
- voucher chronology;
- return documents;
- batch/serial;
- Stock Reconciliation.

Do not directly edit SLE/Bin.

Do not post a fake Ledgix stock movement.

---

## 30. Negative stock error

This is ERPNext stock-policy/chronology behavior.

Check:

- stock availability;
- posting dates/times;
- Warehouse;
- stock settings;
- source transactions.

Fix the real chronology/configuration.

---

## 31. Batch error

Check:

- Item has batch tracking enabled;
- Batch exists;
- Batch belongs to same Item;
- Warehouse has quantity;
- correct batch passed to native voucher.

Do not use Ledgix Stock Lot as current batch authority.

---

## 32. Serial error

Check:

- Item serial configuration;
- native Serial No;
- warehouse availability;
- exact quantity/serial count;
- native bundle behavior.

Do not modify Ledgix Stock Serial.

---

## 33. FBR readiness fails

Start with:

- source submitted Sales/POS Invoice;
- Company Integration Profile;
- seller identity;
- buyer identity;
- immutable V2 snapshot;
- Item mappings;
- Tax Component mappings;
- official references;
- mode;
- token presence;
- certification state.

Use FBR_ARCHITECTURE.md for exact boundaries.

---

## 34. FBR snapshot missing

Snapshot capture happens before submit when an active FBR profile applies.

For an already submitted invoice missing required V2 snapshot:

- do not reconstruct payload from current mutable masters and send anyway;
- inspect why profile/hook/schema was not active at submit;
- use supported migration/correction workflow if one exists.

Payload builder intentionally requires verified persisted snapshot.

---

## 35. Snapshot hash failure

Do not overwrite hash/JSON to make it pass.

Investigate:

- invoice/item mutation;
- schema/version mismatch;
- corruption;
- incorrect migration.

Snapshot mismatch is designed to fail closed.

---

## 36. FBR mapping Needs Review

Review against authoritative current FBR/provider evidence.

Do not clear Needs Review just to unblock payload.

Especially confirm:

- HS Code;
- UOM;
- sale type;
- tax basis;
- SRO references;
- effective dates.

---

## 37. Sandbox ready but not certified

This is normal.

sandbox_ready means configuration can exercise Sandbox.

sandbox_proven / certification requires real persisted Validate/POST proof.

Do not manually mark certification Complete.

---

## 38. FBR Production not ready

This is expected until genuine prerequisites are complete.

Current baseline intentionally has:

- Production Ready: NO;
- Production Active: NO;
- general V2 cutover: false.

Do not "fix" this by toggling fields directly.

---

## 39. General cutover blocks FBR traffic

Current code has:

    V2_NETWORK_CUTOVER_ACTIVE = False

General FBR network calls are fail-closed.

A narrow explicit local Sandbox exercise exists for certification work.

Do not change the cutover while troubleshooting ordinary local behavior.

---

## 40. Reconciliation Required

Stop.

Do not repeatedly retry.

This status means a Production POST may have reached FBR but local outcome is uncertain.

Required action:

- reconcile externally with FBR/PRAL/provider;
- determine whether invoice was received;
- only use the supported release action after confirmed not received.

---

## 41. Reconciliation release

Supported confirmation:

    CONFIRMED NOT RECEIVED BY FBR

Requires admin role.

The release action makes no network call.

It changes state to retry-eligible Pending only after external reconciliation.

---

## 42. Offline Pending

Known Offline is separate from Reconciliation Required.

Check:

- Production mode;
- Production token;
- Production arm;
- completed Sandbox certification;
- Known Offline policy;
- configured provider/client upload window;
- no prior Production POST.

Never convert an ambiguous POST into Offline Pending.

---

## 43. Offline upload not sent

If controlled offline upload makes no network call, current implementation must preserve Offline Pending.

Inspect readiness/transport blocker.

Do not clear Offline Pending manually.

---

## 44. FBR Submission Log missing

Check:

- source invoice FBR state;
- whether transport/readiness path actually created an attempt;
- linked log field;
- server traceback.

Do not create a fake log manually.

---

## 45. Print missing FBR QR/reference

Check:

- native source invoice;
- official FBR number/status;
- persisted QR/context;
- correct current Ledgix ERPNext print format;
- print-format setup after migrate.

Do not fabricate QR/reference for layout testing and then treat it as certification.

---

## 46. Backup verification fails

Run:

    bash deploy/verify_backup_set.sh \
      --metadata <file> \
      --site <site>

If it fails:

- do not update/deploy;
- identify corrupt/missing artifact;
- create a fresh safe backup.

Never ignore checksum failure.

---

## 47. Restore drill refuses target

Confirm:

- source != target;
- target site exists;
- target has non-production recovery marker;
- marker content exactly matches target;
- exact confirmation phrase supplied;
- code release matches backup.

The refusal is a safety feature.

---

## 48. Restore loses Password fields

Likely encryption-key mismatch.

Verify the restore used the source encryption key while preserving target DB identity.

Do not copy full source site_config over target blindly.

---

## 49. Single-site updater refuses shared bench

Expected behavior.

Use:

    deploy/deploy_update_shared_safe.sh

with the complete Ledgix tenant cohort.

Do not bypass the check.

---

## 50. Shared updater says cohort mismatch

Discover which sites use ledgix_saas.

Every such site must be explicitly listed.

Do not remove a tenant from the list merely to proceed faster.

---

## 51. Shared updater fails one online smoke

The full cohort returns to maintenance.

Investigate the failing tenant before reopening all sites.

Do not leave a partial cohort live on the new shared code.

---

## 52. Production stuck in maintenance after failed update

This is intentional fail-closed behavior.

Inspect:

- update error;
- current repo SHA;
- migrate status;
- smoke result;
- pre-update backup;
- previous release.

Choose repair or rollback.

Do not turn maintenance off first.

---

## 53. Production 502 / Supervisor issue

Check:

    sudo supervisorctl status
    sudo nginx -t

Inspect bench logs.

Do not switch to bench start as a production workaround.

---

## 54. Wrong site / 404

Check:

- DNS;
- Nginx host config;
- site directory;
- host_name;
- maintenance mode.

Useful upstream test:

    curl -I -H "Host: client.example.com" http://127.0.0.1

---

## 55. Final release gate fails

Review the failing category.

Possible blockers include:

- immutable release mismatch;
- preflight/smoke;
- client readiness;
- Phase 12 frozen snapshot;
- manual UAT;
- verified backup/release evidence;
- FBR Production prerequisites if requested.

Do not mark Production accepted manually.

---

## 56. Phase 12 snapshot mismatch

Treat as serious historical-integrity failure.

Do not generate a new snapshot over the changed rows.

Investigate:

- unauthorized legacy write;
- restore mismatch;
- rollback operation;
- migration bug.

Normal operation should leave Frozen history unchanged.

---

## 57. Legacy record says read-only

That is expected after migration.

Correct the authoritative ERPNext document instead.

Only controlled rollback/migration work may unfreeze legacy ledgers.

---

## 58. Old doc says phase pending/active

Check whether the document is under:

    docs/archive/migration/

Archived phase-time status is historical.

Use current developer docs and current implementation.

---

## 59. When to inspect hooks.py

Inspect hooks.py when:

- API behavior differs from the file name you expected;
- old method calls a new service;
- FBR hook runs on invoice submit;
- Payment Entry validation appears unexpectedly;
- migrate changes permissions;
- legacy writes are blocked.

hooks.py is the runtime wiring map.

---

## 60. When to inspect current service vs old module

Prefer current services:

- erpnext_pos.py;
- erpnext_selling.py;
- erpnext_buying_inventory.py;
- erpnext_tax_authority.py;
- fbr_v2_*.

Do not assume generic older sales/stock/tax modules are current authority.

Trace caller/hook first.

---

## 61. Do not troubleshoot by changing ERPNext core

Never patch ERPNext source just because a Ledgix integration bug is inconvenient.

Use:

- hooks;
- Custom Fields;
- services;
- patches;
- application code;
- documented ERPNext extension points.

---

## 62. Do not troubleshoot by changing accounting

Never modify real accounting state only to satisfy a test.

If a test expectation is stale:

- fix test/adapter;
- document the new authority;
- preserve correct accounting.

---

## 63. Minimal diagnostic sequence

For most issues:

1. identify authoritative document/service;
2. inspect current source + hooks;
3. reproduce locally if safe;
4. run focused test;
5. inspect native ERPNext state;
6. inspect Ledgix metadata only as extension evidence;
7. fix application integration;
8. add regression;
9. migrate/build if required;
10. rerun appropriate gate.

---

## 64. Source map

| Issue | Start with |
|---|---|
| Runtime wiring | hooks.py |
| POS | services/erpnext_pos.py |
| Sales/payments | services/erpnext_selling.py |
| Purchasing/stock | services/erpnext_buying_inventory.py |
| Tax | services/erpnext_tax_authority.py |
| FBR | api/fbr_native.py + services/fbr_v2_readiness.py |
| Permissions | setup/permissions.py + fast_permissions.py |
| Legacy freeze | api/legacy_retirement.py |
| Deployment | deploy/deploy_update*_safe.sh |
| Backup | deploy/backup_safe.sh |
| Release acceptance | api/release_acceptance.py |

---

## 65. Summary

> **Troubleshoot Ledgix by following the current authority boundary: inspect native ERPNext business state, current Ledgix services/hooks and controlled compliance evidence; do not revive frozen legacy engines, bypass fail-closed FBR states, alter ERPNext core or mutate accounting simply to make the symptom disappear.**
