# Ledgix POS — Backup, Deployment and Go-Live

**Audience:** Client owner, implementation lead, Ledgix Admin, technical administrator

## 1. Purpose

This guide explains what a client should expect before:

- initial go-live;
- major update;
- FBR Production activation;
- recovery/rollback.

Technical commands are handled by the responsible system administrator.

The client's job is to ensure the business and acceptance evidence are genuinely complete.

---

## 2. Installation is not go-live

A newly installed Ledgix site is not automatically ready for staff.

Before go-live complete:

- business setup;
- users/roles;
- workflow tests;
- printer/scanner tests;
- backup;
- approved release;
- FBR certification if applicable.

---

## 3. Approved software release

Production should run a specific approved Ledgix release.

The technical administrator records the exact Git release SHA/tag.

This helps:

- identify what code is running;
- reproduce issues;
- perform controlled rollback.

Do not allow ad-hoc untracked code changes on Production.

---

## 4. Production environment

A proper Production site should use:

- HTTPS;
- Nginx;
- Supervisor-managed services;
- protected database/Redis;
- strong credentials.

The local development runner is not the production service model.

---

## 5. One site per client

Each client should have its own Frappe site/database.

This keeps separate:

- business data;
- users;
- FBR tokens;
- backups;
- configuration.

Clients can share infrastructure while still keeping separate sites.

---

## 6. Backup before go-live

Before final go-live, the technical administrator should create a fresh verified backup containing:

- database;
- public files;
- private files;
- secure site configuration recovery input;
- checksums;
- release/version metadata.

The backup should be recoverable and protected.

---

## 7. Off-site backup

A protected off-server/off-host copy is recommended according to client policy.

A server snapshot can be useful but should not be the only Ledgix recovery evidence.

---

## 8. Why backup verification matters

A backup file existing does not prove it is usable.

Ledgix backup tooling verifies:

- required files exist;
- files are non-empty;
- SHA-256 checksums match.

If backup verification fails, do not proceed with update/go-live.

---

## 9. Recovery test

The implementation team should have proven the recovery process.

Production-like restore testing should use a separate non-production recovery site.

Do not experiment by restoring over the live Production source site.

---

## 10. Business readiness

Before handover, Ledgix onboarding should be green.

Verify:

- Business Profile applied;
- Company accounting complete;
- Price List;
- Warehouse where required;
- POS Profile where required;
- payment account mappings;
- named operational users;
- FBR pre-activation safety if FBR enabled.

---

## 11. Manual UAT

Real users should test the workflows they will use.

Software cannot truthfully auto-pass a physical business process.

The current release process records explicit manual UAT evidence.

---

## 12. Base UAT

All applicable clients should test:

- login/navigation;
- normal Sales Invoice flow;
- A4 print;
- payment flow;
- reports relevant to the business.

The exact required UAT set depends on enabled profile features.

---

## 13. POS UAT

POS-enabled clients should test:

- open shift;
- barcode/item selection;
- checkout/payment;
- split payment/change where required;
- thermal receipt;
- hold/resume if used;
- POS return;
- close shift.

Use the real workstation and devices.

---

## 14. Buying/inventory UAT

Buying/inventory clients should test:

- Purchase Order if used;
- Purchase Receipt;
- Purchase Invoice;
- supplier payment;
- stock quantity;
- valuation;
- Stock Entry;
- Stock Reconciliation where advanced inventory is enabled;
- Batch/Serial if used.

---

## 15. Printer UAT

Test actual:

- A4 printer;
- receipt printer;
- paper width;
- margins;
- totals/tax;
- customer/seller details;
- QR/reference area when genuine FBR evidence exists.

Do not approve printer UAT based only on an HTML preview.

---

## 16. Scanner UAT

Test the actual barcode scanner:

- known barcode;
- multiple Items;
- focus/input behavior;
- rapid scans if normal operations require it.

Record scanner mode/model where useful.

---

## 17. FBR UAT is separate

FBR certification and physical device UAT are separate.

You can test non-FBR printing/device workflows before a real FBR token is available.

Do not fabricate FBR invoice numbers/QR just to complete device UAT.

---

## 18. FBR not part of go-live

If the client is going live without FBR Production:

- FBR Production must remain disabled/unarmed;
- normal ERPNext/Ledgix workflows can still be accepted if legally appropriate for that client/use case.

Document the FBR workstream as pending.

---

## 19. FBR part of go-live

If FBR Production is required, go-live must additionally require:

- genuine Sandbox proof;
- Sandbox Certification;
- Production token;
- reviewed mappings/reference data;
- seller identity;
- final print/QR;
- fresh verified backup;
- approved release;
- zero Reconciliation Required;
- explicit Production activation approval.

---

## 20. Final production acceptance

