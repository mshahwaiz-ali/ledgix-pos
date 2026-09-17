#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
BENCH_PYTHON="$BENCH_DIR/env/bin/python"

[[ -x "$BENCH_PYTHON" ]] || { printf '[FAIL] bench Python missing: %s\n' "$BENCH_PYTHON" >&2; exit 1; }

printf '==================================================\n'
printf ' Ledgix Release Acceptance Static Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf 'Bench Python: %s\n' "$BENCH_PYTHON"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

run_contract() {
  local label="$1" module="$2"
  printf '\n===== %s =====\n' "$label"
  PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
    "$BENCH_PYTHON" -m unittest -v "$module"
}

run_contract "PHASE 10 PRINT/REPORT REGRESSION" ledgix_saas.setup.test_erpnext_phase10_contract
run_contract "R3 BACKUP/RECOVERY REGRESSION" ledgix_saas.setup.test_backup_restore_contract
run_contract "R5 CLIENT READINESS REGRESSION" ledgix_saas.setup.test_client_readiness_contract
run_contract "FBR ACTIVATION REGRESSION" ledgix_saas.setup.test_fbr_activation_contract
run_contract "FINAL RELEASE ACCEPTANCE CONTRACT" ledgix_saas.setup.test_release_acceptance_contract

printf '\n===== RELEASE ACCEPTANCE STATIC VERDICT =====\n'
printf '[PASS] native A4 + thermal print authority contract\n'
printf '[PASS] true read-only Phase 12 verification contract\n'
printf '[PASS] profile-aware manual UAT evidence contract\n'
printf '[PASS] FBR external certification remains separate and non-sending\n'
printf '[PASS] final production gate is audit-only and immutable-release bound\n'
printf 'release_acceptance_static_complete=true\n'
