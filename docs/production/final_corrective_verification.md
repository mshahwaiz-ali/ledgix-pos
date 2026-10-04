# Ledgix final corrective verification

The final corrective batch implements fix groups A through M and preserves the current Federal POS/IMS V1 safety contracts. Source, static, runtime and local site checks pass. Guarded migration and both current app builds succeeded. Financial and historical state remained unchanged. This records local software verification; external Sandbox acceptance and Production approval remain incomplete.

## Source and environment

Starting `main` HEAD and fetched `origin/main` both equalled `df22d531133894e70f9901779978770042cc93a2`; the owning repository was clean before edits. The final corrective commit is the commit containing this report; obtain its exact identity with `git log -1 --format=%H -- docs/production/final_corrective_verification.md`. The final handoff also reports that identity. No push or production deployment is part of this batch.

Pinned Frappe authority: `588e443808206a7bfe87429c5a55e16016ec7840` (15.113.4). Pinned ERPNext authority: `26f06878346fb6861229ccb1fe3a53dc1bf5bad3` (15.121.3). Core source hashes before and after migration/build match. Both nested framework repositories already had a `package.json` modification for a Yarn package-manager pin; those existing edits were preserved and remain outside this commit.

Canonical `rhp.local` lists only frappe 15.113.4, erpnext 15.121.3, ledgix_saas 15.0.1 and fbr_v1 15.0.1. No site was created, reinstalled, reset or reseeded. `fbr-v1-install-proof.local` could not be inventoried because its local database authentication failed; it was not reset. No app was uninstalled. Historical controllers remain for unidentified existing sites. Any site found to retain installed `fbr_v12` requires a separately controlled inventory, preservation and uninstall operation.

## Corrective issue matrix

| Group | Result | Implementation | Proof |
| --- | --- | --- | --- |
| A Release semantics | PASS | Schema 2 separates Sandbox transport acceptance, configuration, explicit external approval and Production release. Strict release independently requires both cutovers, arm, transport, manual UAT and existing release/backup evidence. Deprecated input alias does not recreate certification output. | Release acceptance behavioral tests cover every missing gate, non-FBR clients and Sandbox-only/configuration-only states. Site readiness remains false. |
| B Generic HTTP | PASS | Generic fiscal GET/POST helpers reject before credentials, DB or network. Only current V1 protocol transport owns HTTP. | Direct-call no-I/O tests and AST gate. |
| C Executable DI app | PASS | `fbr_v12` is a tombstone: guarded installation, empty invoice/scheduler hooks, no runtime assets/schema or dependencies, rejecting functions/controllers. Two executable helper classes are removed. | All 230 former top-level functions and historical DocType controller identities retain rejecting shells; direct tests exercise retained functions. CI excludes DI runtime validation and enforces tombstone contracts. |
| D Fresh V1 schema | PASS | Four retired DI DocType JSON definitions are removed; read-only controllers retain existing metadata. Correction Request stays active. | Pinned Frappe orphan-removal contract test, fresh source tests and actual post-migrate controller resolution; four historical DocTypes retained with zero rows. |
| E Profile upgrade | PASS | Pre-model patch captures exact old values, child rows and encrypted credential storage without decryption into one canonical hashed immutable container per profile. V1 credentials remain separate; obsolete fields cease to be current schema. Payload is excluded from document API serialization. | Hash stability/idempotence/fresh no-op/permissions tests; one actual evidence record with verified hash; Administrator document API payload hidden; all obsolete fields absent from current metadata. |
| F Historical payload | PASS | Old seller/buyer and payload builders fail closed; no live master reconstruction. | Direct imports with master/credential lookups forbidden. |
| G Strict history | PASS | Existing persisted historical snapshot reader remains unchanged; manifest, hashes, counts and row identity still govern evidence. | Existing strict snapshot regression tests plus verified/missing/incomplete identity tests. |
| H Historical printing | PASS | Old Sale formats are explicitly non-fiscal archival views. Historical native fiscal identity requires strict persisted complete evidence. Bare old fiscal numbers cannot generate QR. Current V1 prints retain their own snapshot/result gates. | Archival source checks, live-fallback gate, strict historical tests and current V1 print-state/offline tests. |
| I Backfills | PASS | Seller/item historical identity backfills are no-ops. Existing item patch retains only safe print reload. Current ERPNext/frozen sites skip obsolete ledger bootstrap/normalization. | No DB mutation direct tests; source and post-migrate fingerprints. |
| J Print sync | PASS | New last patch reloads only the two archival print definitions. | Registration/source tests and actual DB HTML checks after migration. |
| K Posting arm | PASS | Only System Manager may transition arm 0 to 1; existing profile writers can disarm. Existing On Submit, fee and print rules remain. External approval verification separately requires System Manager, readable File and server stamps. | Role/disarm/configuration and approval tests; actual arm remains 0. |
| L Sellable items | PASS | Shared scope rejects disabled, non-sales and variant-template Items for new native Retail/B2B sales, including legacy-ID resolution. Concrete variants remain allowed. Returns remain source-bound and can reference a now-disabled original Item. Direct commerce compatibility delegates to native services. | Actual Retail/B2B builder rejection tests, helper/variant tests, source-bound return quantity/foreign-row tests and direct delegation tests. |
| M Tax coverage | PASS | Actual configured contextual/date Tax Rules and net-rate/category-dependent paths prevent complete readiness. Default/static coverage and complete transaction coverage are separate outputs. ERPNext still calculates tax. | Contextual/net-rate/category/default-path tests plus existing inheritance, dates, zero, N/A, POS and Third Schedule regression. |

