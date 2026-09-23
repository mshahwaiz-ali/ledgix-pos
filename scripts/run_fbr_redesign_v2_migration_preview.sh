#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
COMPANY="${2:-}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/fbr-redesign-v2-migration-preview.txt"
BENCH_PYTHON="$ROOT_DIR/frappe-bench/env/bin/python"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing FBR V2 migration preview on site: $SITE" >&2
  echo "[ERROR] This helper is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

if [[ -z "$COMPANY" ]]; then
  echo "[ERROR] ERPNext Company is required." >&2
  echo "Usage: $0 ledgix-erpnext.local 'Company Name'" >&2
  exit 2
fi

[[ -x "$BENCH_PYTHON" ]] || {
  echo "[ERROR] Bench Python not found: $BENCH_PYTHON" >&2
  exit 1
}

mkdir -p "$LOG_DIR"

KWARGS="$(
  "$BENCH_PYTHON" - "$COMPANY" <<'PY'
import json
import sys

print(json.dumps({"company": sys.argv[1]}))
PY
)"

echo "=================================================="
echo " FBR Redesign V2 Migration Preview"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Company: $COMPANY"
echo "Branch: $(git -C "$ROOT_DIR" branch --show-current)"
echo "Commit: $(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)"
echo
echo "READ ONLY: no password values, no database writes, no FBR network."
echo

cd "$ROOT_DIR/frappe-bench"

bench --site "$SITE" execute   ledgix_saas.migration.fbr_redesign_v2_migration.preview_v2_migration   --kwargs "$KWARGS"   | tee "$RESULT"

echo
echo "[OK] Preview result: $RESULT"
