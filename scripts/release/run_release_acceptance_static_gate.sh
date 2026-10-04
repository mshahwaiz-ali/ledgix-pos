#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
BENCH_PYTHON="$BENCH_DIR/env/bin/python"
[[ -x "$BENCH_PYTHON" ]] || { printf '[FAIL] bench Python missing: %s\n' "$BENCH_PYTHON" >&2; exit 1; }

# Focused contracts only. No bench/site initialization, migration, build,
# external transport, credentials, or cutover configuration writes.
export PYTHONPATH="$BENCH_DIR/apps:$BENCH_DIR/apps/fbr_v1:$BENCH_DIR/apps/frappe:$BENCH_DIR/apps/erpnext${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_ROOT"
"$BENCH_PYTHON" scripts/validation/check_fiscal_architecture.py
"$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_v1_bridge_contract \
  fbr_v1.setup.test_fbr_v1_readiness_runtime \
  fbr_v1.setup.test_sandbox_acceptance_runtime \
  ledgix_saas.setup.test_fbr_activation_contract \
  ledgix_saas.setup.test_fbr_client_certification_handoff_contract \
  ledgix_saas.setup.test_fbr_native_ui_v2_control_state_contract \
  ledgix_saas.setup.test_fbr_native_v2_preview_cutover_contract \
  ledgix_saas.setup.test_fbr_v2_activation_profile_contract \
  ledgix_saas.setup.test_fbr_v2_client_setup_readiness_contract \
  ledgix_saas.setup.test_fbr_v2_transport_contract \
  ledgix_saas.setup.test_fbr_redesign_v2_snapshot_persistence_contract \
  fbr_v1.setup.test_runtime_retirement_contract \
  fbr_v1.setup.test_fbr_v1_tax_readiness_runtime \
  ledgix_saas.setup.test_fbr_v2_legacy_transport_retirement_contract \
  ledgix_saas.setup.test_fbr_v2_print_legacy_seller_contract \
  ledgix_saas.setup.test_release_acceptance_contract

printf '[PASS] current V1 read-only readiness and Sandbox acceptance contracts\n'
printf '[PASS] retired V2 routes reject before DB, credentials, or transport\n'
printf '[PASS] Sandbox acceptance is separate from Production authorization\n'
printf 'release_acceptance_static_complete=true\n'
