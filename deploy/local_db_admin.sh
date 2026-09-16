#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SECRETS_DIR="$REPO_ROOT/.secrets"
ENV_FILE="$SECRETS_DIR/local-db-admin.env"
DB_ADMIN_USER="${LEDGIX_LOCAL_DB_ADMIN_USER:-ledgix_local_admin}"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

[[ "$DB_ADMIN_USER" =~ ^[A-Za-z0-9_]+$ ]] || fail 'unsafe local DB admin username'
command -v sudo >/dev/null 2>&1 || fail 'sudo is required for local MariaDB administration'
command -v mariadb >/dev/null 2>&1 || fail 'mariadb client is required'
command -v openssl >/dev/null 2>&1 || fail 'openssl is required'

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR" 2>/dev/null || true

DB_ADMIN_PASSWORD=""
if [[ -f "$ENV_FILE" ]]; then
  chmod 600 "$ENV_FILE" 2>/dev/null || true
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  DB_ADMIN_USER="${LOCAL_DB_ADMIN_USER:-$DB_ADMIN_USER}"
  DB_ADMIN_PASSWORD="${LOCAL_DB_ADMIN_PASSWORD:-}"
fi

if [[ -z "$DB_ADMIN_PASSWORD" ]]; then
  DB_ADMIN_PASSWORD="$(openssl rand -base64 36 | tr -d '\n' | cut -c 1-32)"
fi

sql_quote() {
  printf '%s' "$1" | sed "s/'/''/g"
}

user_sql="$(sql_quote "$DB_ADMIN_USER")"
pass_sql="$(sql_quote "$DB_ADMIN_PASSWORD")"

info 'ensuring dedicated localhost MariaDB administrator for Ledgix local development'
sudo -v
sudo mariadb <<SQL
CREATE USER IF NOT EXISTS '$user_sql'@'localhost' IDENTIFIED BY '$pass_sql';
ALTER USER '$user_sql'@'localhost' IDENTIFIED BY '$pass_sql';
GRANT ALL PRIVILEGES ON *.* TO '$user_sql'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
SQL

{
  printf 'LOCAL_DB_ADMIN_USER=%q\n' "$DB_ADMIN_USER"
  printf 'LOCAL_DB_ADMIN_PASSWORD=%q\n' "$DB_ADMIN_PASSWORD"
  printf 'CREATED_AT_UTC=%q\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} >"$ENV_FILE"
chmod 600 "$ENV_FILE"

ok "local DB admin credentials ready outside Git: $ENV_FILE"
