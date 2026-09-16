#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RETURN_RATE_RESULT="$LOG_DIR/erpnext-phase6-return-rate-gate.txt"
TEMP_REDIS_READY=0

cleanup() {
  if [[ "$TEMP_REDIS_READY" == "1" ]]; then
    cd "$ROOT_DIR"
    bash deploy/bench_redis.sh stop || true
  fi
}
trap cleanup EXIT

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 6 closure gate on site: $SITE" >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 6 development is main-only." >&2
  exit 2
fi

echo "=================================================="
echo " ERPNext Phase 6 Closure Gate"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Branch: $(git branch --show-current)"
echo "Commit: $(git rev-parse --short=12 HEAD)"
echo

echo "===== FAIL-CLOSED STATIC CONTRACT ====="
bash scripts/run_erpnext_phase6_static_contract.sh "$SITE"

echo
echo "===== FULL PHASE 6 FINAL GATE ====="
bash scripts/run_erpnext_phase6_final_gate.sh "$SITE"

echo
echo "===== RETURN RATE AUTHORITY REGRESSION ====="
bash deploy/bench_redis.sh start
TEMP_REDIS_READY=1
bash deploy/bench_redis.sh status

cd "$ROOT_DIR/frappe-bench"
bench --site "$SITE" execute \
  ledgix_saas.migration.erpnext_phase6_return_rate_gate.run \
  | tee "$RETURN_RATE_RESULT"

python3 - "$RETURN_RATE_RESULT" <<'PY'
import json
import sys
from pathlib import Path

payload = None
for line in reversed(
    [x.strip() for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]
):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    if isinstance(value, dict) and "phase6_return_rate_complete" in value:
        payload = value
        break

if payload is None:
    print("[FAIL] Could not find Phase 6 return-rate gate JSON result.")
    raise SystemExit(1)

for name, passed in (payload.get("checks") or {}).items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")

if not payload.get("phase6_return_rate_complete"):
    print("[FAIL] ERPNext return-rate authority regression failed.")
    raise SystemExit(1)

print("[PASS] Client-supplied return rate cannot override the original ERPNext invoice rate.")
PY

echo
echo "===== PHASE 6 CLOSURE VERDICT ====="
echo "[PASS] Phase 6 static, transaction, pricing, payment-policy and return-rate authority gates are green."
echo "[NEXT] Phase 7 — Buying and Inventory Cutover"
echo "[OK] Return-rate result: $RETURN_RATE_RESULT"
