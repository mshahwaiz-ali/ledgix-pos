# Ledgix post audit corrective verification

The post-audit batch closes groups A through K: server role and discount authority, native pricing/UOM, Retail stock location, tender/change validation, B2B payment scope, read-only runtime schema checks, direct Python compatibility, historical Desk retirement and regression gates. ERPNext remains the financial, stock, pricing and tax authority. Local migration and current-app regressions pass; external Sandbox acceptance and Production approval remain pending.

## Commit authority

Starting branch: `main`. Starting HEAD and fetched `origin/main`: `4e35f8b9cc8d4dcca5a70492bf4e039d47a1aa02`. Its verified parent: `df22d531133894e70f9901779978770042cc93a2`. Owning repository was clean before work. One local post-audit commit contains this report and the bounded corrections; no push is authorized or performed.

Final SHA is the exact commit containing this updated report, resolved after commit by `git log -1 --format=%H -- docs/production/final_corrective_verification.md` and reported in the final handoff. This avoids embedding an uncommitted or self-referential future SHA in the committed report. The handoff also verifies the parent, clean worktree and `git diff --check HEAD^ HEAD`.

Frappe 15.113.4 is pinned at `588e443808206a7bfe87429c5a55e16016ec7840`; ERPNext 15.121.3 at `26f06878346fb6861229ccb1fe3a53dc1bf5bad3`. All captured core source hashes match before/after. Their existing unrelated `package.json` edits were preserved, not included in this commit. No framework core was modified by this work.

## Issue closure

Paths below use `LED = frappe-bench/apps/ledgix_saas` and `V1 = frappe-bench/apps/fbr_v1/fbr_v1`. Full repository-relative paths are listed in the manifest.