## Preserved contracts

| Requirement | Result and evidence |
| --- | --- |
| Third Schedule authority | PASS: native tax authority and notified-retail-price capture are unchanged; current V1 tax/payload/service-fee tests pass. |
| V1 transport safety | PASS: documented endpoints, TLS, Cloud Bearer ownership, Local IMS behavior, Code 100 plus fiscal number, durable intent and ambiguous reconciliation remain; protocol/transport runtime tests pass. |
| Native payment authority | PASS: native cash/non-cash/B2B payment evidence remains; current readiness, payload and bridge regressions pass. |
| Immutable V1 snapshots | PASS: current persistence and serializer integrity code is unchanged; missing/tampered/line-manifest/hash regressions pass. |
| Offline and closing | PASS: durable offline issue evidence, fixed restoration deadline, no invented batch endpoint, immutable internal closing and unresolved external status remain; offline/compliance tests pass. |
| Corrections | PASS: current Correction Request retains controlled writes, external File evidence, 72-hour/Commissioner logic and accounting separation; site app tests pass. |
| Current V1 prints | PASS: On Submit/result blocking, strict immutable evidence, authoritative fiscal number/QR and durable Offline Pending printing remain; print-state tests pass. |
| Signatures | PASS: no invented algorithm or mandatory undocumented IMS signature was added; current documentation labels unsupported signatures unresolved. |
| Phase 12 history | PASS: legacy fingerprints and the existing Phase 12 status are unchanged. This site was `Not Frozen` before work and remains `Not Frozen`; this batch does not certify a frozen local dataset or change that state. Existing freeze guards remain. |
| Migration safety | PASS: destructive authorizations absent, cutovers off, arm 0, no pending destructive targets; no historical table/record deletion or automatic retransmission. |
| Static and CI rules | PASS: architecture gate runs from current CI and repository/release static validation; current app validation requires V1 fields/native modules. |
| External protocol authority | PASS: no FBR endpoint, field, QR algorithm, signature, closing/outage/alert/correction API or legal classification was guessed. |

## Validation results

Final green runs are below. Test groups overlap; counts are not unique-test totals. Diagnostic runs exposed stale tests, a fixture translation dependency and an Administrator serialization leak; those were corrected before final green runs. An early pair of concurrent site test invocations hit a scheduler-row deadlock; all final site checks ran sequentially and passed.

Set the following for pure setup tests from repository root:

```bash
export PYTHONPATH="$PWD/frappe-bench/apps:$PWD/frappe-bench/apps/fbr_v1:$PWD/frappe-bench/apps/frappe:$PWD/frappe-bench/apps/erpnext"
```

