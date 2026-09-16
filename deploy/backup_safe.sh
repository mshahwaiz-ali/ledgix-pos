#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SITE="${PRODUCTION_SITE:-}"
BENCH_DIR_INPUT="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
FROM_RELEASE="${BACKUP_FROM_RELEASE:-}"
TO_RELEASE="${BACKUP_TO_RELEASE:-}"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: deploy/backup_safe.sh --site SITE [options]

Creates and verifies a Frappe database + public files + private files backup.
The site is always explicit; there is no production-site fallback.

Options:
  --site SITE             Frappe site name (required unless PRODUCTION_SITE is set)
  --bench-dir PATH        Bench path (default: ./frappe-bench)
  --from-release SHA      Current/rollback release identity for metadata
  --to-release SHA        Intended target release identity for metadata
  --help, -h              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) [[ $# -ge 2 ]] || die '--site requires a value'; SITE="$2"; shift 2 ;;
    --bench-dir) [[ $# -ge 2 ]] || die '--bench-dir requires a value'; BENCH_DIR_INPUT="$2"; shift 2 ;;
    --from-release) [[ $# -ge 2 ]] || die '--from-release requires a value'; FROM_RELEASE="$2"; shift 2 ;;
    --to-release) [[ $# -ge 2 ]] || die '--to-release requires a value'; TO_RELEASE="$2"; shift 2 ;;
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

if [[ -x "$BENCH_DIR/env/bin/bench" ]]; then
  BENCH="$BENCH_DIR/env/bin/bench"
elif command -v bench >/dev/null 2>&1; then
  BENCH="$(command -v bench)"
else
  die 'bench is not available'
fi

BACKUP_DIR="$BENCH_DIR/sites/$SITE/private/backups"
mkdir -p "$BACKUP_DIR"
MARKER="$BACKUP_DIR/.ledgix-backup-marker.$$"
touch "$MARKER"
trap 'rm -f "$MARKER"' EXIT

printf '\n===== VERIFIED BACKUP %s =====\n' "$SITE"
(
  cd "$BENCH_DIR"
  "$BENCH" --site "$SITE" backup --with-files
)

mapfile -t NEW_FILES < <(
  find "$BACKUP_DIR" -maxdepth 1 -type f -newer "$MARKER" ! -name "$(basename "$MARKER")" -printf '%f\n' | sort
)
[[ "${#NEW_FILES[@]}" -gt 0 ]] || die 'backup command completed but no new backup files were detected'

has_database=0
has_public_files=0
has_private_files=0
for file in "${NEW_FILES[@]}"; do
  case "$file" in
    *database*.sql|*database*.sql.gz|*.sql|*.sql.gz) has_database=1 ;;
  esac
  case "$file" in
    *private-files*) has_private_files=1 ;;
    *files*) has_public_files=1 ;;
  esac
done

[[ "$has_database" -eq 1 ]] || die 'verified backup is missing a database archive'
[[ "$has_public_files" -eq 1 ]] || die 'verified backup is missing a public files archive'
[[ "$has_private_files" -eq 1 ]] || die 'verified backup is missing a private files archive'

printf '\n===== NEW BACKUP FILES =====\n'
printf '  %s\n' "${NEW_FILES[@]}"

TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
REPO_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true)"
METADATA="$BACKUP_DIR/ledgix-backup-${SITE//./_}-$(date -u '+%Y%m%dT%H%M%SZ').env"
{
  printf 'site=%q\n' "$SITE"
  printf 'created_at_utc=%q\n' "$TIMESTAMP"
  printf 'repo_sha=%q\n' "$REPO_SHA"
  printf 'from_release=%q\n' "$FROM_RELEASE"
  printf 'to_release=%q\n' "$TO_RELEASE"
  printf 'backup_dir=%q\n' "$BACKUP_DIR"
  printf 'verified_database=1\n'
  printf 'verified_public_files=1\n'
  printf 'verified_private_files=1\n'
  printf 'backup_files=%q\n' "${NEW_FILES[*]}"
} >"$METADATA"
chmod 600 "$METADATA"

ok "verified backup complete: $SITE"
ok "rollback metadata: $METADATA"
info 'Copy the verified backup set off-host/off-server according to the production backup policy.'
