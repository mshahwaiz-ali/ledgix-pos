#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
MODE=""
SITE=""
URL=""
FAILURES=0
WARNINGS=0

usage() {
  cat <<'EOF'
Usage: ./deploy/smoke_test.sh --site SITE [--offline|--online|--all] [--url URL]

Options:
  --site SITE       Frappe site name to check
  --url URL         Public URL for online checks, for example https://erp.example.com
  --offline         Run checks that do not require web services
  --online          Run checks that require production web services
  --all             Run offline and online checks
  --bench-dir PATH  Bench directory (default: ./frappe-bench)
  --help, -h        Show this help
EOF
}

pass() { printf '[PASS] %s\n' "$*"; }
warn() { WARNINGS=$((WARNINGS + 1)); printf '[WARN] %s\n' "$*" >&2; }
fail() { FAILURES=$((FAILURES + 1)); printf '[FAIL] %s\n' "$*" >&2; }
info() { printf '[INFO] %s\n' "$*"; }

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --site) [[ $# -ge 2 ]] || { fail "--site requires a value"; exit 2; }; SITE="$2"; shift 2 ;;
      --url) [[ $# -ge 2 ]] || { fail "--url requires a value"; exit 2; }; URL="${2%/}"; shift 2 ;;
      --bench-dir) [[ $# -ge 2 ]] || { fail "--bench-dir requires a value"; exit 2; }; BENCH_DIR="$2"; shift 2 ;;
      --offline) MODE="offline"; shift ;;
      --online) MODE="online"; shift ;;
      --all) MODE="all"; shift ;;
      --help|-h) usage; exit 0 ;;
      *) fail "Unknown option: $1"; usage; exit 2 ;;
    esac
  done
  [[ -n "$SITE" ]] || { fail "--site is required"; usage; exit 2; }
  [[ -n "$MODE" ]] || MODE="offline"
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

run_maybe_sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif have_cmd sudo && sudo -n true >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

bench_python() {
  if [[ -x "$BENCH_DIR/env/bin/python" ]]; then
    printf '%s\n' "$BENCH_DIR/env/bin/python"
  elif have_cmd python3; then
    printf 'python3\n'
  else
    return 1
  fi
}

bench_cmd() {
  if [[ -x "$BENCH_DIR/env/bin/bench" ]]; then
    printf '%s\n' "$BENCH_DIR/env/bin/bench"
  elif have_cmd bench; then
    command -v bench
  else
    return 1
  fi
}

require_file() {
  local path="$1" label="$2"
  if [[ -f "$path" ]]; then pass "$label"; else fail "$label missing: $path"; fi
}

require_dir() {
  local path="$1" label="$2"
  if [[ -d "$path" ]]; then pass "$label"; else fail "$label missing: $path"; fi
}

http_status() {
  local url="$1"
  curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || true
}

check_http_route() {
  local path="$1" label="$2" code
  code="$(http_status "$URL$path")"
  if [[ "$code" =~ ^[23] ]]; then
    pass "$label responded with $code"
  elif [[ -n "$code" && "$code" != "000" ]]; then
    warn "$label responded with HTTP $code"
  else
    fail "$label did not respond"
  fi
}

run_optional_bench_check() {
  local label="$1"; shift
  local b
  b="$(bench_cmd 2>/dev/null || true)"
  if [[ -z "$b" ]]; then
    warn "$label skipped: bench command unavailable"
    return 0
  fi
  if (cd "$BENCH_DIR" && "$b" "$@" >/tmp/ledgix-smoke.$$ 2>&1); then
    pass "$label"
  else
    warn "$label could not complete"
    tail -n 12 /tmp/ledgix-smoke.$$ | sed 's/^/  /' >&2 || true
  fi
  rm -f /tmp/ledgix-smoke.$$
}

