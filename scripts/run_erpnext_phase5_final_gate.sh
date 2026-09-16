#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
PHASE2_RESULT="$LOG_DIR/erpnext-phase2-final-gate-from-phase5.txt"
PHASE3_RESULT="$LOG_DIR/erpnext-phase3-final-gate-from-phase5.txt"
PHASE4_RESULT="$LOG_DIR/erpnext-phase4-final-gate-from-phase5.txt"
PHASE5_RESULT="$LOG_DIR/erpnext-phase5-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 5 final gate on site: $SITE" >&2
  echo "[ERROR] This runner is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

echo "=================================================="
echo " ERPNext Phase 2 + 3 + 4 + 5 Final Gate"
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
echo "===== MIGRATE PHASE 5 EXTENSION SCHEMA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

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
for line in reversed([line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "phase2_complete" in candidate:
        payload = candidate
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
for line in reversed([line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "phase3_complete" in candidate:
        payload = candidate
        break
if not payload or not payload.get("phase3_complete"):
    print("[FAIL] Phase 3 regression gate is not green.")
    raise SystemExit(1)
print("[PASS] Phase 3 regression gate remains green.")
PY

echo
echo "===== PHASE 4 TAX REGRESSION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase4_tax_parity_gate_v3.run \
  | tee "$PHASE4_RESULT"

python3 - "$PHASE4_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "phase4_complete" in candidate:
        payload = candidate
        break
if not payload or not payload.get("phase4_complete") or payload.get("failed_cases"):
    print("[FAIL] Phase 4 tax/accounting regression gate is not green.")
    if payload:
        print("       failed cases: " + ", ".join(payload.get("failed_cases") or []))
    raise SystemExit(1)
print("[PASS] Phase 4 tax/accounting regression gate remains green.")
PY

echo
echo "===== PHASE 5 MASTER MIGRATION / RECONCILIATION ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase5_master_migration_gate_v3.run \
  | tee "$PHASE5_RESULT"

echo
echo "===== FINAL VERDICT ====="
python3 - "$PHASE5_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed([line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "phase5_complete" in candidate:
        payload = candidate
        break

if payload is None:
    print("[FAIL] Could not find Phase 5 final-gate JSON result.")
    raise SystemExit(1)

for name, passed in (payload.get("checks") or {}).items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")

first = payload.get("first_migration") or {}
second = payload.get("second_migration") or {}
if first.get("conflicts"):
    print("\nFirst-run conflicts:")
    for row in first["conflicts"]:
        print(f"  - {row}")
if second.get("conflicts"):
    print("\nRerun conflicts:")
    for row in second["conflicts"]:
        print(f"  - {row}")

print()
if payload.get("phase5_complete") and payload.get("phase6_ready"):
    print("[PASS] Phase 5 COMPLETE — native ERPNext master migration and reconciliation are proven.")
    print("[PASS] Dry-run rollback and actual idempotent rerun are proven.")
    print("[PASS] Stock-enabled and Invoice + FBR Only non-stock Item migration are both proven.")
    print("[PASS] Legacy masters were not deleted/frozen; transaction authority was not cut over.")
    print(f"[NEXT] {payload.get('next_phase')}")
    raise SystemExit(0)

print("[FAIL] Phase 5 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 2 result: $PHASE2_RESULT"
echo "[OK] Phase 3 result: $PHASE3_RESULT"
echo "[OK] Phase 4 result: $PHASE4_RESULT"
echo "[OK] Phase 5 result: $PHASE5_RESULT"
