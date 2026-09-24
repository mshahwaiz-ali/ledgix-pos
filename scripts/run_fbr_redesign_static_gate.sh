#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
BENCH_PYTHON="$BENCH_DIR/env/bin/python"

[[ -x "$BENCH_PYTHON" ]] || {
  printf '[FAIL] bench Python is required for Frappe-aware redesign contract tests: %s\n' "$BENCH_PYTHON" >&2
  exit 1
}

printf '==================================================\n'
printf ' Ledgix FBR / Tax Redesign Static Gate\n'
printf '==================================================\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Branch: %s\n' "$(git -C "$REPO_ROOT" branch --show-current)"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf 'Bench Python: %s\n' "$BENCH_PYTHON"

printf '\n===== LOCAL CI =====\n'
bash "$SCRIPT_DIR/ci_local.sh"

printf '\n===== PHASE 1 TAX AUTHORITY CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_phase1_tax_authority_contract

printf '\n===== PHASE 2 FBR V2 SCHEMA CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_phase2_schema_contract

printf '\n===== PHASE 3 REFERENCE SYNC CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_phase3_reference_contract

printf '\n===== PHASE 4 NATIVE SNAPSHOT CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_phase4_snapshot_contract

printf '\n===== V2 LEGACY MIGRATION RETIREMENT CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_v2_migration_contract

printf '\n===== LEGACY SETTINGS RETIREMENT CONTRACTS =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_v2_old_settings_source_deregistration_contract \
  ledgix_saas.setup.test_fbr_v2_old_settings_runtime_cleanup_contract \
  ledgix_saas.setup.test_fbr_v2_legacy_test_cleanup_contract \
  ledgix_saas.setup.test_fbr_v2_retired_settings_db_cleanup_contract

printf '\n===== V2 IDENTITY CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_identity_v2_contract

printf '\n===== V2 READINESS CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_v2_readiness_contract

printf '\n===== PHASE 9 LEGACY TAX RETIREMENT CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_phase9_legacy_tax_retirement_contract

printf '\n===== PHASE 6 DESK CUTOVER CONTRACT =====\n'
PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_redesign_phase6_desk_contract

printf '\n===== REDESIGN STATIC VERDICT =====\n'
printf '[PASS] transaction tax authority boundary is isolated\n'
printf '[PASS] FBR V2 schemas contain no shadow monetary tax engine\n'
printf '[PASS] Sandbox scenario is certification-scoped\n'
printf '[PASS] V2 reference sync is GET-only and non-destructive\n'
printf '[PASS] Production arming remains outside reference sync\n'
printf '[PASS] ERPNext-native line snapshot collector has no Ledgix tax formula\n'
printf '[PASS] unsupported pinned-v15 tax splits fail closed\n'
printf '[PASS] legacy V2 migration helper is retired and cannot read/copy old FBR state\n'
printf '[PASS] old FBR Settings package/runtime/test dependencies are retired\n'
printf '[PASS] legacy monetary tax write/calculation surfaces are fail-closed\n'
printf '[PASS] retained legacy tax/classification data is audit-only when frozen\n'
printf '[PASS] old FBR Settings DocType source tombstone is physically removed\n'
printf '[PASS] retired FBR Settings compatibility API shell is physically removed\n'
printf '[PASS] zero live Python imports reference the retired Settings API\n'
printf '[PASS] guarded cleanup helper remains unregistered and V2-safe\n'
printf '[PASS] FBR identity resolves from ERPNext Company/Customer/Address authority\n'
printf '[PASS] V2 readiness requires native tax + identity + official reference evidence\n'
printf '[PASS] Desk Tax & FBR Center exposes ERPNext-native tax + FBR V2 only\n'
printf '[PASS] Desk contains no Production invoice-submit action\n'
printf 'fbr_redesign_static_complete=true\n'
