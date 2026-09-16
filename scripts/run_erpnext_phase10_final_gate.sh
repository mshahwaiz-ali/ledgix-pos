#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/erpnext-phase10-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 10 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 10 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 10 BI / Reports / Print Final Gate"
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
echo "===== MIGRATE NATIVE REPORT / PRINT METADATA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== BUILD LEDGIX CLIENT ASSETS ====="
bench build --app ledgix_saas

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== FAIL-CLOSED PHASE 6 + 7 + 8 + 9 + 10 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract \
  ledgix_saas.setup.test_erpnext_phase8_contract \
  ledgix_saas.setup.test_erpnext_phase9_contract \
  ledgix_saas.setup.test_erpnext_phase10_contract

echo
echo "===== PHASE 10 NATIVE BI / REPORT / PRINT CUTOVER ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase10_reporting_print_gate.run \
  | tee "$RESULT"

echo
echo "===== PHASE 10 FINAL VERDICT ====="
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
    if isinstance(value, dict) and "phase10_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 10 gate JSON result.")
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

network = payload.get("network_safety") or {}
if network.get("real_fbr_network_calls") != 0:
    print("[FAIL] Phase 10 gate attempted a real FBR/PRAL network adapter call.")
    raise SystemExit(1)

if payload.get("phase10_complete") and payload.get("phase11_ready") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 10 COMPLETE — active Ledgix BI and reports read ERPNext-native data only.")
    print("[PASS] Ledgix A4 / thermal / Credit Note printing renders native Sales Invoice and POS Invoice documents with persisted FBR QR/reference metadata.")
    print("[PASS] Historical legacy print formats remain available only for historical Ledgix Sale records; new POS printing targets ERPNext documents.")
    print("[PASS] Phase 10 gate made zero real FBR/PRAL network calls.")
    print("[NEXT] Phase 11 — Workspace and Product Simplification")
    raise SystemExit(0)

print("\n[FAIL] Phase 10 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 10 result: $RESULT"
