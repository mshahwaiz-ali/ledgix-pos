#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SITE="${PRODUCTION_SITE:-}"
BENCH_DIR_INPUT="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
FROM_RELEASE="${BACKUP_FROM_RELEASE:-}"
TO_RELEASE="${BACKUP_TO_RELEASE:-}"
OFF_HOST_DIR="${LEDGIX_BACKUP_COPY_DIR:-}"
BACKUP_OPERATOR="${LEDGIX_BACKUP_OPERATOR:-${USER:-unknown}}"
ROLLBACK_OWNER="${LEDGIX_ROLLBACK_OWNER:-${USER:-unknown}}"
SITE_URL="${PRODUCTION_URL:-}"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: deploy/backup_safe.sh --site SITE [options]

Creates and verifies a Frappe database + public files + private files + site
configuration recovery set. Required backup files are checksummed and the
result is recorded in private rollback metadata.

Options:
  --site SITE             Frappe site name (required unless PRODUCTION_SITE is set)
  --bench-dir PATH        Bench path (default: ./frappe-bench)
  --from-release SHA      Current/rollback release identity for metadata
  --to-release SHA        Intended target release identity for metadata
  --url URL               Site/domain evidence for metadata
  --operator NAME         Operator evidence (default: current OS user)
  --rollback-owner NAME   Rollback owner evidence (default: current OS user)
  --copy-to DIR           Optional absolute off-host/mounted backup directory
  --help, -h              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) [[ $# -ge 2 ]] || die '--site requires a value'; SITE="$2"; shift 2 ;;
    --bench-dir) [[ $# -ge 2 ]] || die '--bench-dir requires a value'; BENCH_DIR_INPUT="$2"; shift 2 ;;
    --from-release) [[ $# -ge 2 ]] || die '--from-release requires a value'; FROM_RELEASE="$2"; shift 2 ;;
    --to-release) [[ $# -ge 2 ]] || die '--to-release requires a value'; TO_RELEASE="$2"; shift 2 ;;
    --url) [[ $# -ge 2 ]] || die '--url requires a value'; SITE_URL="$2"; shift 2 ;;
    --operator) [[ $# -ge 2 ]] || die '--operator requires a value'; BACKUP_OPERATOR="$2"; shift 2 ;;
    --rollback-owner) [[ $# -ge 2 ]] || die '--rollback-owner requires a value'; ROLLBACK_OWNER="$2"; shift 2 ;;
    --copy-to) [[ $# -ge 2 ]] || die '--copy-to requires a value'; OFF_HOST_DIR="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

case "$BENCH_DIR_INPUT" in
  /*) BENCH_DIR="$BENCH_DIR_INPUT" ;;
  ./*) BENCH_DIR="$REPO_ROOT/${BENCH_DIR_INPUT#./}" ;;
  *) BENCH_DIR="$REPO_ROOT/$BENCH_DIR_INPUT" ;;
esac

[[ -n "$SITE" ]] || die '--site (or PRODUCTION_SITE) is required'
[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $SITE"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || die "site not found: $SITE"
[[ -d "$BENCH_DIR/sites/$SITE/private" ]] || die "site private directory missing: $SITE"
[[ -z "$OFF_HOST_DIR" || "$OFF_HOST_DIR" == /* ]] || die '--copy-to must be an absolute path'
command -v sha256sum >/dev/null 2>&1 || die 'sha256sum is required'
command -v stat >/dev/null 2>&1 || die 'stat is required'

if [[ -x "$BENCH_DIR/env/bin/bench" ]]; then
  BENCH="$BENCH_DIR/env/bin/bench"
elif command -v bench >/dev/null 2>&1; then
  BENCH="$(command -v bench)"
else
  die 'bench is not available'
fi

bench_run() {
  (cd "$BENCH_DIR" && "$BENCH" "$@")
}

BACKUP_DIR="$BENCH_DIR/sites/$SITE/private/backups"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
PREFIX="ledgix-${SITE//./_}-$STAMP"
DATABASE_FILE="$BACKUP_DIR/${PREFIX}-database.sql.gz"
PUBLIC_FILES_FILE="$BACKUP_DIR/${PREFIX}-files.tar"
PRIVATE_FILES_FILE="$BACKUP_DIR/${PREFIX}-private-files.tar"
SITE_CONFIG_FILE="$BACKUP_DIR/${PREFIX}-site_config_backup.json"
MANIFEST="$BACKUP_DIR/${PREFIX}.sha256"
METADATA="$BACKUP_DIR/ledgix-backup-${SITE//./_}-$STAMP.env"

printf '\n===== VERIFIED BACKUP %s =====\n' "$SITE"
bench_run --site "$SITE" backup --with-files \
  --backup-path-db "$DATABASE_FILE" \
  --backup-path-files "$PUBLIC_FILES_FILE" \
  --backup-path-private-files "$PRIVATE_FILES_FILE" \
  --backup-path-conf "$SITE_CONFIG_FILE"

for required in "$DATABASE_FILE" "$PUBLIC_FILES_FILE" "$PRIVATE_FILES_FILE" "$SITE_CONFIG_FILE"; do
  [[ -s "$required" ]] || die "required backup artifact is missing or empty: $required"
done
chmod 600 "$SITE_CONFIG_FILE" 2>/dev/null || true

(
  cd "$BACKUP_DIR"
  sha256sum \
    "$(basename "$DATABASE_FILE")" \
    "$(basename "$PUBLIC_FILES_FILE")" \
    "$(basename "$PRIVATE_FILES_FILE")" \
    "$(basename "$SITE_CONFIG_FILE")" >"$(basename "$MANIFEST")"
)
chmod 600 "$MANIFEST"
(
  cd "$BACKUP_DIR"
  sha256sum -c "$(basename "$MANIFEST")"
)

REPO_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
FROM_RELEASE="${FROM_RELEASE:-$REPO_SHA}"
TO_RELEASE="${TO_RELEASE:-$FROM_RELEASE}"
TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
APPS="$(bench_run --site "$SITE" list-apps)"
FRAPPE_VERSION="$(printf '%s\n' "$APPS" | awk '$1=="frappe" {print $2; exit}')"
ERPNEXT_VERSION="$(printf '%s\n' "$APPS" | awk '$1=="erpnext" {print $2; exit}')"
LEDGIX_VERSION="$(printf '%s\n' "$APPS" | awk '$1=="ledgix_saas" {print $2; exit}')"
[[ -n "$FRAPPE_VERSION" ]] || die 'could not record Frappe version'
[[ -n "$ERPNEXT_VERSION" ]] || die 'could not record ERPNext version'
[[ -n "$LEDGIX_VERSION" ]] || die 'could not record Ledgix version'

OFF_HOST_COPY=""
if [[ -n "$OFF_HOST_DIR" ]]; then
  OFF_HOST_COPY="$OFF_HOST_DIR/$SITE/$STAMP"
fi

{
  printf 'site=%q\n' "$SITE"
  printf 'site_url=%q\n' "$SITE_URL"
  printf 'created_at_utc=%q\n' "$TIMESTAMP"
  printf 'operator=%q\n' "$BACKUP_OPERATOR"
  printf 'rollback_owner=%q\n' "$ROLLBACK_OWNER"
  printf 'repo_sha=%q\n' "$REPO_SHA"
  printf 'from_release=%q\n' "$FROM_RELEASE"
  printf 'to_release=%q\n' "$TO_RELEASE"
  printf 'frappe_version=%q\n' "$FRAPPE_VERSION"
  printf 'erpnext_version=%q\n' "$ERPNEXT_VERSION"
  printf 'ledgix_version=%q\n' "$LEDGIX_VERSION"
  printf 'backup_dir=%q\n' "$BACKUP_DIR"
  printf 'database_file=%q\n' "$DATABASE_FILE"
  printf 'public_files_file=%q\n' "$PUBLIC_FILES_FILE"
  printf 'private_files_file=%q\n' "$PRIVATE_FILES_FILE"
  printf 'site_config_file=%q\n' "$SITE_CONFIG_FILE"
  printf 'sha256_manifest=%q\n' "$MANIFEST"
  printf 'off_host_copy_dir=%q\n' "$OFF_HOST_COPY"
  printf 'verified_database=1\n'
  printf 'verified_public_files=1\n'
  printf 'verified_private_files=1\n'
  printf 'verified_site_config=1\n'
  printf 'verified_checksums=1\n'
} >"$METADATA"
chmod 600 "$METADATA"

if [[ -n "$OFF_HOST_COPY" ]]; then
  mkdir -p "$OFF_HOST_COPY"
  chmod 700 "$OFF_HOST_COPY" 2>/dev/null || true
  cp -p "$DATABASE_FILE" "$PUBLIC_FILES_FILE" "$PRIVATE_FILES_FILE" "$SITE_CONFIG_FILE" "$MANIFEST" "$METADATA" "$OFF_HOST_COPY/"
  (
    cd "$OFF_HOST_COPY"
    sha256sum -c "$(basename "$MANIFEST")"
  )
  ok "verified secondary backup copy: $OFF_HOST_COPY"
fi

printf '\n===== BACKUP EVIDENCE =====\n'
printf '  database:      %s (%s bytes)\n' "$DATABASE_FILE" "$(stat -c '%s' "$DATABASE_FILE")"
printf '  public files:  %s (%s bytes)\n' "$PUBLIC_FILES_FILE" "$(stat -c '%s' "$PUBLIC_FILES_FILE")"
printf '  private files: %s (%s bytes)\n' "$PRIVATE_FILES_FILE" "$(stat -c '%s' "$PRIVATE_FILES_FILE")"
printf '  site config:   %s (%s bytes)\n' "$SITE_CONFIG_FILE" "$(stat -c '%s' "$SITE_CONFIG_FILE")"
printf '  manifest:      %s\n' "$MANIFEST"

ok "verified backup complete: $SITE"
ok "rollback metadata: $METADATA"
if [[ -z "$OFF_HOST_COPY" ]]; then
  info 'No secondary copy was requested. Production policy should place this verified set on protected off-host/off-server storage.'
fi
