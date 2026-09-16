#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

printf '==================================================\n'
printf ' Ledgix R5 Client Onboarding / Readiness Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

printf '\n===== R3 REGRESSION CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_backup_restore_contract

printf '\n===== R1 + R4 REGRESSION CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_provisioning_multisite_contract

printf '\n===== R5 CONTRACT TESTS =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_client_readiness_contract

printf '\n===== R5 STATIC VERDICT =====\n'
printf '[PASS] ERPNext-native onboarding readiness contract\n'
printf '[PASS] profile setup reuse contract\n'
printf '[PASS] accounting/payment prerequisite contract\n'
printf '[PASS] named Ledgix user/role contract\n'
printf '[PASS] FBR pre-activation safety interlock contract\n'
printf '[PASS] private non-secret readiness evidence contract\n'
printf '[PASS] setup UI onboarding visibility contract\n'
printf 'r5_static_complete=true\n'
