# Ledgix Production Go-Live Checklist

**Status:** CURRENT  
**Use with:** detailed runbooks in `docs/production/`

## 1. Release and infrastructure

- [ ] Approved immutable Ledgix SHA/tag recorded.
- [ ] Pinned Frappe/ERPNext release contract verified.
- [ ] DNS resolves the intended client domain to the correct server.
- [ ] SSH is restricted to trusted access.
- [ ] HTTP/HTTPS firewall/security-group rules are intentional.
- [ ] MariaDB and Redis are not publicly exposed.
- [ ] Nginx + Supervisor are used; `bench start` is not used for production.
- [ ] HTTPS is enabled and redirects/host routing are verified.

## 2. Site provisioning

- [ ] One client = one Frappe site/database.
- [ ] ERPNext is installed before `ledgix_saas`.
- [ ] Strong production credentials are stored outside Git.
- [ ] Client dependency preflight is green.
- [ ] Offline smoke checks are green.
- [ ] Provisioning evidence is retained.
- [ ] No local/demo credentials were copied into production.

## 3. ERPNext business setup

- [ ] Company and Chart of Accounts are correct.
- [ ] Required receivable/payable/income/expense defaults are configured.
- [ ] Selling/Buying Price Lists are correct.
- [ ] Warehouses are correct for enabled workflows.
- [ ] Modes of Payment have correct Company account mappings.
- [ ] Customers/Suppliers/Items are ERPNext-native.
- [ ] POS Profile is complete where POS is enabled.
- [ ] Business Profile has been reviewed/applied through the supported setup workflow.
- [ ] Client onboarding readiness is green.

## 4. Workflow acceptance

Test only the workflows relevant to the selected client profile.

- [ ] Retail POS opening/sale/payment/return/closing works.
- [ ] Split payment works where required.
- [ ] Held carts resume through native draft ERPNext documents.
- [ ] B2B Sales Invoice and partial/full Payment Entry allocation works.
- [ ] B2B Credit Note/refund works where required.
- [ ] Buying/receipt/Purchase Invoice flow works where required.
- [ ] Stock Entry/Reconciliation/Batch/Serial flows work where required.
- [ ] ERPNext outstanding, stock and accounting values are authoritative.
- [ ] Required A4/thermal print formats are installed and manually checked.
- [ ] Scanner/printer/device UAT evidence is recorded where applicable.

## 5. Backup and rollback

- [ ] Fresh `deploy/backup_safe.sh` recovery set created.
- [ ] Backup checksums verified.
- [ ] Database/public/private/config recovery inputs are present.
- [ ] Matching application release identity is recorded.
- [ ] Protected/off-host copy exists where required.
- [ ] Rollback owner and previous known-good release are identified.
- [ ] Restore procedure has been rehearsed for the applicable release family.

## 6. FBR boundary

If FBR is **not** part of this client's go-live:

- [ ] FBR Production remains disabled/unarmed.

If FBR **is** part of go-live:

- [ ] Seller legal identity confirmed.
- [ ] Item/FBR classifications reviewed.
- [ ] Real Sandbox token configured securely.
- [ ] Real Sandbox validation/POST proof persisted for required native invoice types.
- [ ] Return/Credit Note proof captured when required.
- [ ] No invoice remains `Reconciliation Required`.
- [ ] Production token configured securely.
- [ ] Fresh verified backup and exact release SHA recorded.
- [ ] `fbr_production_switch_ready=true` achieved through the supported read-only evaluator.
- [ ] Explicit Production activation/arming approved by authorized operator.

**Do not restore retry/offline schedulers. Ambiguous Production POSTs are reconciliation-required and fail closed.**

## 7. Final release gate

Run:

```bash
bash scripts/run_ledgix_production_release_gate.sh \
  --site client.example.com \
  --url https://client.example.com \
  --release <approved-immutable-release>
```

Add `--require-fbr-production` only when real FBR Production evidence is part of the approved go-live.

Required success marker:

```text
ledgix_production_release_gate_complete=true
```

## 8. After go-live

- [ ] Online smoke remains green.
- [ ] Scheduler/workers/services are healthy.
- [ ] First live business transactions reconcile correctly in ERPNext.
- [ ] First FBR live transaction is explicitly observed when FBR Production is enabled.
- [ ] Backups continue to be produced and verified.
- [ ] Release/provisioning/acceptance evidence is retained per client.