| Command | Final result |
| --- | --- |
| `frappe-bench/env/bin/python -m unittest discover -s frappe-bench/apps/fbr_v1/fbr_v1/protocol/tests -p 'test*.py'` | 6 passed, 0 failed |
| `frappe-bench/env/bin/python -m unittest discover -s frappe-bench/apps/fbr_v1/fbr_v1/setup -p 'test*.py'` | 151 passed, 0 failed |
| `frappe-bench/env/bin/python -m unittest discover -s frappe-bench/apps/ledgix_saas/setup -p 'test*.py'` | 388 passed, 0 failed |
| `bash scripts/release/run_release_acceptance_static_gate.sh` | 158 passed, 0 failed; architecture gate PASS |
| `bench --site rhp.local run-tests --app fbr_v1` | 165 passed, 0 failed |
| `bench --site rhp.local run-tests --module ledgix_saas.setup.test_release_acceptance_contract` | 11 passed, 0 failed |
| `PYTHONPATH="/tmp/ledgix-local-guard${PYTHONPATH:+:$PYTHONPATH}" frappe-bench/env/bin/python /tmp/ledgix_site_regression.py` | 388 passed, 0 failed, initialized against rhp.local; setup-only suite, HTTP/external sockets blocked, rollback after run |
| `bash scripts/validation/validate_repo.sh` | PASS: owned Python AST, JSON, TOML, shell and packaging/dependency checks |
| `bash scripts/validation/check_secrets.sh` | PASS: no secrets found |
| `frappe-bench/env/bin/python -m compileall -q frappe-bench/apps/fbr_v1/fbr_v1 frappe-bench/apps/ledgix_saas frappe-bench/apps/fbr_v12/fbr_v12` | PASS |
| `git diff --check` | PASS |
| `python3 scripts/validation/check_fiscal_architecture.py` | PASS: four zero proofs below |

The temporary site runner initializes the actual local site and discovers only Ledgix setup tests using unittest, intercepts HTTP and external sockets, and rolls back. The site-wide Ledgix business/DocType fixture suite was intentionally not used to create accounting fixtures in the existing operator dataset. The current V1 site suite and relevant release suite were executed through Bench. No external Sandbox/Production or physical device/manual UAT was performed.

## Static zero proofs

The AST gate scans owned current source and the tombstone, excluding tests and archived material. It also verifies controller/function shells, JSON absence, current schema, deployment scripts, release outputs, archival prints and historical backfills.

| Invariant | Result |
| --- | --- |
| Executable DI endpoints | 0 |
| Alternate HTTP transport outside current V1 protocol | 0 |
| Historical live master fallback in fiscal builders, rendering and backfills | 0 |
| Sandbox acceptance equated to external Production approval | 0 |

The deprecated `sandbox_certification_complete` projection remains only as a labeled compatibility alias for Sandbox acceptance. Release evaluation does not consume it or produce an external-certification field. Historical documentation and test literals may mention retired endpoints without executing them.

## Guarded migration and builds

Both guarded `rhp.local` migrations completed successfully; the second verifies repeatability after final schema edits. New patches captured legacy profile evidence before model sync and synchronized archival prints after sync. Old destructive patch entries were already recorded; no destructive target was present, and neither authorization was enabled.

From `frappe-bench`:

```bash
PYTHONPATH="/tmp/ledgix-local-guard${PYTHONPATH:+:$PYTHONPATH}" bench --site rhp.local migrate
COREPACK_ENABLE_AUTO_PIN=0 PYTHONPATH="/tmp/ledgix-local-guard${PYTHONPATH:+:$PYTHONPATH}" bench build --app ledgix_saas
COREPACK_ENABLE_AUTO_PIN=0 PYTHONPATH="/tmp/ledgix-local-guard${PYTHONPATH:+:$PYTHONPATH}" bench build --app fbr_v1
```

The temporary `sitecustomize.py` allows local DB/Redis sockets and rejects external sockets/DNS plus all Python requests HTTP, recording only a generic blocked marker. No blocked-attempt marker was produced. Runtime tests also reject real network calls. No FBR HTTP request occurred; Production was untouched. `fbr_v12` was neither installed nor built.

