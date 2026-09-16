#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/erpnext-phase13-final-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 13 final gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 13 development is main-only." >&2
  exit 2
fi
mkdir -p "$LOG_DIR"

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 13 Client Profiles / SaaS Gate"
printf '%s\n' "=================================================="
printf 'Repo: %s\n' "$ROOT_DIR"
printf 'Site: %s\n' "$SITE"
printf 'Branch: %s\n' "$(git branch --show-current)"
printf 'Commit: %s\n' "$(git rev-parse HEAD)"
printf '\n'

echo "===== LOCAL CI ====="
bash scripts/ci_local.sh

echo
echo "===== REDIS RUNTIME ====="
bash deploy/bench_redis.sh start
TEMP_REDIS_READY=1
bash deploy/bench_redis.sh status

echo
echo "===== MIGRATE PHASE 13 SETUP PAGE / PROFILE METADATA ====="
cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" migrate

echo
echo "===== BUILD LEDGIX CLIENT ASSETS ====="
bench build --app ledgix_saas

echo
echo "===== INSTALLED APPS ====="
bench --site "$SITE" list-apps

cd "$ROOT_DIR"
echo
echo "===== CLIENT SITE ERPNEXT DEPENDENCY PREFLIGHT ====="
bash scripts/run_ledgix_client_preflight.sh "$SITE"

cd "$ROOT_DIR/frappe-bench"
echo
echo "===== FAIL-CLOSED PHASE 6 + 7 + 8 + 9 + 10 + 11 + 12 + 13 STATIC CONTRACTS ====="
./env/bin/python -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions \
  ledgix_saas.setup.test_erpnext_phase7_contract \
  ledgix_saas.setup.test_erpnext_phase8_contract \
  ledgix_saas.setup.test_erpnext_phase9_contract \
  ledgix_saas.setup.test_erpnext_phase10_contract \
  ledgix_saas.setup.test_erpnext_phase11_contract \
  ledgix_saas.setup.test_erpnext_phase12_contract \
  ledgix_saas.setup.test_erpnext_phase13_contract

echo
echo "===== PHASE 13 PROFILE MATRIX / CONFIGURATION-ONLY PROVISIONING ====="
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase13_client_setup_gate.run \
  | tee "$RESULT"

echo
echo "===== PHASE 13 FINAL VERDICT ====="
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
    if isinstance(value, dict) and "phase13_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 13 gate JSON result.")
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

if payload.get("phase13_complete") and payload.get("migration_complete") and not payload.get("failed_cases"):
    print()
    print("[PASS] Phase 13 COMPLETE — client complexity is configuration, not forks.")
    print("[PASS] All five Ledgix presets are validated against ERPNext-native prerequisites.")
    print("[PASS] Setup Wizard is configuration-only and creates no duplicate business masters or ledgers.")
    print("[PASS] Phase 12 frozen historical digest remains stable and the integration-site profile is restored after the gate.")
    print("[PASS] ERPNext Core Migration phases 0–13 are COMPLETE on the guarded integration workflow.")
    print("[NEXT] Client acceptance, production provisioning and release hardening.")
    raise SystemExit(0)

print("\n[FAIL] Phase 13 final gate did not pass.")
raise SystemExit(1)
PY

echo
echo "[OK] Phase 13 result: $RESULT"
