#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

printf '==================================================\n'
printf ' Ledgix R3 Backup / Restore Static Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || true)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

printf '\n===== R3 CONTRACT TESTS =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON_BIN" -m unittest -v ledgix_saas.setup.test_backup_restore_contract

printf '\n===== SAFE HELPER CLI CONTRACT =====\n'
bash "$REPO_ROOT/deploy/backup_safe.sh" --help >/dev/null
bash "$REPO_ROOT/deploy/verify_backup_set.sh" --help >/dev/null
bash "$REPO_ROOT/deploy/restore_drill.sh" --help >/dev/null
bash "$SCRIPT_DIR/run_backup_restore_runtime_gate.sh" --help >/dev/null
printf '[PASS] backup/restore helpers expose non-mutating help paths\n'

printf '\n===== R3 STATIC VERDICT =====\n'
printf '[PASS] complete database/files/site-config backup contract\n'
printf '[PASS] checksum verification contract\n'
printf '[PASS] non-production restore isolation contract\n'
printf '[PASS] recovery-target safety backup contract\n'
printf '[PASS] Phase 12 frozen-state verification contract\n'
printf '[PASS] matching-release restore contract\n'
printf 'backup_restore_static_complete=true\n'
