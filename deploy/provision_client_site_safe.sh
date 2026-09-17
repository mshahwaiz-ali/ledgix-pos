#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR_INPUT="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE=""
RELEASE=""
URL=""
APP="${APP_NAME:-ledgix_saas}"
TARGET_SHA=""
TMP_APP=""
TMP_CONTRACT=""
TARGET_STAGE=""
CREATED_DATABASE=0
CREATED_SITE=0
ADMIN_PASSWORD=""
DB_NAME=""
DB_PASSWORD=""
REUSE_EXISTING_SHARED_CODE=0
SECRETS_ROOT="${LEDGIX_SITE_SECRETS_DIR:-$HOME/.config/ledgix/sites}"

declare -a EXISTING_LEDgIX_SITES=()

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
Usage: deploy/provision_client_site_safe.sh --site SITE --release REF [options]

Creates one fresh isolated Ledgix client site on an already prepared supported
bench. ERPNext is installed before Ledgix. The script does not create client
business masters, apply a Business Profile, or activate FBR Production.

On a bench that already has Ledgix tenants, provisioning is code-preserving:
the requested immutable release must match every existing tenant's recorded
release and the current bench app must match that release exactly. The helper
will then reuse the existing shared code instead of syncing or changing it.
Use deploy/deploy_update_shared_safe.sh first when the shared bench must move to
a different release.

Options:
  --site SITE          New Frappe site name (required)
  --release REF        Full 40-character commit SHA or immutable tag (required)
  --url URL            Optional public URL; enables online smoke after provisioning
  --bench-dir PATH     Bench path (default: ./frappe-bench)
  --app APP            Custom app name (default: ledgix_saas)
  --help, -h           Show this help

Credentials are generated automatically and stored outside the repository with
owner-only permissions. No weak production defaults are provided.
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
TMP_APP="$BENCH_DIR/apps/.${APP}.provision.$$"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

strong_password() {
  openssl rand -base64 42 | tr -d '\n' | cut -c 1-40
}

random_hex() {
  openssl rand -hex "$1"
}

sql_quote() {
  printf '%s' "$1" | sed "s/'/''/g"
}

sql_identifier() {
  printf '%s' "$1" | sed 's/`/``/g'
}