Post-migration inspection confirms current V1 fields/DocTypes, one immutable legacy evidence record with valid SHA-256, removal of obsolete fields from current profile metadata, retained historical controllers/metadata, current native print definitions and safely updated archival prints. Submission-log digest and profile arm counts match the original snapshot. General and Production cutovers are false; destructive authorizations remain absent. Current app `validation.run_all()` returns `ok=true`. Sandbox acceptance, external Production approval and Production readiness all remain false.

## Business and accounting fingerprint

Each value below is identical before the first migration and after the repeated migration, builds and relevant site tests. Empty SQL aggregates are NULL, not fabricated zero values.

| Authority | Before rows / submitted | After rows / submitted | Before monetary aggregate | After monetary aggregate |
| --- | --- | --- | --- | --- |
| GL Entry | 0 / NULL | 0 / NULL | debit NULL; credit NULL | debit NULL; credit NULL |
| Sales Invoice | 0 / NULL | 0 / NULL | grand total NULL | grand total NULL |
| POS Invoice | 3 / 3 | 3 / 3 | grand total 3.0 | grand total 3.0 |
| Payment Entry | 0 / NULL | 0 / NULL | paid NULL; received NULL | paid NULL; received NULL |
| Stock Ledger Entry | 2 / 2 | 2 / 2 | stock value difference 2000.0 | stock value difference 2000.0 |

Legacy business counts and retirement snapshot match exactly. Each of Business Nature, Reference Data, Sandbox Certification and Sandbox Scenario retains its existing metadata and zero historical rows. Fiscal submission-log state/hash remains unchanged. Integration Profile count remains 1, armed profile count remains 0. Phase 12 remains `Not Frozen`.

No submitted monetary value was changed. No historical records/tables were deleted. Old encrypted credential storage was preserved without decryption, logging or conversion into V1 credentials; no plaintext token/password/secret was printed or committed. The neutral payload is withheld from standard document serialization, including Administrator API responses; ordinary audit roles can read only metadata/hash.

## Remaining external requirements

No corrective software defect from groups A through M remains open. Real client onboarding, credentials, Sandbox acceptance, explicit external Production approval, physical/manual UAT and approved release/backup evidence remain external operational prerequisites. Nothing in these local tests authorizes Production.

The current unresolved contract register remains **EXTERNAL / UNRESOLVED / INTENTIONALLY FAIL-CLOSED** for:

- Item-level Debit behavior.
- Complete error-code catalogue and server duplicate-USIN behavior.
- Current client POSID/token acquisition workflow.
- Separate offline batch-upload and external daily/weekly/monthly closing endpoint/schema.
- Undocumented digital-signature algorithm.
- External outage-reporting and alert-message APIs.
- V1 wire fields for Extra Tax, FED Payable and Sales Tax Withheld at Source.
- Foreign-currency and inclusive-tax discount wire semantics.

The inaccessible historical local site's installed-app inventory is unverified. No destructive action was taken to resolve access. Retained tombstone controllers preserve compatibility while that inventory requires a separately controlled operation.

## Exact file manifest

Paths are repository-relative. `A` means added, `M` modified, `D` deleted and `T` replaced with a non-executable rejecting tombstone. Every changed tracked or newly added file is listed once under its primary category. Profile schema is listed under permissions because it also owns approval fields; the migration/evidence sections explain its cross-cutting role.

### V1 current runtime

- `M frappe-bench/apps/fbr_v1/fbr_v1/api/printing.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/install.py`
- `M frappe-bench/apps/ledgix_saas/setup/fbr_sandbox_operator.py`
- `M frappe-bench/apps/ledgix_saas/validation.py`

### Release semantics

- `M frappe-bench/apps/fbr_v1/fbr_v1/api/client_readiness.py`
- `M frappe-bench/apps/ledgix_saas/api/release_acceptance.py`
- `M scripts/release/run_ledgix_production_release_gate.sh`
- `M scripts/release/run_release_acceptance_readiness_gate.sh`
- `M scripts/release/run_release_acceptance_static_gate.sh`

### Retired DI runtime

