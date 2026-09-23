#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
LOG_DIR="$ROOT_DIR/logs"
RESULT="$LOG_DIR/fbr-redesign-phase1-native-tax-probe.txt"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 1 native-tax probe on site: $SITE" >&2
  echo "[ERROR] This read-only probe is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"

echo "=================================================="
echo " FBR Redesign Phase 1 - ERPNext Native Tax Probe"
echo "=================================================="
echo "Repo: $ROOT_DIR"
echo "Site: $SITE"
echo "Branch: $(git -C "$ROOT_DIR" branch --show-current)"
echo "Commit: $(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)"
echo

cd "$ROOT_DIR/frappe-bench"

bench --site "$SITE" execute   ledgix_saas.migration.fbr_redesign_phase1_native_tax_probe.run   | tee "$RESULT"

echo
echo "[OK] Read-only probe result: $RESULT"