| Group | Result | Exact primary files | Before | After | Adversarial proof |
| --- | --- | --- | --- | --- | --- |
| A B2B direct RPC | PASS | LED/api/security.py, LED/api/pos_compat.py, LED/services/erpnext_pos.py, LED/api/selling.py | Read/context/hold routes trusted Cashier boot/UI state; owned B2B holds could bypass channel authority. | Shared existing-role helper authenticates the channel before service work. Cashier cannot query/list/resume/cancel B2B holds. Manager cross-user access remains. Native doctype determines hold channel. | Every direct channel RPC rejects Cashier B2B before context lookup/write; actual site user-role test; Manager/Admin/System Manager positive flows; own Retail and cross-user Manager hold checks. |
| B Retail discount | PASS | LED/services/erpnext_selling.py, LED/services/erpnext_pos.py, LED/api/pos_compat.py | Cashier could send positive checkout discounts; resumed hold discount was unchecked. | Shared server validation requires manager for effective positive discount and rejects malformed/non-finite/negative inputs. Rechecked before builders, locks and application; resume rejects before status write. | Amount/Percent preview/complete/hold matrix, zero Retail flows, resumed discount, Manager positive discount and authorized rate override. |
| C Native pricing | PASS | LED/services/erpnext_selling.py | Native unresolved price could fall back to a manually selected Item Price. | Manual query removed. Only positive native rate or the native response's price_list_rate when no effective rule rate is supplied is accepted. Explicit zero remains failure. No expired/future/inapplicable row is resurrected. | Native Pricing Rule rate wins; ordinary native price-list response passes; absent/zero/negative/non-finite price throws with secondary Item Price queries forbidden. AST gate forbids fallback. |
| D UOM | PASS | LED/services/erpnext_selling.py | Raw client UOM replaced the UOM used for native pricing. | Native ERPNext UOM is retained; blank/matching client UOM is accepted, mismatched or unresolved UOM rejected. No alternate-UOM feature or conversion engine added. | Normal/matching/whitespace/alternate UOM matrix; override role recheck. Current JS cart payload intentionally contains no UOM feature and was unchanged. |
| E Retail warehouse | PASS | LED/services/erpnext_pos.py | Raw item warehouse could override POS Profile stock location. | Missing/matching values use canonical profile warehouse; different same-company or cross-company input fails before native pricing/document creation. Held requests retain validated context rather than stripping crafted warehouse/UOM first. B2B stock semantics stay native. | Both injected warehouse cases reject before pricing/document; absent/matching cases use profile warehouse. |
| F Tender/change | PASS | LED/services/erpnext_pos.py, LED/services/erpnext_selling.py | Any change-capable Cash row could legitimize excess supplied by Card. | Tenders consume remaining due in sequence. Only actual change-capable Cash excess creates change; no later positive tender is accepted. Change account comes from the tender producing the excess. Positive finite amounts, references and partial-payment policy are checked. | Required exact-pay/split/Cash-change pass matrix; Card excess, fake Cash authorization, non-change Cash, later tender and bad-number failures; specific second Cash account verified at native submit boundary. |
| G B2B payment modes | PASS | LED/api/selling.py, LED/services/erpnext_pos.py | Standalone public payment/refund could use any existing Mode of Payment with Company account. | Shared canonical POS Profile policy is used by checkout, standalone payment and refund. Payment uses selected Company; allocation service retains actual customer/invoice Company checks. Refund profile must match actual native note Company. Required references are enforced. ERPNext's own Payment Entry UI is unchanged. | Configured Cash/Card pass; existing unoffered Bank Transfer rejected before payment/refund service; foreign profile Company rejected; checkout mapping regressions pass. |
| H Runtime schema | PASS | LED/services/erpnext_selling.py, LED/services/erpnext_pos.py, LED/setup/erpnext_phase6_extensions.py, LED/setup/erpnext_phase8_extensions.py | Preview/checkout/payment could call extension synchronizers and update schema. | Request services call read-only schema assertions. Missing fields tell the operator to run bench migrate. Install/migrate retains schema synchronization. | All API/service AST calls scanned for sync_all/sync_custom_fields/create_custom_fields/updatedb; complete/missing metadata behavior, repeatable migration synchronization and real migrated field checks. |
| I Python convergence | PASS | LED/api/v2_pos.py, LED/api/v2_holds.py, LED/api/v2_returns.py, LED/api/shifts.py, LED/api/selling.py | Hook override used native services, while direct original Python imports could execute shadow masters/ledgers. | Every POS function overridden to pos_compat delegates directly with its original signature. api.api imports those same shift delegates. Native-return fallback rejects missing native references instead of recursing through old routes. | Iterates all current overridden functions and invokes originals under a mocked canonical target; AST gate verifies convergence. Retail shift authority remains unchanged. |
| J Desk retirement | PASS | V1/setup/legacy_v12_retirement.py, V1/setup/install.py, V1/setup/print_formats.py | Removed JSON did not guarantee stale V1.2 Page/Workspace disappeared from upgraded databases. | Current V1 after_migrate synchronizes shared native prints, then retires only exact owned Page fbr-v12-center and Workspace FBR V1.2. The linking Workspace is deleted before its Page, with normal link checks retained. Unexpected ownership blocks before deletion. Shared prints are adopted/current/enabled and never deleted. Fiscal metadata/data and tombstone hooks remain intact. | Exact targets retire once with linked-Workspace-before-Page enforcement; custom collision blocks all deletions; current Page/Workspace/fiscal record survive; shared print module/doctype/HTML enabled checks; actual site repeat cleanup is no-op. |
| K Guards and CI | PASS | scripts/validation/check_fiscal_architecture.py, scripts/release/run_release_acceptance_static_gate.sh, .github/workflows/fbr-v1-static.yml | Existing gate covered V1 fiscal retirement but lacked these POS boundaries and push trigger. | Adds native pricing, runtime schema, channel, original-route and current-owned cleanup checks. Release gate runs new adversarial tests; CI source gate also triggers on main pushes without secrets/FBR calls. | Architecture gate and expanded 195-test release/static gate pass. |

## Validation

Commands were run locally against the pinned checkout. Test groups overlap; counts are not unique totals.

For pure tests at repository root, `PYTHONPATH` includes `frappe-bench/apps`, `frappe-bench/apps/fbr_v1`, `frappe-bench/apps/frappe` and `frappe-bench/apps/erpnext`; Python is `frappe-bench/env/bin/python`.

