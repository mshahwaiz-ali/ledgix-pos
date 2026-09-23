#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
REFERENCE_DOCTYPE="${2:-}"
REFERENCE_NAME="${3:-}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/fbr-redesign-v2-readiness.txt"
BENCH_PYTHON="$ROOT_DIR/frappe-bench/env/bin/python"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing V2 readiness evaluation on site: $SITE" >&2
  exit 2
fi

case "$REFERENCE_DOCTYPE" in
  "Sales Invoice"|"POS Invoice") ;;
  *)
    echo "[ERROR] Reference DocType must be 'Sales Invoice' or 'POS Invoice'." >&2
    exit 2
    ;;
esac

if [[ -z "$REFERENCE_NAME" ]]; then
  echo "[ERROR] Reference invoice name is required." >&2
  exit 2
fi

[[ -x "$BENCH_PYTHON" ]] || {
  echo "[ERROR] Bench Python not found: $BENCH_PYTHON" >&2
  exit 1
}

mkdir -p "$LOG_DIR"

KWARGS="$(
  "$BENCH_PYTHON" - "$REFERENCE_DOCTYPE" "$REFERENCE_NAME" <<'PY'
import json
import sys

print(json.dumps({
    "reference_doctype": sys.argv[1],
    "reference_name": sys.argv[2],
}))
PY
)"

echo "=================================================="
echo " FBR Redesign V2 - Readiness Evaluation"
echo "=================================================="
echo "Site: $SITE"
echo "Reference: $REFERENCE_DOCTYPE / $REFERENCE_NAME"
echo "Commit: $(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)"
echo
echo "READ ONLY: no payload POST, no database write, no FBR network."
echo

cd "$ROOT_DIR/frappe-bench"

bench --site "$SITE" execute   ledgix_saas.services.fbr_v2_readiness.evaluate_invoice_readiness   --kwargs "$KWARGS"   | tee "$RESULT"

echo
echo "[OK] Readiness result: $RESULT"
