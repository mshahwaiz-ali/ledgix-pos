#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${PRODUCTION_SITE:-ledgix.local}"
APP="${APP_NAME:-ledgix_saas}"
BRANCH="${DEPLOY_BRANCH:-main}"
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.deploy.$$"
MAINTENANCE_ENABLED=0

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
NODE_MAJOR="${NODE_MAJOR:-22}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
  nvm use "$NODE_MAJOR" >/dev/null 2>&1 || true
fi

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

cleanup() {
  rm -rf "$TMP_APP" 2>/dev/null || true
  if [[ "$MAINTENANCE_ENABLED" -eq 1 ]]; then
    bench_run --site "$SITE" set-maintenance-mode off >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $SITE"
[[ "$APP" =~ ^[A-Za-z0-9_]+$ ]] || die "invalid app name: $APP"
[[ -d "$REPO_ROOT/.git" ]] || die "repository not found: $REPO_ROOT"
[[ -d "$BENCH_DIR/sites/$SITE" ]] || die "site not found: $SITE"
[[ -d "$BENCH_DIR/apps/frappe" ]] || die "invalid bench: $BENCH_DIR"
command -v bench >/dev/null 2>&1 || die 'bench is not available in PATH'
sudo -n true >/dev/null 2>&1 || die 'passwordless sudo is required'

if [[ -n "$(git -C "$REPO_ROOT" status --short)" ]]; then
  die 'repository has local changes; commit or stash them before deployment'
fi

printf '\n===== PRE-UPDATE BACKUP =====\n'
bench_run --site "$SITE" backup --with-files

printf '\n===== UPDATE REPOSITORY =====\n'
info "branch: $BRANCH"
git -C "$REPO_ROOT" fetch origin "$BRANCH"
git -C "$REPO_ROOT" pull --ff-only origin "$BRANCH"
ok "repo at $(git -C "$REPO_ROOT" rev-parse --short HEAD)"

[[ -d "$SRC_APP" ]] || die "source app missing after pull: $SRC_APP"

printf '\n===== MAINTENANCE MODE =====\n'
bench_run --site "$SITE" set-maintenance-mode on
MAINTENANCE_ENABLED=1

printf '\n===== ERPNEXT DEPENDENCY =====\n'
[[ -f "$SCRIPT_DIR/ensure_erpnext.sh" ]] || die "missing ERPNext dependency helper: $SCRIPT_DIR/ensure_erpnext.sh"
BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/ensure_erpnext.sh" --site "$SITE"

printf '\n===== EXACT APP SYNC =====\n'
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$SCRIPT_DIR/repair_apps_txt.sh" ]]; then
  bash "$SCRIPT_DIR/repair_apps_txt.sh"
fi
ok "bench app mirrors repository app exactly"

printf '\n===== BUILD ASSETS =====\n'
bench_run build

printf '\n===== MIGRATE SITE =====\n'
bench_run --site "$SITE" migrate
bench_run --site "$SITE" clear-cache
bench_run --site "$SITE" clear-website-cache

printf '\n===== REFRESH PRODUCTION PROCESSES =====\n'
if [[ -f "$SCRIPT_DIR/post_build_refresh.sh" ]]; then
  bash "$SCRIPT_DIR/post_build_refresh.sh"
else
  sudo -n supervisorctl restart frappe-bench-web:
  sudo -n supervisorctl restart frappe-bench-workers:
fi

printf '\n===== LEAVE MAINTENANCE MODE =====\n'
bench_run --site "$SITE" set-maintenance-mode off
MAINTENANCE_ENABLED=0

printf '\n===== NGINX + PROCESS VALIDATION =====\n'
sudo -n nginx -t
sudo -n systemctl reload nginx
sudo -n supervisorctl status

printf '\n===== FINAL APP STATE =====\n'
bench_run --site "$SITE" list-apps
printf 'Git: %s @ %s\n' "$(git -C "$REPO_ROOT" branch --show-current)" "$(git -C "$REPO_ROOT" rev-parse --short HEAD)"

printf '\n===== HTTP CHECK =====\n'
curl -fsSI --max-time 10 -H "Host: $SITE" http://127.0.0.1/ | head -n 1

ok "production update completed for $SITE"
