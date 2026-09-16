#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="${BENCH_DIR:-$ROOT_DIR/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
ACTION="menu"
CONFIRM=""
APP="ledgix_saas"
SRC_APP="$ROOT_DIR/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.site-sync.$$"
SECRETS_DIR="$ROOT_DIR/.secrets/sites"
TEMP_REDIS_STARTED=0
LOCAL_ADMIN_PASSWORD="${LEDGIX_LOCAL_ADMIN_PASSWORD:-admin}"
LOCAL_USER_PASSWORD="${LEDGIX_LOCAL_USER_PASSWORD:-admin@123}"
LOCAL_DB_PASSWORD="${LEDGIX_LOCAL_DB_PASSWORD:-admin@123}"

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
  nvm use "${NODE_MAJOR:-22}" >/dev/null 2>&1 || true
fi

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: ./site_setup.sh [--ensure|--reset|--status] [--site SITE] [--confirm PHRASE]

Ledgix local development uses one canonical site with the standard stack:
  Frappe -> ERPNext -> ledgix_saas

There is no app-selection menu. ERPNext is a required dependency and Ledgix is
always installed after ERPNext.

Local credential convention:
  Administrator password: admin
  Other enabled users:     admin@123
  Site database password:  admin@123

Actions:
  --ensure              Create/repair the canonical site without deleting data
  --reset               Delete all active local sites and recreate one clean site
  --status              Show the canonical site and installed apps

Options:
  --site SITE           Default: ledgix-erpnext.local
  --confirm PHRASE      Required for --reset: RESET <site>
  --help, -h            Show this help