| Validation | Exact command or scope | Final result |
| --- | --- | --- |
| Targeted Ledgix | `python -m unittest ledgix_saas.setup.test_pos_authority_hardening_contract ledgix_saas.setup.test_erpnext_phase6_extensions ledgix_saas.setup.test_erpnext_phase8_contract ledgix_saas.setup.test_b2b_checkout_payment_contract` | 60 passed, 0 failed |
| V1 runtime/contracts | `python -m unittest discover -s frappe-bench/apps/fbr_v1/fbr_v1/setup -p 'test*.py'` | 156 passed, 0 failed; includes all requested transport, snapshot, payload, print, readiness, tax, Sandbox, fee and retirement modules plus offline/closing regressions |
| Ledgix setup regression | `python -m unittest discover -s frappe-bench/apps/ledgix_saas/setup -p 'test*.py'` | 416 passed, 0 failed |
| Release/static gate | `bash scripts/release/run_release_acceptance_static_gate.sh` | 195 passed, 0 failed |
| Full Ledgix site app | `bench --site rhp.local run-tests --app ledgix_saas --skip-test-records` | 469 run, 455 passed, 14 existing intentional historical skips, 0 failed |
| Full V1 site app | `bench --site rhp.local run-tests --app fbr_v1` | 170 passed, 0 failed |
| Python compile | `frappe-bench/env/bin/python -m compileall -q frappe-bench/apps/ledgix_saas frappe-bench/apps/fbr_v1` | PASS |
| JSON/TOML/shell/packaging | `bash scripts/validation/validate_repo.sh` | PASS |
| Architecture | `python3 scripts/validation/check_fiscal_architecture.py` | PASS |
| Secret scan | `bash scripts/validation/check_secrets.sh` | PASS |
| Diff consistency | `git diff --check`, final `git diff --check HEAD^ HEAD` | PASS |
| JavaScript | No JS file changed; current POS cart source inspected for UOM/warehouse/override contract | No changed-JS syntax check required |

Full-site runs were sequential, with test-record pre-seeding disabled for Ledgix. Existing skipped tests are pre-cutover legacy business fixtures, not newly skipped coverage: `test_ledgix_pos_shift`, `test_v2_print_formats`, `test_ledgix_sale`, `test_v2_serial_pos`, `test_v2_serial_return`, `test_ledgix_purchase`, `test_ledgix_sales_return`, `test_ledgix_item_price`, `test_ledgix_pos_hold`, `test_ledgix_payment`, `test_v2_return_credit_balance` and `test_ledgix_stock_movement`, plus the two retired legacy Customer/role fixture methods in `test_ledgix_user_profile`. Their existing skip reasons state that the frozen pre-cutover engine is retired and native ERPNext gates are authoritative.

The first broad Ledgix run found five stale assertions. No runtime permission/reporting/UI behavior was changed to satisfy them. Existing tests now assert the real pre-freeze versus Frozen legacy metadata policy plus actual current B2B role checks, the current native workspace links, retired Tax Center routing/title, ERPNext-native inventory references and Batch terminology. No test was deleted or newly skipped. Two V1 fixtures gained explicit authenticated role/read-only schema mocks because native service authorization is now enforced before their item-scope/tax assertions.

All final focused and full site runs follow migration. Schema completeness is also inspected read-only from the actual rhp.local metadata; mocked runtime tests alone are not treated as installation proof.

## Migration and historical metadata

`PYTHONPATH="/tmp/ledgix-local-guard${PYTHONPATH:+:$PYTHONPATH}" bench --site rhp.local migrate` completed successfully three times, including after the final linked-workspace deletion-order correction. Source gates were green before migration. The second run proves repeated schema synchronization and retirement are safe. No app was installed, reinstalled or uninstalled. rhp.local still lists frappe, erpnext, ledgix_saas and fbr_v1 only.

The temporary local guard rejects external sockets/DNS and every requests HTTP call, allows local MariaDB/Redis, and logs only a generic blocked marker. No marker was generated during guarded verification. Runtime tests also prohibit actual HTTP. Real FBR/PRAL calls = 0. Both cutovers remained 0, and the one profile remained disarmed. No credentials were entered, modified, revealed or rotated; no production host, DB, config or service was touched.

The stale exact V1.2 Page/Workspace were already absent on rhp.local before this batch; historical-upgrade behavior is proven with mocked metadata, without installing fbr_v12. After migration current fbr-v1-center and FBR V1 remain, current shared Print Formats are enabled with FBR V1 module, correct native doctypes and collision-safe current Jinja. Current V1 Third Schedule taxable-base hook, native tax engine, snapshots, durable intent, reconciliation, offline/closing/correction and fiscal print checks remain unchanged. fbr_v12 retains rejecting installation/controllers and empty runtime hooks.

All captured historical fiscal DocType row counts and legacy retirement snapshots remain unchanged. The site's pre-existing Phase 12 `Not Frozen` state is preserved; this work does not certify/fabricate a frozen dataset or alter pre-freeze legacy metadata permissions.

## Financial and FBR fingerprint

Read-only snapshots include counts, submitted counts and monetary aggregates for every required authority. NULL empty aggregates are retained as NULL.

