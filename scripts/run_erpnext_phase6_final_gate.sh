#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
PHASE2_RESULT="$LOG_DIR/erpnext-phase2-regression-from-phase6.txt"
PHASE3_RESULT="$LOG_DIR/erpnext-phase3-regression-from-phase6.txt"
PHASE4_RESULT="$LOG_DIR/erpnext-phase4-regression-from-phase6.txt"
PHASE5_RESULT="$LOG_DIR/erpnext-phase5-regression-from-phase6.txt"
PHASE6_RESULT="$LOG_DIR/erpnext-phase6-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 6 final gate on site: $SITE" >&2
  echo "[ERROR] This runner is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

echo "=================================================="
echo " ERPNext Phase 2 + 3 + 4 + 5 + 6 Final Gate"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short=12 HEAD)"
echo

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 6 development is now main-only." >&2
  exit 2
fi

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== REDIS RUNTIME ====="
bash deploy/bench_redis.sh start
TEMP_REDIS_READY=1
bash deploy/bench_redis.sh status

echo
echo "===== MIGRATE PHASE 6 EXTENSION SCHEMA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== PHASE 6 STATIC CONTRACT ====="
bench --site "$SITE" run-tests \
  --app ledgix_saas \
  --module ledgix_saas.setup.test_erpnext_phase6_extensions \
  --skip-test-records

echo
echo "===== PHASE 2 REGRESSION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase2_final_gate.run \
  | tee "$PHASE2_RESULT"
python3 - "$PHASE2_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase2_complete" in value:
        payload = value
        break
if not payload or not payload.get("phase2_complete"):
    print("[FAIL] Phase 2 regression gate is not green.")
    raise SystemExit(1)
print("[PASS] Phase 2 regression gate remains green.")
PY

echo
echo "===== PHASE 3 REGRESSION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase3_schema_gate.run \
  | tee "$PHASE3_RESULT"
python3 - "$PHASE3_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase3_complete" in value:
        payload = value
        break
if not payload or not payload.get("phase3_complete"):
    print("[FAIL] Phase 3 regression gate is not green.")
    raise SystemExit(1)
print("[PASS] Phase 3 regression gate remains green.")
PY

echo
echo "===== PHASE 4 TAX / ACCOUNTING REGRESSION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase4_tax_parity_runtime.run \
  | tee "$PHASE4_RESULT"
python3 - "$PHASE4_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase4_complete" in value:
        payload = value
        break
if not payload or not payload.get("phase4_complete") or payload.get("failed_cases"):
    print("[FAIL] Phase 4 tax/accounting regression gate is not green.")
    if payload:
        print("       failed cases: " + ", ".join(payload.get("failed_cases") or []))
    raise SystemExit(1)
print("[PASS] Phase 4 tax/accounting regression gate remains green.")
PY

echo
echo "===== PHASE 5 MASTER MIGRATION REGRESSION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase5_master_migration_gate_runtime.run \
  | tee "$PHASE5_RESULT"
python3 - "$PHASE5_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase5_complete" in value:
        payload = value
        break
if not payload or not payload.get("phase5_complete") or not payload.get("phase6_ready"):
    print("[FAIL] Phase 5 master migration regression gate is not green.")
    raise SystemExit(1)
print("[PASS] Phase 5 master migration regression gate remains green.")
PY

echo
echo "===== PHASE 6 SELLING / PAYMENTS / RETURNS CUTOVER ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase6_selling_gate.run \
  | tee "$PHASE6_RESULT"

echo
echo "===== FINAL VERDICT ====="
python3 - "$PHASE6_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase6_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 6 final-gate JSON result.")
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

if payload.get("failed_cases"):
    print("\nFailed cases: " + ", ".join(payload["failed_cases"]))

print()
if payload.get("phase6_complete") and payload.get("phase7_ready"):
    print("[PASS] Phase 6 COMPLETE — new B2B sales, payments, receivables and returns use ERPNext authority.")
    print("[PASS] No parallel Ledgix Sale/Payment financial writes occurred on the Phase 6 path.")
    print("[PASS] Retail POS backend remains intentionally deferred to Phase 8.")
    print("[PASS] FBR network submission/source cutover remains intentionally deferred to Phase 9.")
    print(f"[NEXT] {payload.get('next_phase')}")
    raise SystemExit(0)

print("[FAIL] Phase 6 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 2 result: $PHASE2_RESULT"
echo "[OK] Phase 3 result: $PHASE3_RESULT"
echo "[OK] Phase 4 result: $PHASE4_RESULT"
echo "[OK] Phase 5 result: $PHASE5_RESULT"
echo "[OK] Phase 6 result: $PHASE6_RESULT"
