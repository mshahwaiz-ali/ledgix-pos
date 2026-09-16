#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$ROOT_DIR/frappe-bench}"
SITE="${1:-}"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

pass() {
  printf '[PASS] %s\n' "$*"
}

[[ -n "$SITE" ]] || fail "Usage: bash scripts/run_ledgix_client_preflight.sh <site>"
[[ -d "$BENCH_DIR" ]] || fail "Bench not found: $BENCH_DIR"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "Frappe site not found: $SITE"

cd "$BENCH_DIR"
APPS="$(bench --site "$SITE" list-apps)"
printf '%s\n' "$APPS"

for app in frappe erpnext ledgix_saas; do
  if ! printf '%s\n' "$APPS" | grep -Eq "^${app}[[:space:]]"; then
    fail "Required app is not installed on $SITE: $app"
  fi
  pass "$app is installed"
done

frappe_version="$(printf '%s\n' "$APPS" | awk '$1=="frappe" {print $2; exit}')"
erpnext_version="$(printf '%s\n' "$APPS" | awk '$1=="erpnext" {print $2; exit}')"

[[ "$frappe_version" == 15.* ]] || fail "Ledgix requires Frappe v15; found ${frappe_version:-unknown}"
[[ "$erpnext_version" == 15.* ]] || fail "Ledgix requires ERPNext v15; found ${erpnext_version:-unknown}"
pass "Frappe/ERPNext major versions are pinned to v15"

if [[ -f "$BENCH_DIR/apps/ledgix_saas/ledgix_saas/hooks.py" ]]; then
  hooks="$BENCH_DIR/apps/ledgix_saas/ledgix_saas/hooks.py"
elif [[ -f "$ROOT_DIR/apps/ledgix_saas/hooks.py" ]]; then
  hooks="$ROOT_DIR/apps/ledgix_saas/hooks.py"
else
  fail "Could not locate Ledgix hooks.py"
fi

grep -Eq 'required_apps[[:space:]]*=[[:space:]]*\[[^]]*"erpnext"' "$hooks" \
  || fail "Ledgix required_apps does not enforce ERPNext"
pass "Ledgix app dependency contract requires ERPNext"

printf '\n[PASS] Client site dependency preflight is green for %s.\n' "$SITE"
printf '[NEXT] Open /app/ledgix-setup as Ledgix Admin/System Manager and complete the client configuration readiness checks.\n'
