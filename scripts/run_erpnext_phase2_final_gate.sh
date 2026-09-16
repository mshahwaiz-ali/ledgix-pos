#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT_FILE="$LOG_DIR/erpnext-phase2-final-gate.txt"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 2 final gate on site: $SITE" >&2
  echo "[ERROR] This runner is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

echo "=================================================="
echo " ERPNext Phase 2 Final Gate"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short=12 HEAD)"
echo

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== INSTALLED APPS ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" list-apps

echo
echo "===== PHASE 2 FINAL GATE ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase2_final_gate.run \
  | tee "$RESULT_FILE"

echo
echo "===== FINAL VERDICT ====="
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
    if isinstance(candidate, dict) and "phase2_complete" in candidate:
        payload = candidate
        break

if payload is None:
    print("[FAIL] Could not find Phase 2 final-gate JSON result.")
    raise SystemExit(1)

for name, step in (payload.get("steps") or {}).items():
    if step.get("passed"):
        status = "PASS"
    elif step.get("blocked"):
        status = "BLOCKED"
    else:
        status = "FAIL"
    print(f"[{status}] {name}")
    if not step.get("passed") and step.get("error"):
        print(f"       {step.get('error_type', 'Error')}: {step['error']}")
        trace = step.get("traceback_tail") or []
        if trace:
            print("       traceback tail:")
            for row in trace:
                print(f"         {row}")

print()
print("===== GAP MATRIX =====")
for concept, detail in (payload.get("gap_matrix") or {}).items():
    print(f"{concept}: {detail.get('decision')} -> {detail.get('authority')}")

print()
if payload.get("phase2_complete"):
    print("[PASS] Phase 2 COMPLETE — ERPNext capability/gap decisions are evidence-backed.")
    print(f"[NEXT] {payload.get('next_phase')}")
    raise SystemExit(0)

failed = payload.get("failed_steps") or ["unknown"]
print("[FAIL] Phase 2 final gate failed: " + ", ".join(failed))
raise SystemExit(1)
PY

echo
echo "[OK] Result log: $RESULT_FILE"
