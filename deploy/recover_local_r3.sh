#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
STAGE_DIR=""
LOCAL_ADMIN_PASSWORD="${LEDGIX_LOCAL_ADMIN_PASSWORD:-admin}"
LOCAL_USER_PASSWORD="${LEDGIX_LOCAL_USER_PASSWORD:-admin@123}"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: deploy/recover_local_r3.sh [SITE] [--stage DIR]

Resume a local-only R3 recovery from a checksum-valid staged recovery set.
The helper never accepts production-style site names.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ $# -gt 0 && "${1:-}" != --* ]]; then
  SITE="$1"
  shift
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage) [[ $# -ge 2 ]] || fail '--stage requires a directory'; STAGE_DIR="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) fail "local recovery helper refuses non-local site: $SITE" ;;
esac
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "local site not found: $SITE"
[[ -x "$BENCH_DIR/env/bin/python" ]] || fail "bench Python missing: $BENCH_DIR/env/bin/python"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

if [[ -z "$STAGE_DIR" ]]; then
  STAGE_DIR="$(find "$BENCH_DIR/recovery-staging" -mindepth 1 -maxdepth 1 -type d -name "${SITE}-*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
fi
[[ -n "$STAGE_DIR" && -d "$STAGE_DIR" ]] || fail 'no staged local recovery set found'

one_file() {
  local pattern="$1" exclude="${2:-}" matches
  if [[ -n "$exclude" ]]; then
    matches="$(find "$STAGE_DIR" -maxdepth 1 -type f -name "$pattern" ! -name "$exclude" -print)"
  else
    matches="$(find "$STAGE_DIR" -maxdepth 1 -type f -name "$pattern" -print)"
  fi
  [[ "$(printf '%s\n' "$matches" | awk 'NF {count++} END {print count+0}')" -eq 1 ]] || fail "expected exactly one staged file matching $pattern"
  printf '%s\n' "$matches"
}

STAGED_DATABASE="$(one_file '*-database.sql.gz')"
STAGED_PUBLIC="$(one_file '*-files.tar' '*-private-files.tar')"
STAGED_PRIVATE="$(one_file '*-private-files.tar')"
STAGED_CONFIG="$(one_file '*-site_config_backup.json')"
STAGED_MANIFEST="$(one_file '*.sha256')"

printf '\n===== VERIFY STAGED RECOVERY SET =====\n'
(
  cd "$STAGE_DIR"
  sha256sum -c "$(basename "$STAGED_MANIFEST")"
)
ok "staged recovery set is checksum-valid: $STAGE_DIR"

printf '\n===== LOCAL DATABASE ADMIN =====\n'
bash "$REPO_ROOT/deploy/local_db_admin.sh"
DB_ADMIN_ENV="$REPO_ROOT/.secrets/local-db-admin.env"
[[ -f "$DB_ADMIN_ENV" ]] || fail "local DB admin credential file missing: $DB_ADMIN_ENV"
chmod 600 "$DB_ADMIN_ENV" 2>/dev/null || true
# shellcheck disable=SC1090
source "$DB_ADMIN_ENV"
[[ -n "${LOCAL_DB_ADMIN_USER:-}" && -n "${LOCAL_DB_ADMIN_PASSWORD:-}" ]] || fail 'local DB admin credentials are incomplete'

printf '\n===== MERGE SOURCE ENCRYPTION KEY =====\n'
TARGET_CONFIG="$BENCH_DIR/sites/$SITE/site_config.json"
"$BENCH_DIR/env/bin/python" - "$STAGED_CONFIG" "$TARGET_CONFIG" <<'PY'
import json, os, pathlib, sys, tempfile
source_path = pathlib.Path(sys.argv[1])
target_path = pathlib.Path(sys.argv[2])
source = json.loads(source_path.read_text(encoding="utf-8"))
target = json.loads(target_path.read_text(encoding="utf-8"))
key = source.get("encryption_key")
if key:
    target["encryption_key"] = key
fd, tmp_name = tempfile.mkstemp(prefix=".ledgix-local-resume-", dir=str(target_path.parent), text=True)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(target, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.chmod(tmp_name, 0o600)
    os.replace(tmp_name, target_path)
finally:
    if os.path.exists(tmp_name):
        os.unlink(tmp_name)
PY
ok 'source encryption key merged without replacing fresh DB credentials'

printf '\n===== RESTORE STAGED DATABASE AND FILES =====\n'
bench_run --site "$SITE" restore "$STAGED_DATABASE" \
  --with-public-files "$STAGED_PUBLIC" \
  --with-private-files "$STAGED_PRIVATE" \
  --db-root-username "$LOCAL_DB_ADMIN_USER" \
  --db-root-password "$LOCAL_DB_ADMIN_PASSWORD" \
  --admin-password "$LOCAL_ADMIN_PASSWORD" \
  --force

printf '\n===== LOCAL LOGIN PASSWORDS =====\n'
bench_run --site "$SITE" set-admin-password "$LOCAL_ADMIN_PASSWORD"
USER_LIST="$(bench_run --site "$SITE" execute frappe.get_all --args '["User"]' --kwargs '{"filters":{"enabled":1},"pluck":"name"}')"
printf '%s' "$USER_LIST" | "$BENCH_DIR/env/bin/python" -c 'import ast,json,sys
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

printf '\n===== RECOVERY VERIFICATION =====\n'
bench_run --site "$SITE" clear-cache
bench_run --site "$SITE" clear-website-cache
bench_run --site "$SITE" execute ledgix_saas.setup.recovery.verify_recovery_state
ok 'restored local site is readable and Phase 12 frozen snapshot matches'
printf 'local_r3_recovery_complete=true\n'