- `T frappe-bench/apps/fbr_v12/fbr_v12/api/client_readiness.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_activation.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_native.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_offline.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_reference_v2.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_transport.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_v2_center.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/fbr_v2_transport.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/api/printing.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_business_nature/ledgix_fbr_business_nature.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_business_nature/ledgix_fbr_business_nature.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_correction_request/ledgix_fbr_correction_request.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_correction_request/ledgix_fbr_correction_request.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_correction_request/test_ledgix_fbr_correction_request.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_item_mapping/ledgix_fbr_item_mapping.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_item_mapping/ledgix_fbr_item_mapping.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_reference_data/ledgix_fbr_reference_data.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_reference_data/ledgix_fbr_reference_data.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_sandbox_certification/ledgix_fbr_sandbox_certification.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_sandbox_certification/ledgix_fbr_sandbox_certification.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_sandbox_scenario/ledgix_fbr_sandbox_scenario.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_sandbox_scenario/ledgix_fbr_sandbox_scenario.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_submission_log/ledgix_fbr_submission_log.js`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_submission_log/ledgix_fbr_submission_log.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_submission_log/ledgix_fbr_submission_log.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_submission_log/test_ledgix_fbr_submission_log.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_tax_component_mapping/ledgix_fbr_tax_component_mapping.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/doctype/ledgix_fbr_tax_component_mapping/ledgix_fbr_tax_component_mapping.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/page/fbr_v12_center/fbr_v12_center.css`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/page/fbr_v12_center/fbr_v12_center.js`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/page/fbr_v12_center/fbr_v12_center.json`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/print_format/ledgix_erpnext_pos_receipt/ledgix_erpnext_pos_receipt.json`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/print_format/ledgix_erpnext_tax_invoice/ledgix_erpnext_tax_invoice.json`
- `D frappe-bench/apps/fbr_v12/fbr_v12/fbr_v12/workspace/fbr_v1_2/fbr_v1_2.json`
- `T frappe-bench/apps/fbr_v12/fbr_v12/hooks.py`
- `A frappe-bench/apps/fbr_v12/fbr_v12/retired.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/erpnext_fbr_identity.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/erpnext_fbr_snapshot.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/erpnext_taxable_base.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/fbr_submission_support.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/fbr_v2_payload_builder.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/fbr_v2_readiness.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/services/fbr_v2_snapshot_persistence.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/setup/erpnext_fbr_schema.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/setup/erpnext_phase9_extensions.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/setup/fbr_v2_component_mappings.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/setup/install.py`
- `T frappe-bench/apps/fbr_v12/fbr_v12/setup/print_formats.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/setup/test_fbr_v12_offline_runtime.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/setup/test_fbr_v12_payload_runtime.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/setup/test_fbr_v12_snapshot_runtime.py`
- `D frappe-bench/apps/fbr_v12/fbr_v12/setup/test_fbr_v12_transport_runtime.py`
- `M frappe-bench/apps/fbr_v12/pyproject.toml`
- `M frappe-bench/apps/ledgix_saas/api/fbr_reference_v2.py`
- `M frappe-bench/apps/ledgix_saas/api/fbr_transport.py`
- `M frappe-bench/apps/ledgix_saas/api/fbr_v2_transport.py`

### Historical evidence

- `D frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_business_nature/ledgix_fbr_business_nature.json`
- `M frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_business_nature/ledgix_fbr_business_nature.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_legacy_evidence/__init__.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_legacy_evidence/ledgix_fbr_legacy_evidence.json`
- `A frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_legacy_evidence/ledgix_fbr_legacy_evidence.py`
- `D frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_reference_data/ledgix_fbr_reference_data.json`
- `M frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_reference_data/ledgix_fbr_reference_data.py`
- `D frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_sandbox_certification/ledgix_fbr_sandbox_certification.json`
- `M frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_sandbox_certification/ledgix_fbr_sandbox_certification.py`
- `D frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_sandbox_scenario/ledgix_fbr_sandbox_scenario.json`
- `M frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_sandbox_scenario/ledgix_fbr_sandbox_scenario.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/services/historical_document.py`
- `M frappe-bench/apps/ledgix_saas/api/fbr_payload.py`
- `M frappe-bench/apps/ledgix_saas/api/printing.py`
- `M frappe-bench/apps/ledgix_saas/ledgix/print_format/ledgix_b2b_invoice/ledgix_b2b_invoice.json`
- `M frappe-bench/apps/ledgix_saas/ledgix/print_format/ledgix_thermal_receipt/ledgix_thermal_receipt.json`

### Migration

- `M frappe-bench/apps/fbr_v1/fbr_v1/patches.txt`
- `A frappe-bench/apps/fbr_v1/fbr_v1/patches/__init__.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/patches/preserve_legacy_profile_evidence.py`
- `M frappe-bench/apps/ledgix_saas/patches.txt`
- `M frappe-bench/apps/ledgix_saas/patches/v1_0/backfill_sale_item_identity_and_sync_receipts.py`
- `M frappe-bench/apps/ledgix_saas/patches/v1_0/backfill_sale_seller_snapshots.py`
- `M frappe-bench/apps/ledgix_saas/patches/v1_0/bootstrap_v2_commerce_contracts.py`
- `M frappe-bench/apps/ledgix_saas/patches/v1_0/normalize_v2_payment_methods.py`
- `A frappe-bench/apps/ledgix_saas/patches/v1_0/sync_archival_transaction_prints.py`

### Permissions

- `M frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.json`
- `M frappe-bench/apps/fbr_v1/fbr_v1/fbr_v1/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/services/production_approval.py`

### Item and tax readiness

- `M frappe-bench/apps/fbr_v1/fbr_v1/services/erpnext_tax_readiness.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/services/native_tax_paths.py`
- `M frappe-bench/apps/ledgix_saas/api/v2_pos.py`
- `M frappe-bench/apps/ledgix_saas/api/v2_returns.py`
- `M frappe-bench/apps/ledgix_saas/services/erpnext_item_scope.py`
- `M frappe-bench/apps/ledgix_saas/services/erpnext_selling.py`

### Tests

- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/test_fbr_v1_readiness_runtime.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/test_fbr_v1_tax_readiness_runtime.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/setup/test_runtime_retirement_contract.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/test_sandbox_acceptance_runtime.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/v1_test_support.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_backup_restore_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_demo_data_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_erpnext_extensions.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_erpnext_phase10_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_erpnext_phase11_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_erpnext_phase12_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_erpnext_phase7_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_erpnext_phase9_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_legacy_reference_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_native_legacy_dependency_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_offline_lifecycle_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_phase8_print_correction_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_phase9_legacy_tax_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_redesign_phase1_legacy_fbr_isolation_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_redesign_phase2_schema_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_legacy_desk_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_legacy_test_cleanup_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_legacy_transport_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_old_settings_runtime_cleanup_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_old_settings_source_deregistration_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_print_legacy_seller_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_fbr_v2_retired_settings_db_cleanup_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_phase12_legacy_business_test_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_provisioning_multisite_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_release_acceptance_contract.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_release_hardening_contract.py`

### CI and docs

- `M .github/workflows/fbr-v1-static.yml`
- `D .github/workflows/fbr-v12-static.yml`
- `M README.md`
- `M docs/fbr/fbr_v1/FBR_V1_PRODUCTION_CHECKLIST.md`
- `M docs/fbr/fbr_v1/FBR_V1_RUNTIME_ARCHITECTURE.md`
- `M docs/fbr/fbr_v1/FBR_V1_SETUP_AND_ACTIVATION.md`
- `M docs/fbr/fbr_v1/README.md`
- `M docs/production/fbr_sandbox_production_activation.md`
- `A docs/production/final_corrective_verification.md`
- `M docs/production/final_release_gate.md`
- `M frappe-bench/apps/fbr_v1/README.md`
- `M frappe-bench/apps/fbr_v12/README.md`
- `M scripts/README.md`
- `A scripts/validation/check_fiscal_architecture.py`
- `M scripts/validation/validate_doctype_names.sh`
- `M scripts/validation/validate_repo.sh`

Manifest contains 148 paths. Temporary validation scripts/logs are outside the repository and are not committed.
