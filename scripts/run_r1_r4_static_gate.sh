#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

printf '==================================================\n'
printf ' Ledgix R1 + R4 Provisioning / Multi-Site Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

printf '\n===== R3 REGRESSION CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_backup_restore_contract

printf '\n===== R1 + R4 CONTRACT TESTS =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_provisioning_multisite_contract

printf '\n===== SAFE HELPER CLI CONTRACT =====\n'
bash "$REPO_ROOT/deploy/provision_client_site_safe.sh" --help >/dev/null
bash "$REPO_ROOT/deploy/deploy_update_shared_safe.sh" --help >/dev/null
bash "$REPO_ROOT/deploy/deploy_update_safe.sh" --help >/dev/null
printf '[PASS] provisioning and release helpers expose non-mutating help paths\n'

printf '\n===== R1 + R4 STATIC VERDICT =====\n'
printf '[PASS] immutable fresh-client provisioning contract\n'
printf '[PASS] ERPNext-before-Ledgix install ordering contract\n'
printf '[PASS] generated production credential isolation contract\n'
printf '[PASS] single-site updater shared-bench refusal contract\n'
printf '[PASS] complete shared-bench tenant cohort contract\n'
printf '[PASS] all-sites backup/maintenance/migrate/smoke sequencing contract\n'
printf '[PASS] per-site release evidence contract\n'
printf 'r1_r4_static_complete=true\n'
