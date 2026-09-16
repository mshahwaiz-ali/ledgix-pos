#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
PHASE8_RESULT="$LOG_DIR/erpnext-phase8-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 8 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 8 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 8 POS Engine Migration Final Gate"
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
echo "===== MIGRATE PHASE 8 EXTENSION SCHEMA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== FAIL-CLOSED PHASE 6 + 7 + 8 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract \
  ledgix_saas.setup.test_erpnext_phase8_contract

echo
echo "===== PHASE 8 NATIVE POS CUTOVER ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase8_pos_gate.run \
  | tee "$PHASE8_RESULT"

echo
echo "===== PHASE 8 FINAL VERDICT ====="
python3 - "$PHASE8_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase8_complete" in value:
        payload = value
        break
if payload is None:
    print("[FAIL] Could not find Phase 8 gate JSON result.")
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
        for line in case.get("traceback_tail") or []:
            print("         " + line)

if payload.get("phase8_complete") and payload.get("phase9_ready") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 8 COMPLETE — Ledgix POS UX is backed by ERPNext POS Profile, Opening/Closing, POS Invoice, native pricing/payment/stock and native returns.")
    print("[PASS] No parallel Ledgix Sale/Payment/POS Shift/POS Hold/stock writes occurred on the tested POS cutover paths.")
    print("[PASS] FBR source cutover was NOT performed in Phase 8.")
    print("[NEXT] Phase 9 — FBR Source Cutover")
    raise SystemExit(0)

print("\n[FAIL] Phase 8 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 8 result: $PHASE8_RESULT"
