#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
LOG_FILE="$REPO_ROOT/logs/release-hardening-static-gate.txt"
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee "$LOG_FILE") 2>&1

printf '==================================================\n'
printf ' Ledgix Release Hardening Static Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

printf '\n===== RELEASE HARDENING CONTRACT =====\n'
if [[ -x "$BENCH_DIR/env/bin/python" ]]; then
  PYTHON="$BENCH_DIR/env/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  printf '[FAIL] Python is required for the static contract.\n' >&2
  exit 1
fi
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON" -m unittest -v ledgix_saas.setup.test_release_hardening_contract

printf '\n===== SAFE HELPER CLI CONTRACT =====\n'
bash "$REPO_ROOT/deploy/backup_safe.sh" --help >/dev/null
bash "$REPO_ROOT/deploy/deploy_update_safe.sh" --help >/dev/null
printf '[PASS] production helpers expose non-mutating help paths\n'

printf '\n===== RELEASE HARDENING STATIC VERDICT =====\n'
printf '[PASS] explicit production site contract\n'
printf '[PASS] immutable release SHA/tag contract\n'
printf '[PASS] verified backup + rollback metadata contract\n'
printf '[PASS] fail-closed maintenance behavior contract\n'
printf '[PASS] ERPNext-native smoke surface contract\n'
printf 'release_hardening_static_complete=true\n'
printf '[OK] result: %s\n' "$LOG_FILE"
