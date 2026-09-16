#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SITE="${PRODUCTION_SITE:-}"
RELEASE="${DEPLOY_RELEASE:-}"
URL="${PRODUCTION_URL:-}"
BENCH_DIR_INPUT="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
APP="${APP_NAME:-ledgix_saas}"
TMP_APP=""
MAINTENANCE_ENABLED=0
TARGET_SHA=""
PREVIOUS_SHA=""

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
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: deploy/deploy_update_safe.sh --site SITE --release REF --url URL [options]

Deploys an explicitly approved immutable Ledgix release to one existing site on
a single-tenant bench. Shared benches must use deploy/deploy_update_shared_safe.sh
so every Ledgix tenant is backed up, placed in maintenance and migrated together.
REF must be a full 40-character commit SHA or a Git tag. Moving branch names
such as main are rejected.

Options:
  --site SITE          Target Frappe site (required)
  --release REF        Full commit SHA or tag (required)
  --url URL            Public HTTPS/HTTP URL for online smoke checks (required)
  --bench-dir PATH     Bench path (default: ./frappe-bench)
  --app APP            Custom app name (default: ledgix_saas)
  --help, -h           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) [[ $# -ge 2 ]] || die '--site requires a value'; SITE="$2"; shift 2 ;;
    --release) [[ $# -ge 2 ]] || die '--release requires a value'; RELEASE="$2"; shift 2 ;;
    --url) [[ $# -ge 2 ]] || die '--url requires a value'; URL="${2%/}"; shift 2 ;;
    --bench-dir) [[ $# -ge 2 ]] || die '--bench-dir requires a value'; BENCH_DIR_INPUT="$2"; shift 2 ;;
    --app) [[ $# -ge 2 ]] || die '--app requires a value'; APP="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

case "$BENCH_DIR_INPUT" in
  /*) BENCH_DIR="$BENCH_DIR_INPUT" ;;
  ./*) BENCH_DIR="$REPO_ROOT/${BENCH_DIR_INPUT#./}" ;;
  *) BENCH_DIR="$REPO_ROOT/$BENCH_DIR_INPUT" ;;
esac

SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.deploy.$$"
CONTRACT="$REPO_ROOT/deploy/release_contract.env"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

cleanup() {
  rm -rf "$TMP_APP" 2>/dev/null || true
  if [[ "$MAINTENANCE_ENABLED" -eq 1 ]]; then
    warn "deployment exited before success; maintenance mode remains ON for $SITE"
    warn "recover using the verified pre-update backup and previous release $PREVIOUS_SHA"
  fi
}
trap cleanup EXIT

[[ -n "$SITE" ]] || die '--site is required'
[[ -n "$RELEASE" ]] || die '--release is required'
[[ -n "$URL" ]] || die '--url is required'
[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $SITE"
[[ "$APP" =~ ^[A-Za-z0-9_]+$ ]] || die "invalid app name: $APP"
[[ "$URL" =~ ^https?://[^[:space:]]+$ ]] || die "invalid --url: $URL"
[[ -d "$REPO_ROOT/.git" ]] || die "repository not found: $REPO_ROOT"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || die "site not found: $SITE"
[[ -d "$BENCH_DIR/apps/frappe" ]] || die "invalid bench: $BENCH_DIR"
command -v bench >/dev/null 2>&1 || die 'bench is not available in PATH'
sudo -n true >/dev/null 2>&1 || die 'passwordless sudo is required'

if [[ -n "$(git -C "$REPO_ROOT" status --short)" ]]; then
  die 'repository has local changes; commit or stash them before deployment'
fi

site_count=0
for site_config in "$BENCH_DIR"/sites/*/site_config.json; do
  [[ -f "$site_config" ]] || continue
  site_count=$((site_count + 1))
done
if [[ "$site_count" -gt 1 ]]; then
  die "bench contains $site_count sites; single-site updater refuses shared benches. Use deploy/deploy_update_shared_safe.sh with every Ledgix tenant explicitly approved."
fi

printf '\n===== RESOLVE IMMUTABLE RELEASE =====\n'
PREVIOUS_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
git -C "$REPO_ROOT" fetch origin --tags --prune
if [[ "$RELEASE" =~ ^[0-9a-fA-F]{40}$ ]]; then
  if ! git -C "$REPO_ROOT" cat-file -e "${RELEASE}^{commit}" 2>/dev/null; then
    git -C "$REPO_ROOT" fetch origin "$RELEASE"
  fi
  TARGET_SHA="$(git -C "$REPO_ROOT" rev-parse "${RELEASE}^{commit}" 2>/dev/null || true)"
elif git -C "$REPO_ROOT" show-ref --verify --quiet "refs/tags/$RELEASE"; then
  TARGET_SHA="$(git -C "$REPO_ROOT" rev-parse "refs/tags/${RELEASE}^{commit}")"
else
  die 'release must be a full 40-character commit SHA or tag; moving branch names are not accepted'
fi
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || die "could not resolve immutable release: $RELEASE"
info "previous release: $PREVIOUS_SHA"
info "approved release input: $RELEASE"
info "approved target SHA: $TARGET_SHA"

printf '\n===== VERIFIED PRE-UPDATE BACKUP =====\n'
[[ -f "$SCRIPT_DIR/backup_safe.sh" ]] || die "missing backup helper: $SCRIPT_DIR/backup_safe.sh"
bash "$SCRIPT_DIR/backup_safe.sh" \
  --site "$SITE" \
  --bench-dir "$BENCH_DIR" \
  --from-release "$PREVIOUS_SHA" \
  --to-release "$TARGET_SHA"

printf '\n===== MAINTENANCE MODE =====\n'
bench_run --site "$SITE" set-maintenance-mode on
MAINTENANCE_ENABLED=1

printf '\n===== CHECKOUT APPROVED RELEASE =====\n'
git -C "$REPO_ROOT" checkout --detach "$TARGET_SHA"
[[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" == "$TARGET_SHA" ]] || die 'repository did not land on approved release SHA'
[[ -f "$CONTRACT" ]] || die "release contract missing from approved release: $CONTRACT"
# shellcheck disable=SC1090
source "$CONTRACT"
[[ "${LEDGIX_APP:-}" == "$APP" ]] || die "release contract app mismatch: expected ${LEDGIX_APP:-missing}, deploying $APP"
[[ -d "$SRC_APP" ]] || die "source app missing after checkout: $SRC_APP"

printf '\n===== PINNED STACK CHECK =====\n'
APPS_BEFORE="$(bench_run --site "$SITE" list-apps)"
FRAPPE_VERSION="$(printf '%s\n' "$APPS_BEFORE" | awk '$1=="frappe" {print $2; exit}')"
ERPNEXT_VERSION="$(printf '%s\n' "$APPS_BEFORE" | awk '$1=="erpnext" {print $2; exit}')"
LEDGIX_VERSION="$(printf '%s\n' "$APPS_BEFORE" | awk '$1=="ledgix_saas" {print $2; exit}')"
[[ "$FRAPPE_VERSION" == "${LEDGIX_EXPECTED_FRAPPE_VERSION:-}" ]] \
  || die "Frappe version mismatch: expected ${LEDGIX_EXPECTED_FRAPPE_VERSION:-unset}, found ${FRAPPE_VERSION:-missing}"
[[ "$ERPNEXT_VERSION" == "${LEDGIX_EXPECTED_ERPNEXT_VERSION:-}" ]] \
  || die "ERPNext version mismatch: expected ${LEDGIX_EXPECTED_ERPNEXT_VERSION:-unset}, found ${ERPNEXT_VERSION:-missing}"
[[ -n "$LEDGIX_VERSION" ]] || die 'ledgix_saas is not installed on the target site'
ok "pinned stack already installed: frappe $FRAPPE_VERSION / erpnext $ERPNEXT_VERSION / ledgix $LEDGIX_VERSION"

# Updating Ledgix must never silently pull or rewrite ERPNext core. The exact
# supported ERPNext/Frappe versions are prerequisites and fail closed above.
printf '\n===== PRE-MUTATION CLIENT PREFLIGHT =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"

printf '\n===== EXACT LEDGIX APP SYNC =====\n'
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$SCRIPT_DIR/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/repair_apps_txt.sh"
fi
ok "bench app mirrors approved repository release exactly"

printf '\n===== BUILD ASSETS =====\n'
bench_run build

printf '\n===== MIGRATE SITE =====\n'
bench_run --site "$SITE" migrate
bench_run --site "$SITE" clear-cache
bench_run --site "$SITE" clear-website-cache

printf '\n===== POST-MIGRATION CLIENT PREFLIGHT =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"

printf '\n===== OFFLINE RELEASE SMOKE =====\n'
bash "$SCRIPT_DIR/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== REFRESH PRODUCTION PROCESSES =====\n'
if [[ -f "$SCRIPT_DIR/post_build_refresh.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/post_build_refresh.sh"
else
  sudo -n supervisorctl restart frappe-bench-web:
  sudo -n supervisorctl restart frappe-bench-workers:
fi
sudo -n nginx -t
sudo -n systemctl reload nginx
sudo -n supervisorctl status

printf '\n===== LEAVE MAINTENANCE MODE =====\n'
bench_run --site "$SITE" set-maintenance-mode off
MAINTENANCE_ENABLED=0

printf '\n===== ONLINE RELEASE SMOKE =====\n'
if ! bash "$SCRIPT_DIR/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --online --url "$URL"; then
  warn 'online smoke failed; restoring maintenance mode'
  bench_run --site "$SITE" set-maintenance-mode on || true
  MAINTENANCE_ENABLED=1
  die 'online release smoke failed'
fi

printf '\n===== FINAL RELEASE RECORD =====\n'
DEPLOYED_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$DEPLOYED_SHA" == "$TARGET_SHA" ]] || die 'deployed SHA changed unexpectedly during release'
RECORD_DIR="$BENCH_DIR/sites/$SITE/private/ledgix-release"
mkdir -p "$RECORD_DIR"
RECORD="$RECORD_DIR/last-successful.env"
LATEST_BACKUP_METADATA="$(find "$BENCH_DIR/sites/$SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
{
  printf 'site=%q\n' "$SITE"
  printf 'url=%q\n' "$URL"
  printf 'released_at_utc=%q\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'release_input=%q\n' "$RELEASE"
  printf 'previous_sha=%q\n' "$PREVIOUS_SHA"
  printf 'deployed_sha=%q\n' "$DEPLOYED_SHA"
  printf 'frappe_version=%q\n' "$FRAPPE_VERSION"
  printf 'erpnext_version=%q\n' "$ERPNEXT_VERSION"
  printf 'ledgix_app=%q\n' "$APP"
  printf 'backup_metadata=%q\n' "$LATEST_BACKUP_METADATA"
  printf 'dependency_preflight=passed\n'
  printf 'offline_smoke=passed\n'
  printf 'online_smoke=passed\n'
} >"$RECORD"
chmod 600 "$RECORD"

bench_run --site "$SITE" list-apps
printf 'Git: detached approved release @ %s\n' "$DEPLOYED_SHA"
ok "production update completed for $SITE"
ok "release record: $RECORD"
