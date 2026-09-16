#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
PHASE2_RESULT="$LOG_DIR/erpnext-phase2-final-gate-from-phase3.txt"
PHASE3_RESULT="$LOG_DIR/erpnext-phase3-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 3 final gate on site: $SITE" >&2
  echo "[ERROR] This runner is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

echo "=================================================="
echo " ERPNext Phase 2 + Phase 3 Final Gate"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short=12 HEAD)"
echo

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== REDIS RUNTIME ====="
bash deploy/bench_redis.sh start
TEMP_REDIS_READY=1
bash deploy/bench_redis.sh status

echo
echo "===== MIGRATE PHASE 3 SCHEMA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== PHASE 2 REGRESSION GATE ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase2_final_gate.run \
  | tee "$PHASE2_RESULT"

python3 - "$PHASE2_RESULT" <<'PY'
import json
import sys
from pathlib import Path

lines = [line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
payload = None
for line in reversed(lines):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "phase2_complete" in candidate:
        payload = candidate
        break
if not payload or not payload.get("phase2_complete"):
    failed = (payload or {}).get("failed_steps") or ["unknown"]
    print("[FAIL] Phase 2 regression gate: " + ", ".join(failed))
    raise SystemExit(1)
print("[PASS] Phase 2 regression gate remains green.")
PY

echo
echo "===== PHASE 3 EXTENSION SCHEMA GATE ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase3_schema_gate.run \
  | tee "$PHASE3_RESULT"

echo
echo "===== FINAL VERDICT ====="
python3 - "$PHASE3_RESULT" <<'PY'
import json
import sys
from pathlib import Path

lines = [line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
payload = None
for line in reversed(lines):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "phase3_complete" in candidate:
        payload = candidate
        break

if payload is None:
    print("[FAIL] Could not find Phase 3 final-gate JSON result.")
    raise SystemExit(1)

for name, passed in (payload.get("checks") or {}).items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")

if payload.get("errors"):
    print("\nErrors:")
    for error in payload["errors"]:
        print(f"  - {error}")

print()
if payload.get("phase3_complete"):
    print("[PASS] Phase 3 COMPLETE — ERPNext masters can hold all Ledgix-only FBR/product metadata.")
    print("[PASS] No standard business master was duplicated or cut over by this phase.")
    print(f"[NEXT] {payload.get('next_phase')}")
    raise SystemExit(0)

print("[FAIL] Phase 3 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 2 result: $PHASE2_RESULT"
echo "[OK] Phase 3 result: $PHASE3_RESULT"