| Authority | Before rows / submitted | After rows / submitted | Before aggregate | After aggregate |
| --- | --- | --- | --- | --- |
| GL Entry | 0 / NULL | 0 / NULL | debit NULL, credit NULL | debit NULL, credit NULL |
| Sales Invoice | 0 / NULL | 0 / NULL | total NULL | total NULL |
| POS Invoice | 3 / 3 | 3 / 3 | total 3.0 | total 3.0 |
| Payment Entry | 0 / NULL | 0 / NULL | paid NULL, received NULL | paid NULL, received NULL |
| Journal Entry | 0 / NULL | 0 / NULL | debit NULL, credit NULL | debit NULL, credit NULL |
| Stock Ledger Entry | 2 / 2 | 2 / 2 | stock value difference 2000.0 | stock value difference 2000.0 |

| Fiscal control | Before | After |
| --- | --- | --- |
| fbr_v1_network_cutover_active | 0 | 0 |
| fbr_v1_production_cutover_active | 0 | 0 |
| production_post_armed | 0 on the single profile | 0 on the same profile |
| Fiscal submission-log state SHA-256 | 1260a2036b8cd2a7c99c57225b8022984643ae7e6ddc64bc56f47be7f4ecdc2c | identical |
| Real FBR calls | 0 | 0 |

No persistent accounting/test invoice/payment/stock entry was created. No new fiscal log, ambiguous send or reconciliation state was caused by this work. No production access/deployment/restart/push occurred. Core source hashes and the existing unrelated core package edits match the pre-work capture.

## Remaining requirements

Software blockers for groups A through K: **none**.

External Sandbox acceptance, real client/provider onboarding/POSID/credentials, separate explicit Production/go-live approval, approved release/backup evidence and physical/manual UAT remain pending. Local test success does not establish regulatory certification or authorize Production.

The existing FBR contract register remains **EXTERNAL / UNRESOLVED / INTENTIONALLY FAIL-CLOSED** for Item-level Debit semantics, full error catalogue, duplicate-USIN server behavior, POSID/token acquisition workflow, separate offline upload, external closing, undocumented signature algorithm, outage/alert APIs, undocumented Extra Tax/FED/withheld wire fields and foreign-currency/inclusive-discount semantics. None was guessed or widened in this batch.

The previous historical proof site's database access limitation is unchanged. No reset or automatic uninstall was attempted; historical tombstone compatibility remains for separately controlled inventories.

## Exact changed files

Every path below belongs to this post-audit commit. `A` means added and `M` modified. The earlier 148-file corrective commit remains available through Git history; this existing report was updated rather than creating another report.

- `M .github/workflows/fbr-v1-static.yml`
- `M docs/production/final_corrective_verification.md`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/install.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/setup/legacy_v12_retirement.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/print_formats.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/test_fbr_v1_tax_readiness_runtime.py`
- `A frappe-bench/apps/fbr_v1/fbr_v1/setup/test_legacy_v12_desk_retirement.py`
- `M frappe-bench/apps/fbr_v1/fbr_v1/setup/test_runtime_retirement_contract.py`
- `M frappe-bench/apps/ledgix_saas/api/pos_compat.py`
- `M frappe-bench/apps/ledgix_saas/api/security.py`
- `M frappe-bench/apps/ledgix_saas/api/selling.py`
- `M frappe-bench/apps/ledgix_saas/api/shifts.py`
- `M frappe-bench/apps/ledgix_saas/api/v2_holds.py`
- `M frappe-bench/apps/ledgix_saas/api/v2_pos.py`
- `M frappe-bench/apps/ledgix_saas/api/v2_returns.py`
- `M frappe-bench/apps/ledgix_saas/ledgix/doctype/ledgix_user_profile/test_ledgix_user_profile.py`
- `M frappe-bench/apps/ledgix_saas/ledgix/doctype/ledgix_user_profile/test_v2_ui_architecture.py`
- `M frappe-bench/apps/ledgix_saas/ledgix/doctype/ledgix_user_profile/test_v2_workspace_and_intelligence.py`
- `M frappe-bench/apps/ledgix_saas/services/erpnext_pos.py`
- `M frappe-bench/apps/ledgix_saas/services/erpnext_selling.py`
- `M frappe-bench/apps/ledgix_saas/setup/erpnext_phase6_extensions.py`
- `M frappe-bench/apps/ledgix_saas/setup/erpnext_phase8_extensions.py`
- `M frappe-bench/apps/ledgix_saas/setup/test_b2b_checkout_payment_contract.py`
- `A frappe-bench/apps/ledgix_saas/setup/test_pos_authority_hardening_contract.py`
- `M scripts/release/run_release_acceptance_static_gate.sh`
- `M scripts/validation/check_fiscal_architecture.py`

26 paths in this bounded batch. Validation scripts and snapshots in /tmp are not committed.
