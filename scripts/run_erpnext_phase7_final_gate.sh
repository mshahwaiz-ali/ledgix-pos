#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
AP_RESULT="$LOG_DIR/erpnext-phase7-supplier-ap-preflight.txt"
PHASE7_RESULT="$LOG_DIR/erpnext-phase7-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 7 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 7 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 7 Buying + Inventory Final Gate"
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
echo "===== MIGRATE PHASE 7 EXTENSION SCHEMA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== FAIL-CLOSED PHASE 6 + PHASE 7 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract

echo
echo "===== PHASE 7 SUPPLIER AP PREFLIGHT ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase7_supplier_ap_preflight.run \
  | tee "$AP_RESULT"
python3 - "$AP_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "blocking_suppliers" in value:
        payload = value
        break
if payload is None:
    print("[FAIL] Could not find Phase 7 supplier AP preflight JSON.")
    raise SystemExit(1)
if not payload.get("ready"):
    print("[FAIL] Legacy/native supplier payable state is not reconciled.")
    for row in payload.get("blocking_suppliers") or []:
        print(
            "       {legacy_supplier} -> {erpnext_supplier}: legacy={legacy_current_payable} native={erpnext_current_payable} difference={difference}".format(**row)
        )
    raise SystemExit(1)
print(f"[PASS] Supplier AP preflight green for {payload.get('mapped_supplier_count', 0)} mapped supplier(s).")
PY

echo
echo "===== PHASE 7 BUYING / INVENTORY CUTOVER ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase7_buying_inventory_gate.run \
  | tee "$PHASE7_RESULT"

echo
echo "===== PHASE 7 FINAL VERDICT ====="
python3 - "$PHASE7_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase7_complete" in value:
        payload = value
        break
if payload is None:
    print("[FAIL] Could not find Phase 7 gate JSON result.")
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

if payload.get("phase7_complete") and payload.get("phase8_ready") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 7 COMPLETE — new buying, supplier payment, stock movement, traceability and valuation use ERPNext authority.")
    print("[PASS] No parallel Ledgix Purchase/Stock Movement/Lot/Serial writes occurred on the tested cutover paths.")
    print("[NEXT] Phase 8 — POS Engine Migration")
    raise SystemExit(0)

print("\n[FAIL] Phase 7 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Supplier AP preflight: $AP_RESULT"
echo "[OK] Phase 7 result: $PHASE7_RESULT"
