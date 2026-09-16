#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/erpnext-phase12-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 12 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 12 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"
export LEDGIX_PHASE12_COMMIT="$(git rev-parse HEAD)"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 12 Legacy Freeze / Retirement Gate"
printf '%s\n' "=================================================="
printf 'Repo: %s\n' "$ROOT_DIR"
printf 'Site: %s\n' "$SITE"
printf 'Branch: %s\n' "$(git branch --show-current)"
printf 'Commit: %s\n' "$LEDGIX_PHASE12_COMMIT"
printf '\n'

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== REDIS RUNTIME ====="
bash deploy/bench_redis.sh start
TEMP_REDIS_READY=1
bash deploy/bench_redis.sh status

echo
echo "===== MIGRATE PHASE 12 RETIREMENT STATE / HOOKS ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== BUILD LEDGIX CLIENT ASSETS ====="
bench build --app ledgix_saas

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== FAIL-CLOSED PHASE 6 + 7 + 8 + 9 + 10 + 11 + 12 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract \
  ledgix_saas.setup.test_erpnext_phase8_contract \
  ledgix_saas.setup.test_erpnext_phase9_contract \
  ledgix_saas.setup.test_erpnext_phase10_contract \
  ledgix_saas.setup.test_erpnext_phase11_contract \
  ledgix_saas.setup.test_erpnext_phase12_contract

echo
echo "===== PHASE 12 RECONCILIATION / FREEZE / RETIREMENT ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase12_legacy_retirement_gate.run \
  | tee "$RESULT"

echo
echo "===== PHASE 12 FINAL VERDICT ====="
python3 - "$RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
lines = [line.strip() for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
for line in reversed(lines):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase12_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 12 gate JSON result.")
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
        evidence = case.get("evidence") or {}
        reconciliation = evidence.get("after") or evidence.get("before") or evidence.get("reconciliation")
        if isinstance(reconciliation, dict) and reconciliation.get("blockers"):
            print("       reconciliation blockers:")
            for blocker in reconciliation.get("blockers"):
                print("         - " + json.dumps(blocker, default=str, sort_keys=True))
        for trace_line in case.get("traceback_tail") or []:
            print("         " + trace_line)

snapshot_case = (payload.get("cases") or {}).get("legacy_history_preserved_without_delete") or {}
snapshot_checks = snapshot_case.get("checks") or {}
if not snapshot_checks.get("legacy_snapshot_matches"):
    print("[FAIL] legacy_snapshot_matches is not true.")
    raise SystemExit(1)

if payload.get("phase12_complete") and payload.get("phase13_ready") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 12 COMPLETE — duplicate Ledgix business-engine records are frozen historical audit data.")
    print("[PASS] Legacy masters are provenance-mapped, unresolved legacy drafts/open POS operations are zero, and the digest snapshot is stable.")
    print("[PASS] Legacy Admin/Manager/System access is read/report/export/print only; Cashier legacy access is removed.")
    print("[PASS] No legacy schema or business rows were deleted. Controlled rollback requires the explicit unfreeze confirmation phrase.")
    print("[NEXT] Phase 13 — Client Profiles and SaaS Productization")
    raise SystemExit(0)

print("\n[FAIL] Phase 12 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 12 result: $RESULT"
