# Ledgix Client Onboarding and Readiness

This runbook defines R5 of the Client Acceptance + Production Provisioning + Release Hardening track.

**ERPNext remains the business authority.** R5 does not create replacement business masters, accounting ledgers, stock ledgers, invoices, payments or client forks. It evaluates whether an already provisioned Ledgix site is operationally ready for client handover and records non-secret evidence.

## Scope

R5 sits after fresh provisioning / multi-site deployment hardening and before the dedicated FBR Sandbox -> Production activation workstream.

It checks:

- Ledgix Business Profile setup has been applied;
- the selected profile still satisfies its ERPNext-native Company / Selling Price List / Warehouse / POS Profile prerequisites;
- the Company has a Chart of Accounts and profile-relevant accounting defaults;
- at least one Mode of Payment has a Company account mapping when selling/payment flows are enabled;
- required Ledgix role definitions exist;
- at least one enabled named user has a Ledgix operational role;
- POS-enabled sites are warned when no named Ledgix Cashier exists;
- FBR Settings exist when the profile enables FBR;
- FBR Production posting is still unarmed before the dedicated activation gate;
- seller identity gaps are surfaced as the next FBR-workstream input;
- release/provisioning and verified-backup evidence are visible to the readiness audit.

## Configuration boundary

R5 is primarily an evaluator and evidence layer.

It does **not**:

- create Company, Item, Customer, Supplier, Warehouse, POS Profile, Account or Mode of Payment records;
- assign business data to legacy Ledgix DocTypes;
- create users automatically;
- change user passwords;
- enable or arm FBR Production;
- store FBR tokens in readiness evidence;
- fork code per client.

Client differences remain Business Profile + ERPNext configuration + permissions. There is no client fork.

The local/integration runtime helper has one explicit configuration mutation option: `--apply-setup`. It is fail-closed and runs only when **the sole blocking check** is `client_setup_applied` and the current profile prerequisites are already green. It reuses the already-resolved Company, Selling Price List, Warehouse and POS Profile and calls the existing Phase 13 `apply_client_setup` service. It does not manufacture missing ERPNext masters or bypass readiness checks.

## Desk workflow

Open:

```text
/app/ledgix-setup
```

The existing configuration readiness remains the authority for applying a Business Profile. R5 adds an **Operational onboarding** section to the same page.

Use **Refresh Onboarding** after changing Company accounting defaults, Mode of Payment mappings, users/roles or FBR seller identity.

The UI uses the non-strict evidence mode because a development/integration site may not have production release/backup records yet.

## Local/integration gate

Read-only evaluation:

```bash
bash scripts/run_r5_client_readiness_gate.sh ledgix-erpnext.local
```

If the output proves that `client_setup_applied` is the **only** blocker and all current profile prerequisites pass, the integration setup marker/configuration can be applied safely and then re-evaluated in one run:

```bash
bash scripts/run_r5_client_readiness_gate.sh ledgix-erpnext.local \
  --apply-setup \
  --require-ready
```

`--apply-setup` refuses to run when any other blocking prerequisite exists.

The runtime gate:

1. runs the R5 static gate;
2. exact-syncs the repository Ledgix app into the local bench;
3. runs dependency preflight;
4. runs ERPNext-native offline smoke checks;
5. evaluates current onboarding readiness;
6. optionally applies only the already-resolved setup configuration when `--apply-setup` is explicitly requested and safe;
7. re-evaluates readiness after an apply;
8. writes a private non-secret readiness snapshot.

It never deletes/resets the site and never creates ERPNext business masters.

The gate always prints:

```text
r5_readiness_evaluation_complete=true
```

when the evaluator/evidence path itself is healthy.

It separately prints either:

```text
r5_client_ready=true
```

or:

```text
r5_client_ready=false
```

so an integration audit can show real remaining client blockers without treating the evaluator as broken.

## Production acceptance mode

For a real client acceptance run, use strict evidence and require a fully green result:

```bash
bash scripts/run_r5_client_readiness_gate.sh client.local \
  --strict-evidence \
  --require-ready
```

The repository runtime helper deliberately exact-syncs only `.local` / `.localhost` integration sites. On production, run the equivalent `bench execute` readiness call against the already approved deployed release instead of using a development exact-sync helper.

**Strict evidence** turns missing release/provisioning evidence and missing verified-backup metadata into blocking acceptance checks.

Do not use the integration `--apply-setup` convenience path as a substitute for client approval of their Business Profile in production; production onboarding should use the normal `/app/ledgix-setup` workflow under an authorized operator.

## Evidence

Snapshots are written under the site's private directory:

```text
private/ledgix-readiness/client-readiness-<UTC timestamp>.json
private/ledgix-readiness/latest.json
```

Files are owner-only (`0600`) and explicitly marked as containing no secrets.

The evidence contains:

- site;
- selected Business Profile;
- resolved Company / Price List / Warehouse / POS Profile;
- country/currency/timezone identity;
- installed-app names;
- readiness checks, blockers and warnings;
- provisioning/release/backup evidence presence;
- release SHA passed by the operator/runtime gate;
- next workstream.

It never includes Administrator passwords, DB passwords, sandbox token or production token values.

## Named users and roles

Client handover requires at least one enabled named user with one of:

- Ledgix Admin;
- Ledgix Manager;
- Ledgix Cashier.

`Administrator` is not counted as the client's operational user. POS-enabled sites additionally warn if no named Ledgix Cashier exists.

Role assignment is still enforced by normal Frappe/ERPNext permissions; Business Profile feature flags never grant authorization.

## Accounting and payment prerequisites

For the selected Company, R5 validates the Chart of Accounts and the standard ERPNext defaults relevant to the selected profile. Selling profiles require normal receivable/income configuration; buying profiles require payable/expense configuration where those standard fields exist.

Selling/payment profiles also require at least one **Mode of Payment** account mapping for the Company. POS-specific customer/warehouse/price-list/payment requirements continue to come from the existing Ledgix setup evaluator and ERPNext POS Profile.

## FBR boundary

R5 confirms the site is safe to enter the next compliance workstream. **FBR Production remains a separate gate.**

For an FBR-enabled profile, R5:

- verifies `Ledgix FBR Settings` exists;
- blocks readiness if Production posting is already armed prematurely;
- reports missing seller identity fields as warnings/input for the next workstream;
- does not read or persist token values into readiness evidence.

After R5 acceptance, continue to the dedicated FBR Sandbox -> Production activation workstream.