Ledgix has a final release gate run by the technical administrator.

It checks the already deployed site.

It does not deploy new code.

It verifies items such as:

- approved immutable release;
- site health;
- dependency preflight;
- offline/online smoke;
- client readiness;
- historical frozen-data integrity where applicable;
- manual UAT;
- backup/release evidence;
- FBR readiness when explicitly required.

---

## 21. What the client should sign off

Client/business sign-off should confirm the tested scope.

Examples:

- Company/business identity correct;
- staff users/roles correct;
- prices/taxes correct;
- POS works;
- returns work;
- purchasing works where used;
- stock is correct;
- reports reviewed;
- printers/scanners accepted;
- FBR scope accepted if applicable.

Do not sign off untested functionality simply because the software contains it.

---

## 22. Go-live day

Recommended sequence:

1. confirm approved release;
2. confirm fresh backup;
3. confirm client users;
4. confirm opening master data;
5. confirm printers/scanners;
6. confirm FBR state;
7. begin transactions with responsible staff present;
8. observe first POS/B2B transactions;
9. verify accounting/stock effects;
10. if FBR Production is enabled, observe first live FBR transaction carefully.

---

## 23. First-day monitoring

Monitor:

- login/access;
- POS opening/closing;
- payment methods;
- receipts;
- customer outstanding;
- stock;
- printer/scanner issues;
- FBR Failed/Offline/Reconciliation states.

Resolve issues early.

---

## 24. Do not "fix" live data casually

If an issue occurs:

- identify the correct transaction;
- preserve evidence;
- use native correction process;
- escalate technical issues.

Do not:

- delete submitted transactions;
- directly edit GL/Stock Ledger;
- revive old Ledgix ledgers;
- rewrite FBR logs.

---

## 25. Production updates

Before an update:

- schedule maintenance window if required;
- confirm exact release;
- create fresh backup;
- notify relevant staff;
- stop/restrict new transactions during update.

After update:

- run smoke checks;
- verify key workflows;
- confirm site reopened correctly.

---

## 26. Shared infrastructure

If multiple clients share one Ledgix bench, application-code updates affect the entire Ledgix tenant cohort.

The technical administrator must update all Ledgix tenants on that bench together under the approved shared-bench process.

A client should not be silently moved to a different release while sharing the same bench.

---

## 27. Rollback

If an update fails seriously, the technical team can roll back using:

- previous known-good Ledgix release;
- matching pre-update verified site backup.

Rollback is not simply "install old code over the new database."

The database/files and matching application version must be treated as a recovery pair.

---

## 28. Maintenance mode

During update/recovery, the site may be placed in maintenance mode.

If the update fails, the site may deliberately remain in maintenance until it is safe to reopen.

Do not pressure the technical operator to disable maintenance before the site state is understood.

---

## 29. Backups after go-live

Continue regular backups according to business/legal requirements.

Monitor that backups are actually verified.

Also create a fresh verified backup before:

- software update;
- major configuration change;
- FBR Production activation;
- destructive maintenance.

---

## 30. Client records to retain

Keep an operational record of:

- site/domain;
- Company;
- Business Profile;
- go-live date;
- current release;
- latest verified backup;
- FBR mode/certification state;
- printer/scanner models;
- responsible client administrator.

Do not store passwords/tokens in this general handover record.

---

## 31. Go-live checklist

### Business

- [ ] Company/accounting reviewed
- [ ] customers/items/suppliers ready
- [ ] pricing reviewed
- [ ] tax reviewed
- [ ] opening stock correct
- [ ] POS Profile correct

### Users

- [ ] named Admin
- [ ] named Manager(s)
- [ ] named Cashier(s) where needed
- [ ] role tests complete

### Operations

- [ ] Sales Invoice tested
- [ ] payment tested
- [ ] return/refund tested
- [ ] POS tested if enabled
- [ ] purchasing tested if enabled
- [ ] inventory tested if enabled
- [ ] reports reviewed

### Devices

- [ ] A4 print
- [ ] thermal print
- [ ] scanner
- [ ] cash/payment hardware as applicable

### Technical

- [ ] approved release
- [ ] verified fresh backup
- [ ] recovery plan known
- [ ] online/offline smoke green
- [ ] final acceptance gate green

### FBR if required

- [ ] Sandbox genuinely proven
- [ ] certification complete
- [ ] Production token secure
- [ ] mappings/reference reviewed
- [ ] final QR/print accepted
- [ ] zero Reconciliation Required
- [ ] fresh backup
- [ ] explicit activation approved
- [ ] first live transaction observed

---

## 32. Summary

> **Go live only after business setup, real-user UAT, devices, backup/recovery and the approved release are proven; if FBR Production is in scope, add genuine Sandbox certification and explicit live activation rather than treating installation as authorization.**