discover_existing_ledgix_sites() {
  local config candidate apps
  for config in "$BENCH_DIR"/sites/*/site_config.json; do
    [[ -f "$config" ]] || continue
    candidate="$(basename "$(dirname "$config")")"
    [[ "$candidate" == "$SITE" ]] && continue
    apps="$(bench_run --site "$candidate" list-apps 2>/dev/null || true)"
    if printf '%s\n' "$apps" | awk '{print $1}' | grep -Fxq "$APP"; then
      printf '%s\n' "$candidate"
    fi
  done
}

recorded_release_sha() {
  local site="$1" record value
  for record in \
    "$BENCH_DIR/sites/$site/private/ledgix-release/last-successful.env" \
    "$BENCH_DIR/sites/$site/private/ledgix-provisioning/initial-provisioning.env"; do
    [[ -f "$record" ]] || continue
    value="$(awk -F= '$1=="deployed_sha" || $1=="release_sha" {print substr($0, index($0, "=") + 1); exit}' "$record")"
    value="${value#\"}"
    value="${value%\"}"
    if [[ "$value" =~ ^[0-9a-fA-F]{40}$ ]]; then
      printf '%s\n' "${value,,}"
      return 0
    fi
  done
  return 1
}

verify_existing_shared_code_matches_target() {
  local site recorded diff_output
  mapfile -t EXISTING_LEDgIX_SITES < <(discover_existing_ledgix_sites | sort -u)
  [[ "${#EXISTING_LEDgIX_SITES[@]}" -gt 0 ]] || return 1

  [[ -d "$DEST_APP" ]] || die "existing Ledgix tenants were found but bench app is missing: $DEST_APP"
  info "existing Ledgix tenants detected: ${EXISTING_LEDgIX_SITES[*]}"
  for site in "${EXISTING_LEDgIX_SITES[@]}"; do
    recorded="$(recorded_release_sha "$site" || true)"
    [[ -n "$recorded" ]] || die "$site has no immutable Ledgix release evidence; run the approved updater before adding another tenant"
    [[ "$recorded" == "$TARGET_SHA" ]] || die "$site records Ledgix release $recorded, but requested release is $TARGET_SHA. Run deploy/deploy_update_shared_safe.sh for the full tenant cohort first."
  done

  command -v tar >/dev/null 2>&1 || die 'tar is required to verify existing shared Ledgix code'
  command -v diff >/dev/null 2>&1 || die 'diff is required to verify existing shared Ledgix code'
  TARGET_STAGE="$(mktemp -d)"
  git -C "$REPO_ROOT" archive --format=tar "$TARGET_SHA" "apps/$APP" | tar -xf - -C "$TARGET_STAGE"
  [[ -d "$TARGET_STAGE/apps/$APP" ]] || die 'could not materialize target Ledgix app for shared-code verification'
  if ! diff_output="$(diff -qr \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='*.pyo' \
      --exclude='*.egg-info' \
      --exclude='.pytest_cache' \
      --exclude='.ruff_cache' \
      "$TARGET_STAGE/apps/$APP" "$DEST_APP" 2>&1)"; then
    [[ -z "$diff_output" ]] || printf '%s\n' "$diff_output" >&2
    die "existing shared bench Ledgix code does not exactly match requested release $TARGET_SHA; use the approved cohort updater before provisioning"
  fi

  REUSE_EXISTING_SHARED_CODE=1
  ok "existing shared bench already runs approved release $TARGET_SHA; code sync will be skipped"
  return 0
}

cleanup() {
  rm -rf "$TMP_APP" 2>/dev/null || true
  [[ -z "$TMP_CONTRACT" ]] || rm -f "$TMP_CONTRACT" 2>/dev/null || true
  [[ -z "$TARGET_STAGE" ]] || rm -rf "$TARGET_STAGE" 2>/dev/null || true
  if [[ "$CREATED_DATABASE" -eq 1 && "$CREATED_SITE" -eq 0 && -n "$DB_NAME" ]]; then
    warn 'site creation did not complete; cleaning newly-created database/user'
    ident="$(sql_identifier "$DB_NAME")"
    user_q="$(sql_quote "$DB_NAME")"
    sudo -n mariadb <<SQL || true
DROP DATABASE IF EXISTS \`$ident\`;
DROP USER IF EXISTS '$user_q'@'localhost';
FLUSH PRIVILEGES;
SQL
  elif [[ "$CREATED_SITE" -eq 1 ]]; then
    warn "provisioning exited after site creation; $SITE is retained for diagnosis and must not be treated as accepted"
  fi
}
trap cleanup EXIT

[[ -n "$SITE" ]] || die '--site is required'
[[ -n "$RELEASE" ]] || die '--release is required'
[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $SITE"
[[ "$APP" =~ ^[A-Za-z0-9_]+$ ]] || die "invalid app name: $APP"
if [[ -n "$URL" ]]; then
  [[ "$URL" =~ ^https?://[^[:space:]]+$ ]] || die "invalid --url: $URL"
fi
[[ -d "$REPO_ROOT/.git" ]] || die "repository not found: $REPO_ROOT"
[[ -d "$BENCH_DIR/apps/frappe" && -x "$BENCH_DIR/env/bin/python" ]] || die "invalid bench: $BENCH_DIR"
[[ -d "$BENCH_DIR/apps/erpnext" ]] || die 'ERPNext bench dependency is missing'
[[ -d "$SRC_APP" ]] || die "Ledgix source app missing: $SRC_APP"
[[ ! -e "$BENCH_DIR/sites/$SITE" ]] || die "refusing to provision existing site: $SITE"
command -v bench >/dev/null 2>&1 || die 'bench is not available in PATH'
command -v openssl >/dev/null 2>&1 || die 'openssl is required'
sudo -n true >/dev/null 2>&1 || die 'passwordless sudo is required'
sudo -n mariadb -e 'SELECT 1;' >/dev/null 2>&1 || die 'MariaDB passwordless sudo/socket administration is required'
[[ -z "$(git -C "$REPO_ROOT" status --short)" ]] || die 'repository has local changes; commit or stash them before provisioning'

printf '\n===== RESOLVE APPROVED RELEASE =====\n'
git -C "$REPO_ROOT" fetch origin --tags --prune
if [[ "$RELEASE" =~ ^[0-9a-fA-F]{40}$ ]]; then
  if ! git -C "$REPO_ROOT" cat-file -e "${RELEASE}^{commit}" 2>/dev/null; then
    git -C "$REPO_ROOT" fetch origin "$RELEASE"
  fi
  TARGET_SHA="$(git -C "$REPO_ROOT" rev-parse "${RELEASE}^{commit}" 2>/dev/null || true)"
elif git -C "$REPO_ROOT" show-ref --verify --quiet "refs/tags/$RELEASE"; then
  TARGET_SHA="$(git -C "$REPO_ROOT" rev-parse "refs/tags/${RELEASE}^{commit}")"
else
  die 'release must be a full 40-character commit SHA or immutable tag'
fi
TARGET_SHA="${TARGET_SHA,,}"
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || die "could not resolve immutable release: $RELEASE"
info "approved target SHA: $TARGET_SHA"

TMP_CONTRACT="$(mktemp)"
git -C "$REPO_ROOT" show "$TARGET_SHA:deploy/release_contract.env" >"$TMP_CONTRACT" \
  || die 'approved release is missing deploy/release_contract.env'
# shellcheck disable=SC1090
source "$TMP_CONTRACT"
[[ "${LEDGIX_APP:-}" == "$APP" ]] || die "release contract app mismatch: expected ${LEDGIX_APP:-missing}, provisioning $APP"

printf '\n===== EXISTING SHARED-BENCH RELEASE SAFETY =====\n'
if verify_existing_shared_code_matches_target; then
  info 'existing Ledgix tenants will keep their current code unchanged'
else
  info 'no existing Ledgix tenants detected; approved release will be synced for the first tenant'
fi

printf '\n===== PINNED BENCH CONTRACT =====\n'
BENCH_VERSIONS="$(bench_run version)"
FRAPPE_VERSION="$(printf '%s\n' "$BENCH_VERSIONS" | awk '$1=="frappe" {print $2; exit}')"
ERPNEXT_VERSION="$(printf '%s\n' "$BENCH_VERSIONS" | awk '$1=="erpnext" {print $2; exit}')"
[[ "$FRAPPE_VERSION" == "${LEDGIX_EXPECTED_FRAPPE_VERSION:-}" ]] \
  || die "Frappe version mismatch: expected ${LEDGIX_EXPECTED_FRAPPE_VERSION:-unset}, found ${FRAPPE_VERSION:-missing}"
[[ "$ERPNEXT_VERSION" == "${LEDGIX_EXPECTED_ERPNEXT_VERSION:-}" ]] \
  || die "ERPNext version mismatch: expected ${LEDGIX_EXPECTED_ERPNEXT_VERSION:-unset}, found ${ERPNEXT_VERSION:-missing}"
ok "supported bench: frappe $FRAPPE_VERSION / erpnext $ERPNEXT_VERSION"

printf '\n===== EXACT LEDGIX APP CONTRACT =====\n'
if [[ "$REUSE_EXISTING_SHARED_CODE" -eq 0 ]]; then
  git -C "$REPO_ROOT" checkout --detach "$TARGET_SHA"
  [[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" == "$TARGET_SHA" ]] || die 'repository did not land on approved release'
  [[ -d "$SRC_APP" ]] || die "source app missing after checkout: $SRC_APP"
  rm -rf "$TMP_APP"
  cp -a "$SRC_APP" "$TMP_APP"
  rm -rf "$DEST_APP"
  mv "$TMP_APP" "$DEST_APP"
  "$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
  if [[ -f "$SCRIPT_DIR/repair_apps_txt.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/repair_apps_txt.sh"
  fi
  ok 'bench Ledgix app mirrors approved release exactly for first tenant'
else
  "$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
  if [[ -f "$SCRIPT_DIR/repair_apps_txt.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/repair_apps_txt.sh"
  fi
  ok 'existing shared Ledgix code preserved; no checkout/sync/replacement performed'
fi

printf '\n===== CREATE ISOLATED SITE DATABASE =====\n'
ADMIN_PASSWORD="$(strong_password)"
DB_PASSWORD="$(strong_password)"
DB_NAME="site_$(random_hex 8)"
ident="$(sql_identifier "$DB_NAME")"
user_q="$(sql_quote "$DB_NAME")"
pass_q="$(sql_quote "$DB_PASSWORD")"
sudo -n mariadb <<SQL
CREATE DATABASE \`$ident\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER '$user_q'@'localhost' IDENTIFIED BY '$pass_q';
GRANT ALL PRIVILEGES ON \`$ident\`.* TO '$user_q'@'localhost';
FLUSH PRIVILEGES;
SQL
CREATED_DATABASE=1

printf '\n===== CREATE FRAPPE SITE =====\n'
bench_run new-site "$SITE" \
  --admin-password "$ADMIN_PASSWORD" \
  --db-name "$DB_NAME" \
  --db-password "$DB_PASSWORD" \
  --no-setup-db
CREATED_SITE=1

printf '\n===== INSTALL STANDARD STACK =====\n'
bench_run --site "$SITE" install-app erpnext
bench_run --site "$SITE" install-app "$APP"
bench_run --site "$SITE" migrate
bench_run build --app "$APP"
bench_run --site "$SITE" enable-scheduler
bench_run --site "$SITE" clear-cache
bench_run --site "$SITE" clear-website-cache
if [[ -n "$URL" ]]; then
  bench_run --site "$SITE" set-config host_name "$URL"
fi

printf '\n===== CLIENT DEPENDENCY PREFLIGHT =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"
bash "$SCRIPT_DIR/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== PROVISIONING EVIDENCE =====\n'
mkdir -p "$SECRETS_ROOT"
chmod 700 "$(dirname "$SECRETS_ROOT")" "$SECRETS_ROOT" 2>/dev/null || true
SECRET_FILE="$SECRETS_ROOT/$SITE.env"
{
  printf 'site=%q\n' "$SITE"
  printf 'administrator_user=Administrator\n'
  printf 'administrator_password=%q\n' "$ADMIN_PASSWORD"
  printf 'db_name=%q\n' "$DB_NAME"
  printf 'db_user=%q\n' "$DB_NAME"
  printf 'db_password=%q\n' "$DB_PASSWORD"
  printf 'release_sha=%q\n' "$TARGET_SHA"
} >"$SECRET_FILE"
chmod 600 "$SECRET_FILE"

EVIDENCE_DIR="$BENCH_DIR/sites/$SITE/private/ledgix-provisioning"
mkdir -p "$EVIDENCE_DIR"
chmod 700 "$EVIDENCE_DIR" 2>/dev/null || true
EVIDENCE="$EVIDENCE_DIR/initial-provisioning.env"
INSTALLED_APPS="$(bench_run --site "$SITE" list-apps)"
SITE_FRAPPE_VERSION="$(printf '%s\n' "$INSTALLED_APPS" | awk '$1=="frappe" {print $2; exit}')"
SITE_ERPNEXT_VERSION="$(printf '%s\n' "$INSTALLED_APPS" | awk '$1=="erpnext" {print $2; exit}')"
SITE_LEDgIX_VERSION="$(printf '%s\n' "$INSTALLED_APPS" | awk -v app="$APP" '$1==app {print $2; exit}')"
[[ "$SITE_FRAPPE_VERSION" == "${LEDGIX_EXPECTED_FRAPPE_VERSION:-}" ]] || die 'provisioned site Frappe version drifted'
[[ "$SITE_ERPNEXT_VERSION" == "${LEDGIX_EXPECTED_ERPNEXT_VERSION:-}" ]] || die 'provisioned site ERPNext version drifted'
[[ -n "$SITE_LEDgIX_VERSION" ]] || die 'Ledgix is missing from provisioned site'
{
  printf 'site=%q\n' "$SITE"
  printf 'url=%q\n' "$URL"
  printf 'provisioned_at_utc=%q\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'release_input=%q\n' "$RELEASE"
  printf 'release_sha=%q\n' "$TARGET_SHA"
  printf 'frappe_version=%q\n' "$SITE_FRAPPE_VERSION"
  printf 'erpnext_version=%q\n' "$SITE_ERPNEXT_VERSION"
  printf 'ledgix_version=%q\n' "$SITE_LEDgIX_VERSION"
  printf 'database_isolated=1\n'
  printf 'erpnext_installed_before_ledgix=1\n'
  printf 'shared_code_reused=%q\n' "$REUSE_EXISTING_SHARED_CODE"
  printf 'existing_ledgix_tenant_count=%q\n' "${#EXISTING_LEDgIX_SITES[@]}"
  printf 'business_masters_created_by_ledgix_provisioner=0\n'
  printf 'business_profile_applied=0\n'
  printf 'fbr_production_activated=0\n'
  printf 'dependency_preflight=passed\n'
  printf 'offline_smoke=passed\n'
} >"$EVIDENCE"
chmod 600 "$EVIDENCE"

if [[ -n "$URL" ]]; then
  printf '\n===== OPTIONAL ONLINE SMOKE =====\n'
  bash "$SCRIPT_DIR/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --online --url "$URL"
  printf 'online_smoke=passed\n' >>"$EVIDENCE"
else
  printf 'online_smoke=not_run\n' >>"$EVIDENCE"
fi

CREATED_DATABASE=0
CREATED_SITE=0

printf '\n===== FRESH CLIENT PROVISIONING VERDICT =====\n'
ok "fresh isolated site provisioned: $SITE"
ok "credentials retained outside repository: $SECRET_FILE"
ok "provisioning evidence: $EVIDENCE"
printf 'fresh_client_provisioning_complete=true\n'
printf '[NEXT] Configure native ERPNext Company/accounting/warehouse/POS prerequisites, then use /app/ledgix-setup.\n'
