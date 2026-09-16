#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-ledgix-erpnext.local}"
BENCH_PY="$ROOT_DIR/frappe-bench/env/bin/python"

if [[ "$SITE" != "ledgix-erpnext.local" ]]; then
  echo "[ERROR] Refusing Phase 6 static contract on site: $SITE" >&2
  echo "[ERROR] This runner is restricted to ledgix-erpnext.local" >&2
  exit 2
fi

cd "$ROOT_DIR"

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "[ERROR] Phase 6 development is main-only." >&2
  exit 2
fi

if [[ ! -x "$BENCH_PY" ]]; then
  echo "[ERROR] Bench Python is missing or not executable: $BENCH_PY" >&2
  exit 2
fi

printf '%s\n' "=================================================="
printf '%s\n' " ERPNext Phase 6 Static Contract"
printf '%s\n' "=================================================="
printf 'Repo: %s\n' "$ROOT_DIR"
printf 'Site: %s\n' "$SITE"
printf 'Branch: %s\n' "$(git branch --show-current)"
printf 'Commit: %s\n' "$(git rev-parse --short=12 HEAD)"
printf '\n'

echo "===== PHASE 6 STATIC CONTRACT ====="
PYTHONPATH="$ROOT_DIR/apps${PYTHONPATH:+:$PYTHONPATH}" \
  "$BENCH_PY" -m unittest -v \
  ledgix_saas.setup.test_erpnext_phase6_extensions

echo
echo "[PASS] Phase 6 static contract executed and passed on $SITE."
