#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
REFERENCE_DOCTYPE="${2:-}"
REFERENCE_NAME="${3:-}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/fbr-redesign-phase4-snapshot-probe.txt"
BENCH_PYTHON="$ROOT_DIR/frappe-bench/env/bin/python"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 4 snapshot probe on site: $SITE" >&2
  echo "[ERROR] This diagnostic is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

case "$REFERENCE_DOCTYPE" in
  "Sales Invoice"|"POS Invoice")
    ;;
  *)
    echo "[ERROR] Reference DocType must be 'Sales Invoice' or 'POS Invoice'." >&2
    exit 2
    ;;
esac

if [[ -z "$REFERENCE_NAME" ]]; then
  echo "[ERROR] Reference invoice name is required." >&2
  echo "Usage: $0 ledgix-erpnext.local 'Sales Invoice' ACC-SINV-..." >&2
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

print(
    json.dumps(
        {
            "reference_doctype": sys.argv[1],
            "reference_name": sys.argv[2],
        }
    )
)
PY
)"

echo "=================================================="
echo " FBR Redesign Phase 4 - Native Snapshot Probe"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Reference: $REFERENCE_DOCTYPE / $REFERENCE_NAME"
echo "Branch: $(git -C "$ROOT_DIR" branch --show-current)"
echo "Commit: $(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)"
echo
echo "This probe writes no snapshot and makes no FBR network request."
echo

cd "$ROOT_DIR/frappe-bench"

bench --site "$SITE" execute   ledgix_saas.services.erpnext_fbr_snapshot.build_snapshot_candidate   --kwargs "$KWARGS"   | tee "$RESULT"

echo
echo "[OK] Probe result: $RESULT"
