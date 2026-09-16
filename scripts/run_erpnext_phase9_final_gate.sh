#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/erpnext-phase9-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 9 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 9 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 9 FBR Source Cutover Final Gate"
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
echo "===== MIGRATE PHASE 9 EXTENSION SCHEMA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== BUILD LEDGIX CLIENT ASSETS ====="
bench build --app ledgix_saas

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

echo
echo "===== FAIL-CLOSED PHASE 6 + 7 + 8 + 9 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract \
  ledgix_saas.setup.test_erpnext_phase8_contract \
  ledgix_saas.setup.test_erpnext_phase9_contract

echo
echo "===== PHASE 9 NATIVE FBR SOURCE CUTOVER ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase9_fbr_gate.run \
  | tee "$RESULT"

echo
echo "===== PHASE 9 FINAL VERDICT ====="
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
    if isinstance(value, dict) and "phase9_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 9 gate JSON result.")
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
    print("[FAIL] Phase 9 gate reported a real FBR network call.")
    raise SystemExit(1)

if payload.get("phase9_complete") and payload.get("phase10_ready") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 9 COMPLETE — FBR source authority is ERPNext Sales Invoice / POS Invoice / native Credit Note.")
    print("[PASS] Ledgix still owns FBR settings, transport, logs, QR/reference, reconciliation and correction tracking.")
    print("[PASS] Consolidated POS Sales Invoice is excluded, legacy Ledgix Sale production submit is retired, and no dual source writes occurred.")
    print("[PASS] Migration gate used mocked FBR adapters only; zero real FBR/PRAL network calls were made.")
    print("[NEXT] Phase 10 — Final Print Redesign")
    raise SystemExit(0)

print("\n[FAIL] Phase 9 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 9 result: $RESULT"
