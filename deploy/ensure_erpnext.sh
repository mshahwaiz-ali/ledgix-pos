#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR_INPUT="${BENCH_DIR:-./frappe-bench}"
case "$BENCH_DIR_INPUT" in
  /*) BENCH_DIR="$BENCH_DIR_INPUT" ;;
  ./*) BENCH_DIR="$REPO_ROOT/${BENCH_DIR_INPUT#./}" ;;
  *) BENCH_DIR="$REPO_ROOT/$BENCH_DIR_INPUT" ;;
esac

FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"
ERPNEXT_BRANCH="${ERPNEXT_BRANCH:-version-15}"
ERPNEXT_REPO="${ERPNEXT_REPO:-https://github.com/frappe/erpnext.git}"
SITE=""

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: deploy/ensure_erpnext.sh [--site SITE]

Ensures the bench contains ERPNext on the configured v15 branch. When --site is
provided, ERPNext is also installed on that site before Ledgix migration.

Environment:
  BENCH_DIR        Default: ./frappe-bench
  FRAPPE_BRANCH    Default: $FRAPPE_BRANCH
  ERPNEXT_BRANCH   Default: $ERPNEXT_BRANCH
  ERPNEXT_REPO     Default: $ERPNEXT_REPO
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site)
      [[ $# -ge 2 ]] || die '--site requires a value'
      SITE="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
  nvm use "${NODE_MAJOR:-22}" >/dev/null 2>&1 || true
fi

command -v bench >/dev/null 2>&1 || die 'bench command is not available in PATH'
[[ -d "$BENCH_DIR/apps/frappe/.git" ]] || die "valid Frappe bench not found: $BENCH_DIR"
[[ -x "$BENCH_DIR/env/bin/python" ]] || die "bench Python environment missing: $BENCH_DIR/env"
[[ -d "$BENCH_DIR/sites" ]] || die "bench sites directory missing: $BENCH_DIR/sites"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

ensure_apps_txt_entry() {
  local app="$1"
  local apps_txt="$BENCH_DIR/sites/apps.txt"
  [[ -f "$apps_txt" ]] || : >"$apps_txt"
  if grep -Fxq "$app" "$apps_txt" 2>/dev/null; then
    return 0
  fi
  if [[ -s "$apps_txt" && -n "$(tail -c 1 "$apps_txt" 2>/dev/null || true)" ]]; then
    printf '\n' >>"$apps_txt"
  fi
  printf '%s\n' "$app" >>"$apps_txt"
  ok "registered bench app: $app"
}

check_branch() {
  local app="$1" expected="$2" app_dir="$BENCH_DIR/apps/$1" branch
  [[ -d "$app_dir/.git" ]] || die "$app is not a git checkout: $app_dir"
  branch="$(git -C "$app_dir" branch --show-current)"
  if [[ -z "$branch" ]]; then
    warn "$app is on a detached HEAD; expected branch policy is $expected"
    return 0
  fi
  [[ "$branch" == "$expected" ]] || die "$app branch mismatch: expected $expected, found $branch"
  ok "$app branch: $branch"
}

printf '\n===== ERPNEXT BENCH DEPENDENCY =====\n'
if [[ -d "$BENCH_DIR/apps/erpnext" ]]; then
  [[ -d "$BENCH_DIR/apps/erpnext/.git" ]] || die "ERPNext directory is not a git checkout: $BENCH_DIR/apps/erpnext"
  info "reusing ERPNext checkout: $BENCH_DIR/apps/erpnext"
else
  info "fetching ERPNext $ERPNEXT_BRANCH from $ERPNEXT_REPO"
  bench_run get-app --branch "$ERPNEXT_BRANCH" erpnext "$ERPNEXT_REPO"
fi

ensure_apps_txt_entry erpnext
"$BENCH_DIR/env/bin/python" -c 'import erpnext' >/dev/null 2>&1 || die 'ERPNext import failed'
check_branch frappe "$FRAPPE_BRANCH"
check_branch erpnext "$ERPNEXT_BRANCH"

info 'bench application versions:'
bench_run version --format plain

if [[ -n "$SITE" ]]; then
  [[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $SITE"
  [[ -d "$BENCH_DIR/sites/$SITE" ]] || die "site not found: $SITE"

  printf '\n===== ERPNEXT SITE DEPENDENCY =====\n'
  if bench_run --site "$SITE" list-apps 2>/dev/null | awk '{print $1}' | grep -Fxq erpnext; then
    info "ERPNext already installed on $SITE"
  else
    info "installing ERPNext on $SITE before Ledgix migration"
    bench_run --site "$SITE" install-app erpnext
  fi
fi

ok 'ERPNext dependency is ready'