Examples:
  ./site_setup.sh --ensure
  ./site_setup.sh --reset --confirm "RESET ledgix-erpnext.local"
  ./site_setup.sh --status
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ensure) ACTION="ensure"; shift ;;
    --reset) ACTION="reset"; shift ;;
    --status) ACTION="status"; shift ;;
    --site) [[ $# -ge 2 ]] || die '--site requires a value'; SITE="$2"; shift 2 ;;
    --confirm) [[ $# -ge 2 ]] || die '--confirm requires a value'; CONFIRM="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

cleanup() {
  rm -rf "$TMP_APP" 2>/dev/null || true
  if [[ "$TEMP_REDIS_STARTED" -eq 1 && -f "$ROOT_DIR/deploy/bench_redis.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$ROOT_DIR/deploy/bench_redis.sh" stop || true
  fi
}
trap cleanup EXIT

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) die "local site manager only accepts .local/.localhost sites; got: $SITE" ;;
esac

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

validate_runtime() {
  [[ -d "$BENCH_DIR/apps/frappe" ]] || die "Frappe bench not found: $BENCH_DIR"
  [[ -x "$BENCH_DIR/env/bin/python" ]] || die "bench Python missing: $BENCH_DIR/env/bin/python"
  [[ -d "$BENCH_DIR/sites" ]] || die "bench sites directory missing: $BENCH_DIR/sites"
  command -v bench >/dev/null 2>&1 || die 'bench command not found; run ./install.sh first'
  command -v openssl >/dev/null 2>&1 || die 'openssl is required'
}

site_names() {
  find "$BENCH_DIR/sites" -mindepth 1 -maxdepth 1 -type d \
    ! -name assets ! -name archived ! -name archived_sites \
    -exec test -f "{}/site_config.json" \; -printf '%f\n' 2>/dev/null | sort
}

site_count() {
  site_names | awk 'NF {count++} END {print count+0}'
}

config_value() {
  local site="$1" key="$2" config="$BENCH_DIR/sites/$site/site_config.json"
  [[ -f "$config" ]] || return 1
  "$BENCH_DIR/env/bin/python" - "$config" "$key" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
value = payload.get(sys.argv[2], "")
print("" if value is None else value)
PY
}

shell_quote() {
  printf '%q' "$1"
}

secret_file() {
  printf '%s/%s.env\n' "$SECRETS_DIR" "$SITE"
}

save_credentials() {
  local admin_password="$1" db_name="$2" db_password="$3" file
  mkdir -p "$SECRETS_DIR"
  chmod 700 "$ROOT_DIR/.secrets" "$SECRETS_DIR" 2>/dev/null || true
  file="$(secret_file)"
  {
    printf 'SITE_NAME=%s\n' "$(shell_quote "$SITE")"
    printf 'SITE_URL=%s\n' "$(shell_quote "http://$SITE:8000")"
    printf 'ADMIN_USER=Administrator\n'
    printf 'ADMIN_PASSWORD=%s\n' "$(shell_quote "$admin_password")"
    printf 'DEFAULT_USER_PASSWORD=%s\n' "$(shell_quote "$LOCAL_USER_PASSWORD")"
    printf 'DB_NAME=%s\n' "$(shell_quote "$db_name")"
    printf 'DB_USER=%s\n' "$(shell_quote "$db_name")"
    printf 'DB_PASSWORD=%s\n' "$(shell_quote "$db_password")"
    printf 'INSTALLED_APPS=%s\n' "$(shell_quote 'frappe, erpnext, ledgix_saas')"
    printf 'BENCH_DIR=%s\n' "$(shell_quote "$BENCH_DIR")"
    printf 'CREATED_AT_UTC=%s\n' "$(shell_quote "$(date -u '+%Y-%m-%dT%H:%M:%SZ')")"
  } >"$file"
  chmod 600 "$file"
  ok "local credentials saved outside Git: $file"
}

sync_ledgix_exact() {
  [[ -d "$SRC_APP" ]] || die "Ledgix source missing: $SRC_APP"
  mkdir -p "$BENCH_DIR/apps"
  if [[ -e "$DEST_APP" && "$(readlink -f "$SRC_APP")" == "$(readlink -f "$DEST_APP")" ]]; then
    info 'bench Ledgix app already resolves to repository source'
  else
    rm -rf "$TMP_APP"
    cp -a "$SRC_APP" "$TMP_APP"
    rm -rf "$DEST_APP"
    mv "$TMP_APP" "$DEST_APP"
    ok 'bench Ledgix app now mirrors repository source exactly'
  fi
  "$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
  if [[ -f "$ROOT_DIR/deploy/repair_apps_txt.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$ROOT_DIR/deploy/repair_apps_txt.sh"
  fi
}

ensure_erpnext_bench() {
  [[ -f "$ROOT_DIR/deploy/ensure_erpnext.sh" ]] || die 'deploy/ensure_erpnext.sh is missing'
  BENCH_DIR="$BENCH_DIR" bash "$ROOT_DIR/deploy/ensure_erpnext.sh"
}

start_redis() {
  [[ -f "$ROOT_DIR/deploy/bench_redis.sh" ]] || die 'deploy/bench_redis.sh is missing'
  BENCH_DIR="$BENCH_DIR" bash "$ROOT_DIR/deploy/bench_redis.sh" start
  TEMP_REDIS_STARTED=1
}

random_hex() {
  openssl rand -hex "$1"
}

strong_password() {
  openssl rand -base64 42 | tr -d '\n' | cut -c 1-40
}

sql_quote() {
  printf '%s' "$1" | sed "s/'/''/g"
}

sql_identifier() {
  printf '%s' "$1" | sed 's/`/``/g'
}

sudo_mariadb() {
  command -v mariadb >/dev/null 2>&1 || die 'mariadb client is required'
  command -v sudo >/dev/null 2>&1 || die 'sudo is required for local MariaDB administration'
  sudo -v
  sudo mariadb "$@"
}

create_database() {
  local db_name="$1" db_password="$2" ident user pass
  [[ "$db_name" =~ ^[A-Za-z0-9_]+$ ]] || die "unsafe database name: $db_name"
  ident="$(sql_identifier "$db_name")"
  user="$(sql_quote "$db_name")"
  pass="$(sql_quote "$db_password")"
  sudo_mariadb <<SQL
CREATE DATABASE \`$ident\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER '$user'@'localhost' IDENTIFIED BY '$pass';
GRANT ALL PRIVILEGES ON \`$ident\`.* TO '$user'@'localhost';
FLUSH PRIVILEGES;
SQL
}

drop_database_for_site() {
  local site="$1" db_name ident user
  db_name="$(config_value "$site" db_name 2>/dev/null || true)"
  if [[ -z "$db_name" || ! "$db_name" =~ ^[A-Za-z0-9_]+$ ]]; then
    die "refusing to drop database for $site; safe db_name was not found"
  fi
  ident="$(sql_identifier "$db_name")"
  user="$(sql_quote "$db_name")"
  sudo_mariadb <<SQL
DROP DATABASE IF EXISTS \`$ident\`;
DROP USER IF EXISTS '$user'@'localhost';
FLUSH PRIVILEGES;
SQL
}

archive_site_folder() {
  local site="$1" source="$BENCH_DIR/sites/$site" archive_root="$BENCH_DIR/archived_sites" destination
  [[ -d "$source" ]] || return 0
  mkdir -p "$archive_root"
  destination="$archive_root/${site}.reset-$(date -u '+%Y%m%dT%H%M%SZ')"
  mv "$source" "$destination"
  info "old site folder archived outside active sites: $destination"
}

remove_site() {
  local site="$1"
  [[ -f "$BENCH_DIR/sites/$site/site_config.json" ]] || return 0
  info "removing local site: $site"
  drop_database_for_site "$site"
  archive_site_folder "$site"
  rm -f "$SECRETS_DIR/$site.env" 2>/dev/null || true
}

apply_local_login_passwords() {
  local user_list
  bench_run --site "$SITE" set-admin-password "$LOCAL_ADMIN_PASSWORD"
  user_list="$(bench_run --site "$SITE" execute frappe.get_all --args '["User"]' --kwargs '{"filters":{"enabled":1},"pluck":"name"}' | tail -n 1)"
  printf '%s' "$user_list" | "$BENCH_DIR/env/bin/python" -c 'import ast,json,sys
raw=sys.stdin.read().strip()
try:
    users=json.loads(raw)
except Exception:
    users=ast.literal_eval(raw)
for user in users:
    if user not in {"Administrator","Guest"}:
        print(user)' | while IFS= read -r user; do
    [[ -n "$user" ]] || continue
    bench_run --site "$SITE" set-password "$user" "$LOCAL_USER_PASSWORD"
  done
  ok 'local login password convention applied'
}

install_standard_stack() {
  ensure_erpnext_bench
  sync_ledgix_exact
  start_redis

  if ! bench_run --site "$SITE" list-apps | awk '{print $1}' | grep -Fxq erpnext; then
    BENCH_DIR="$BENCH_DIR" bash "$ROOT_DIR/deploy/ensure_erpnext.sh" --site "$SITE"
  fi
  if ! bench_run --site "$SITE" list-apps | awk '{print $1}' | grep -Fxq ledgix_saas; then
    bench_run --site "$SITE" install-app ledgix_saas
  fi
  bench_run --site "$SITE" set-config developer_mode 1
  bench_run --site "$SITE" migrate
  bench_run build --app ledgix_saas
  bench_run use "$SITE"
}

create_standard_site() {
  validate_runtime
  [[ ! -e "$BENCH_DIR/sites/$SITE" ]] || die "site already exists: $SITE"
  ensure_erpnext_bench
  sync_ledgix_exact

  local admin_password db_password db_name
  admin_password="${FRAPPE_ADMIN_PASSWORD:-$LOCAL_ADMIN_PASSWORD}"
  db_password="$LOCAL_DB_PASSWORD"
  db_name="_ledgix_$(random_hex 6)"

  printf '\n===== CREATE STANDARD LEDGIX LOCAL SITE =====\n'
  info "site: $SITE"
  info 'stack: Frappe -> ERPNext -> ledgix_saas'
  create_database "$db_name" "$db_password"
  if ! bench_run new-site "$SITE" \
    --admin-password "$admin_password" \
    --db-name "$db_name" \
    --db-password "$db_password" \
    --no-setup-db; then
    warn 'site creation failed; dropping newly prepared database'
    sudo_mariadb -e "DROP DATABASE IF EXISTS \`$(sql_identifier "$db_name")\`; DROP USER IF EXISTS '$(sql_quote "$db_name")'@'localhost'; FLUSH PRIVILEGES;" || true
    exit 1
  fi

  install_standard_stack
  apply_local_login_passwords
  save_credentials "$LOCAL_ADMIN_PASSWORD" "$db_name" "$db_password"
  ok "standard local site ready: $SITE"
}

ensure_site() {
  validate_runtime
  local count db_name db_password
  count="$(site_count)"
  if [[ "$count" -gt 1 ]]; then
    die "multiple active local sites found. Run: ./site_setup.sh --reset --site $SITE --confirm \"RESET $SITE\""
  fi
  if [[ ! -f "$BENCH_DIR/sites/$SITE/site_config.json" ]]; then
    if [[ "$count" -eq 1 ]]; then
      die "a different active local site exists. Use --reset to standardize to $SITE"
    fi
    create_standard_site
    return
  fi

  printf '\n===== REPAIR STANDARD LEDGIX LOCAL SITE =====\n'
  install_standard_stack
  apply_local_login_passwords
  db_name="$(config_value "$SITE" db_name)"
  db_password="$(config_value "$SITE" db_password)"
  save_credentials "$LOCAL_ADMIN_PASSWORD" "$db_name" "$db_password"
  ok "canonical local site is ready: $SITE"
}

reset_site() {
  validate_runtime
  [[ "$CONFIRM" == "RESET $SITE" ]] || die "destructive reset requires: --confirm \"RESET $SITE\""
  printf '\n===== RESET ALL ACTIVE LOCAL SITES =====\n'
  local active
  while IFS= read -r active; do
    [[ -n "$active" ]] || continue
    case "$active" in
      *.local|*.localhost) remove_site "$active" ;;
      *) die "refusing to remove non-local site from local reset: $active" ;;
    esac
  done < <(site_names)
  create_standard_site
  [[ "$(site_count)" -eq 1 ]] || die 'reset completed but active site count is not exactly one'
  [[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || die 'canonical site missing after reset'
  ok "single-site local standard enforced: $SITE"
}

show_status() {
  validate_runtime
  printf 'Canonical local site: %s\n' "$SITE"
  printf 'Active site count: %s\n' "$(site_count)"
  printf 'Active sites:\n'
  site_names | sed 's/^/  - /'
  if [[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]]; then
    printf '\nInstalled apps on %s:\n' "$SITE"
    bench_run --site "$SITE" list-apps
  fi
}

menu() {
  while true; do
    printf '\n========================================\n'
    printf ' Ledgix Local Site Manager\n'
    printf ' Canonical site: %s\n' "$SITE"
    printf ' Standard stack: Frappe -> ERPNext -> Ledgix\n'
    printf '========================================\n'
    printf '1) Ensure / repair standard site\n'
    printf '2) RESET all local sites -> one clean standard site\n'
    printf '3) Status\n'
    printf '4) Exit\n'
    read -r -p 'Choose: ' choice
    case "${choice:-}" in
      1) ensure_site ;;
      2)
        read -r -p "Type RESET $SITE to continue: " CONFIRM
        reset_site
        ;;
      3) show_status ;;
      4) exit 0 ;;
      *) warn 'invalid option' ;;
    esac
  done
}

case "$ACTION" in
  ensure) ensure_site ;;
  reset) reset_site ;;
  status) show_status ;;
  menu) menu ;;
  *) die "unknown action: $ACTION" ;;
esac
