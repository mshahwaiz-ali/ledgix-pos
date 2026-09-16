#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/erpnext-phase11-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 11 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 11 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 11 Workspace / Product Final Gate"
printf '%s\n' "=================================================="
printf 'Repo: %s\n' "$ROOT_DIR"
printf 'Site: %s\n' "$SITE"
printf 'Branch: %s\n' "$(git branch --show-current)"
printf 'Commit: %s\n' "$(git rev-parse --short=12 HEAD)"
printf '\n'

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== REDIS RUNTIME ====="
bash deploy/bench_redis.sh start
TEMP_REDIS_READY=1
bash deploy/bench_redis.sh status

echo
echo "===== MIGRATE PHASE 11 PRODUCT SHELL ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== BUILD LEDGIX CLIENT ASSETS ====="
bench build --app ledgix_saas

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== FAIL-CLOSED PHASE 6 + 7 + 8 + 9 + 10 + 11 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract \
  ledgix_saas.setup.test_erpnext_phase8_contract \
  ledgix_saas.setup.test_erpnext_phase9_contract \
  ledgix_saas.setup.test_erpnext_phase10_contract \
  ledgix_saas.setup.test_erpnext_phase11_contract

echo
echo "===== PHASE 11 WORKSPACE / PRODUCT SIMPLIFICATION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase11_product_shell_gate.run \
  | tee "$RESULT"

echo
echo "===== PHASE 11 FINAL VERDICT ====="
python3 - "$RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase11_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 11 gate JSON result.")
    raise SystemExit(1)

for name, case in (payload.get("cases") or {}).items():
    passed = bool(case.get("passed"))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        if case.get("error_type"):
            print(f"       {case.get('error_type')}: {case.get('error')}")
        failed_checks = [key for key, value in (case.get("checks") or {}).items() if not value]
        if failed_checks:
            print("       failed checks: " + ", ".join(failed_checks))
        for trace_line in case.get("traceback_tail") or []:
            print("         " + trace_line)

if payload.get("phase11_complete") and payload.get("phase12_ready") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 11 COMPLETE — Ledgix is the curated product entry point over ERPNext native Forms/Lists.")
    print("[PASS] Cashier/Manager/Admin navigation is role-aware and Business Profile-aware without granting permissions.")
    print("[PASS] Legacy operational DocTypes are absent from the active workspace and no business/permission ledgers were changed by the shell gate.")
    print("[NEXT] Phase 12 — Legacy Freeze, Reconciliation and Retirement")
    raise SystemExit(0)

print("\n[FAIL] Phase 11 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 11 result: $RESULT"
