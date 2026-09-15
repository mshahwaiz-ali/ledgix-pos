#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT_FILE="$LOG_DIR/erpnext-phase2-core-batch.txt"
PREFLIGHT_FILE="$LOG_DIR/erpnext-phase2-preflight.txt"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 2 behavioral batch on site: $SITE" >&2
  echo "[ERROR] This runner is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"

cd "$ROOT_DIR"

echo "=================================================="
echo " Phase 2 ERPNext Core Batch"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== INSTALLED APPS ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" list-apps

echo
echo "===== PREFLIGHT ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_behavioral_preflight.run \
  | tee "$PREFLIGHT_FILE"

echo
echo "===== CORE BEHAVIORAL BATCH ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_behavioral_batch.run \
  | tee "$RESULT_FILE"

echo
echo "===== BATCH VERDICT ====="
python3 - "$RESULT_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

payload = None
for line in reversed(lines):
    try:
        candidate = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(candidate, dict) and "passed" in candidate:
        payload = candidate
        break

if payload is None:
    print("[FAIL] Could not find JSON batch result in output.")
    raise SystemExit(1)

steps = payload.get("steps") or {}
for name, result in steps.items():
    status = "PASS" if result.get("passed") else "FAIL"
    print(f"[{status}] {name}")
    if not result.get("passed") and result.get("error"):
        print(f"       {result.get('error_type', 'Error')}: {result['error']}")

if payload.get("passed"):
    print("[PASS] ERPNext Phase 2 core behavioral batch passed.")
    raise SystemExit(0)

failed = payload.get("failed_steps") or ["unknown"]
print("[FAIL] ERPNext Phase 2 core behavioral batch failed: " + ", ".join(failed))
raise SystemExit(1)
PY

echo
echo "[OK] Logs:"
echo "  $PREFLIGHT_FILE"
echo "  $RESULT_FILE"
