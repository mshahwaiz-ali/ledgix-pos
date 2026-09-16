#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

printf '==================================================\n'
printf ' Ledgix FBR Activation Static Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

printf '\n===== PHASE 9 FBR REGRESSION CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_erpnext_phase9_contract

printf '\n===== R5 REGRESSION CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_client_readiness_contract

printf '\n===== FBR ACTIVATION CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m unittest -v ledgix_saas.setup.test_fbr_activation_contract

printf '\n===== FBR ACTIVATION STATIC VERDICT =====\n'
printf '[PASS] ERPNext-native FBR authority contract\n'
printf '[PASS] Sandbox configuration readiness contract\n'
printf '[PASS] persisted Sandbox validation/POST proof contract\n'
printf '[PASS] Production unarmed/reconciliation interlock contract\n'
printf '[PASS] strict release + fresh backup Production-switch contract\n'
printf '[PASS] private non-secret activation evidence contract\n'
printf 'fbr_activation_static_complete=true\n'