run_offline() {
  info "Running ERPNext-native Ledgix offline smoke checks for $SITE"
  require_dir "$BENCH_DIR/apps" "bench apps directory"
  require_dir "$BENCH_DIR/sites" "bench sites directory"
  require_file "$BENCH_DIR/sites/$SITE/site_config.json" "site_config.json for $SITE"
  require_file "$BENCH_DIR/sites/apps.txt" "bench apps.txt"
  require_dir "$REPO_ROOT/apps/ledgix_saas" "Ledgix source app"
  require_file "$REPO_ROOT/apps/ledgix_saas/hooks.py" "Ledgix hooks.py"
  require_file "$REPO_ROOT/apps/ledgix_saas/pyproject.toml" "Ledgix pyproject.toml"
  require_file "$REPO_ROOT/apps/ledgix_saas/modules.txt" "Ledgix modules.txt"
  require_file "$REPO_ROOT/apps/ledgix_saas/public/css/ledgix_brand.css" "brand CSS asset"
  require_file "$REPO_ROOT/apps/ledgix_saas/public/js/ledgix_brand.js" "brand JS asset"
  require_file "$REPO_ROOT/apps/ledgix_saas/api/client_setup.py" "client setup service"
  require_file "$REPO_ROOT/apps/ledgix_saas/api/product_shell.py" "product shell service"
  require_file "$REPO_ROOT/apps/ledgix_saas/api/fbr_native.py" "ERPNext-native FBR adapter"
  require_file "$REPO_ROOT/apps/ledgix_saas/services/erpnext_selling.py" "ERPNext-native selling service"
  require_file "$REPO_ROOT/apps/ledgix_saas/services/erpnext_pos.py" "ERPNext-native POS service"
  require_file "$REPO_ROOT/apps/ledgix_saas/ledgix/page/ledgix_setup/ledgix_setup.json" "client setup Desk page"
  require_file "$REPO_ROOT/apps/ledgix_saas/ledgix/doctype/ledgix_fbr_settings/ledgix_fbr_settings.json" "FBR Settings DocType JSON"
  require_file "$REPO_ROOT/apps/ledgix_saas/ledgix/doctype/ledgix_fbr_submission_log/ledgix_fbr_submission_log.json" "FBR Submission Log DocType JSON"

  if [[ -d "$BENCH_DIR/apps/ledgix_saas" ]] &&
    { [[ ! -f "$BENCH_DIR/apps/ledgix_saas/api/client_setup.py" ]] ||
      [[ ! -f "$BENCH_DIR/apps/ledgix_saas/api/fbr_native.py" ]] ||
      [[ ! -f "$BENCH_DIR/apps/ledgix_saas/services/erpnext_selling.py" ]]; }; then
    warn "bench app copy is missing current ERPNext-native Ledgix source files; sync apps before bench execute checks"
  fi

  local py
  py="$(bench_python 2>/dev/null || true)"
  if [[ -n "$py" ]]; then
    if PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" "$py" - <<'PY'
import importlib
for name in (
    "ledgix_saas",
    "ledgix_saas.hooks",
    "ledgix_saas.api.client_setup",
    "ledgix_saas.api.product_shell",
    "ledgix_saas.api.fbr_native",
    "ledgix_saas.services.erpnext_selling",
    "ledgix_saas.services.erpnext_pos",
):
    importlib.import_module(name)
PY
    then
      pass "Ledgix ERPNext-native Python imports"
    else
      fail "Ledgix ERPNext-native Python imports"
    fi
  else
    fail "Python unavailable for import checks"
  fi

  if grep -Fxq "ledgix_saas" "$BENCH_DIR/sites/apps.txt" 2>/dev/null; then
    pass "ledgix_saas registered in bench apps.txt"
  else
    fail "ledgix_saas is not registered in bench apps.txt"
  fi

  run_optional_bench_check "site installed-app list" --site "$SITE" list-apps
}

run_online() {
  info "Running online smoke checks for $SITE"
  [[ -n "$URL" ]] || { fail "--url is required for online smoke checks"; return 0; }
  have_cmd curl || { fail "curl is required for online smoke checks"; return 0; }

  if have_cmd supervisorctl; then
    if run_maybe_sudo supervisorctl status >/tmp/ledgix-supervisor.$$ 2>&1; then
      pass "supervisorctl status"
    else
      fail "supervisorctl status failed"
      sed 's/^/  /' /tmp/ledgix-supervisor.$$ >&2 || true
    fi
    rm -f /tmp/ledgix-supervisor.$$
  else
    fail "supervisorctl command missing"
  fi

  if have_cmd nginx; then
    if run_maybe_sudo nginx -t >/tmp/ledgix-nginx.$$ 2>&1; then
      pass "nginx config test"
    else
      fail "nginx config test failed"
      sed 's/^/  /' /tmp/ledgix-nginx.$$ >&2 || true
    fi
    rm -f /tmp/ledgix-nginx.$$
  else
    fail "nginx command missing"
  fi

  check_http_route "/login" "login route"
  check_http_route "/app" "app route"
  check_http_route "/assets/ledgix_saas/css/ledgix_brand.css" "custom static asset"

  local socket_code
  socket_code="$(http_status "$URL/socket.io/")"
  if [[ -n "$socket_code" && "$socket_code" != "000" ]]; then
    pass "socket.io route responded with $socket_code"
  else
    warn "socket.io route did not respond"
  fi

  local api_code
  api_code="$(http_status "$URL/api/method/frappe.auth.get_logged_user")"
  if [[ -n "$api_code" && "$api_code" != "000" ]]; then
    pass "safe API route responded with $api_code"
  else
    warn "safe API route did not respond"
  fi
}

summary() {
  printf '\nSmoke summary: %s failure(s), %s warning(s)\n' "$FAILURES" "$WARNINGS"
  [[ "$FAILURES" -eq 0 ]]
}

main() {
  parse_args "$@"
  printf 'Repo root: %s\nBench dir: %s\nSite: %s\n' "$REPO_ROOT" "$BENCH_DIR" "$SITE"
  case "$MODE" in
    offline) run_offline ;;
    online) run_online ;;
    all) run_offline; run_online ;;
    *) fail "unknown mode: $MODE" ;;
  esac
  summary
}

main "$@"
