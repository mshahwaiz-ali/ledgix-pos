#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_SITE=""
TARGET_SITE=""
METADATA=""
BENCH_DIR_INPUT="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
CONFIRM=""
TARGET_URL=""
RUN_MIGRATE=0
MAINTENANCE_ENABLED=0

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: deploy/restore_drill.sh --source-site SITE --target-site SITE --metadata FILE --confirm PHRASE [options]

Destructively restores a verified backup onto an explicitly marked non-production
recovery site. The source site is never modified.

Required confirmation phrase:
  RESTORE <source-site> TO <target-site>

The target must contain:
  sites/<target-site>/private/.ledgix-non-production-recovery-target
with exactly:
  NON_PRODUCTION_RECOVERY_TARGET=<target-site>

Options:
  --bench-dir PATH    Bench path (default: ./frappe-bench)
  --url URL           Optional recovery-site URL for online smoke checks
  --migrate           Run bench migrate after restore; default is no migration
  --help, -h          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-site) [[ $# -ge 2 ]] || die '--source-site requires a value'; SOURCE_SITE="$2"; shift 2 ;;
    --target-site) [[ $# -ge 2 ]] || die '--target-site requires a value'; TARGET_SITE="$2"; shift 2 ;;
    --metadata) [[ $# -ge 2 ]] || die '--metadata requires a value'; METADATA="$2"; shift 2 ;;
    --confirm) [[ $# -ge 2 ]] || die '--confirm requires a value'; CONFIRM="$2"; shift 2 ;;
    --bench-dir) [[ $# -ge 2 ]] || die '--bench-dir requires a value'; BENCH_DIR_INPUT="$2"; shift 2 ;;
    --url) [[ $# -ge 2 ]] || die '--url requires a value'; TARGET_URL="${2%/}"; shift 2 ;;
    --migrate) RUN_MIGRATE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

case "$BENCH_DIR_INPUT" in
  /*) BENCH_DIR="$BENCH_DIR_INPUT" ;;
  ./*) BENCH_DIR="$REPO_ROOT/${BENCH_DIR_INPUT#./}" ;;
  *) BENCH_DIR="$REPO_ROOT/$BENCH_DIR_INPUT" ;;
esac

[[ -n "$SOURCE_SITE" ]] || die '--source-site is required'
[[ -n "$TARGET_SITE" ]] || die '--target-site is required'
[[ -n "$METADATA" ]] || die '--metadata is required'
[[ "$SOURCE_SITE" != "$TARGET_SITE" ]] || die 'recovery target must be different from the source site'
[[ "$SOURCE_SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid source site: $SOURCE_SITE"
[[ "$TARGET_SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid target site: $TARGET_SITE"
[[ -z "$TARGET_URL" || "$TARGET_URL" =~ ^https?://[^[:space:]]+$ ]] || die "invalid --url: $TARGET_URL"
[[ "$CONFIRM" == "RESTORE $SOURCE_SITE TO $TARGET_SITE" ]] || die 'explicit recovery confirmation phrase does not match'
[[ -f "$BENCH_DIR/sites/$SOURCE_SITE/site_config.json" ]] || die "source site not found: $SOURCE_SITE"
[[ -f "$BENCH_DIR/sites/$TARGET_SITE/site_config.json" ]] || die "recovery target site not found: $TARGET_SITE"
[[ -f "$METADATA" ]] || die "backup metadata not found: $METADATA"

MARKER="$BENCH_DIR/sites/$TARGET_SITE/private/.ledgix-non-production-recovery-target"
EXPECTED_MARKER="NON_PRODUCTION_RECOVERY_TARGET=$TARGET_SITE"
[[ -f "$MARKER" ]] || die "target is not marked as non-production recovery: $MARKER"
[[ "$(cat "$MARKER")" == "$EXPECTED_MARKER" ]] || die 'recovery target marker content is invalid'

if [[ -x "$BENCH_DIR/env/bin/bench" ]]; then
  BENCH="$BENCH_DIR/env/bin/bench"
elif command -v bench >/dev/null 2>&1; then
  BENCH="$(command -v bench)"
else
  die 'bench is not available'
fi
PYTHON_BIN="$BENCH_DIR/env/bin/python"
[[ -x "$PYTHON_BIN" ]] || die "bench Python not found: $PYTHON_BIN"

bench_run() {
  (cd "$BENCH_DIR" && "$BENCH" "$@")
}

cleanup() {
  if [[ "$MAINTENANCE_ENABLED" -eq 1 ]]; then
    warn "restore drill exited before success; maintenance mode remains ON for $TARGET_SITE"
  fi
}
trap cleanup EXIT

printf '\n===== VERIFY SOURCE BACKUP =====\n'
bash "$SCRIPT_DIR/verify_backup_set.sh" --metadata "$METADATA" --site "$SOURCE_SITE"

# shellcheck disable=SC1090
source "$METADATA"
CURRENT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
RESTORE_RELEASE="${from_release:-${repo_sha:-}}"
[[ "$RESTORE_RELEASE" =~ ^[0-9a-f]{40}$ ]] || die 'backup metadata does not contain a full source release SHA'
[[ "$CURRENT_SHA" == "$RESTORE_RELEASE" ]] || die "recovery bench code mismatch: backup requires $RESTORE_RELEASE, current repo is $CURRENT_SHA"

printf '\n===== RECOVERY TARGET SAFETY BACKUP =====\n'
TARGET_BACKUP_BEFORE="$(find "$BENCH_DIR/sites/$TARGET_SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
bash "$SCRIPT_DIR/backup_safe.sh" \
  --site "$TARGET_SITE" \
  --bench-dir "$BENCH_DIR" \
  --from-release "$CURRENT_SHA" \
  --to-release "$CURRENT_SHA" \
  --operator "recovery-drill"
TARGET_BACKUP_AFTER="$(find "$BENCH_DIR/sites/$TARGET_SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
[[ -n "$TARGET_BACKUP_AFTER" && "$TARGET_BACKUP_AFTER" != "$TARGET_BACKUP_BEFORE" ]] || die 'could not identify recovery-target safety backup metadata'

TARGET_CONFIG="$BENCH_DIR/sites/$TARGET_SITE/site_config.json"
TARGET_DB_IDENTITY_BEFORE="$($PYTHON_BIN - "$TARGET_CONFIG" <<'PY'
import hashlib, json, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
keys = ("db_name", "db_password", "db_host", "db_port", "db_type")
payload = json.dumps({key: data.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(payload.encode()).hexdigest())
PY
)"

printf '\n===== RECOVERY TARGET MAINTENANCE =====\n'
bench_run --site "$TARGET_SITE" set-maintenance-mode on
MAINTENANCE_ENABLED=1

printf '\n===== MERGE SOURCE ENCRYPTION KEY SAFELY =====\n'
"$PYTHON_BIN" - "$site_config_file" "$TARGET_CONFIG" <<'PY'
import json
import os
import pathlib
import sys
import tempfile

source_path = pathlib.Path(sys.argv[1])
target_path = pathlib.Path(sys.argv[2])
source = json.loads(source_path.read_text(encoding="utf-8"))
target = json.loads(target_path.read_text(encoding="utf-8"))
key = source.get("encryption_key")
if key:
    target["encryption_key"] = key
fd, tmp_name = tempfile.mkstemp(prefix=".ledgix-site-config-", dir=str(target_path.parent), text=True)
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
ok 'source encryption key merged without copying source database credentials'

TARGET_DB_IDENTITY_AFTER_KEY="$($PYTHON_BIN - "$TARGET_CONFIG" <<'PY'
import hashlib, json, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
keys = ("db_name", "db_password", "db_host", "db_port", "db_type")
payload = json.dumps({key: data.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(payload.encode()).hexdigest())
PY
)"
[[ "$TARGET_DB_IDENTITY_AFTER_KEY" == "$TARGET_DB_IDENTITY_BEFORE" ]] || die 'target database identity changed while merging recovery encryption key'

printf '\n===== RESTORE DATABASE AND FILES =====\n'
bench_run --site "$TARGET_SITE" restore "$database_file" \
  --with-public-files "$public_files_file" \
  --with-private-files "$private_files_file" \
  --force

TARGET_DB_IDENTITY_AFTER_RESTORE="$($PYTHON_BIN - "$TARGET_CONFIG" <<'PY'
import hashlib, json, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
keys = ("db_name", "db_password", "db_host", "db_port", "db_type")
payload = json.dumps({key: data.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(payload.encode()).hexdigest())
PY
)"
[[ "$TARGET_DB_IDENTITY_AFTER_RESTORE" == "$TARGET_DB_IDENTITY_BEFORE" ]] || die 'recovery target database identity changed during restore; refusing to continue'
ok 'recovery target DB identity was preserved; source DB credentials were not copied onto the target'

if [[ "$RUN_MIGRATE" -eq 1 ]]; then
  printf '\n===== EXPLICIT POST-RESTORE MIGRATION =====\n'
  bench_run --site "$TARGET_SITE" migrate
else
  info 'post-restore migrate skipped by default; matching release restore does not mutate schema unnecessarily'
fi
bench_run --site "$TARGET_SITE" clear-cache
bench_run --site "$TARGET_SITE" clear-website-cache

printf '\n===== RESTORED SITE DEPENDENCY PREFLIGHT =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$TARGET_SITE"

printf '\n===== RESTORED SITE OFFLINE SMOKE =====\n'
bash "$SCRIPT_DIR/smoke_test.sh" --site "$TARGET_SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== RESTORED DATA / PHASE 12 VERIFICATION =====\n'
bench_run --site "$TARGET_SITE" execute ledgix_saas.setup.recovery.verify_recovery_state

ONLINE_SMOKE="not_run"
if [[ -n "$TARGET_URL" ]]; then
  printf '\n===== OPTIONAL RECOVERY ONLINE SMOKE =====\n'
  bash "$SCRIPT_DIR/smoke_test.sh" --site "$TARGET_SITE" --bench-dir "$BENCH_DIR" --online --url "$TARGET_URL"
  ONLINE_SMOKE="passed"
fi

printf '\n===== RECOVERY EVIDENCE =====\n'
EVIDENCE_DIR="$BENCH_DIR/sites/$TARGET_SITE/private/ledgix-recovery"
mkdir -p "$EVIDENCE_DIR"
chmod 700 "$EVIDENCE_DIR" 2>/dev/null || true
EVIDENCE="$EVIDENCE_DIR/restore-drill-$(date -u '+%Y%m%dT%H%M%SZ').env"
{
  printf 'source_site=%q\n' "$SOURCE_SITE"
  printf 'target_site=%q\n' "$TARGET_SITE"
  printf 'verified_backup_metadata=%q\n' "$METADATA"
  printf 'target_safety_backup_metadata=%q\n' "$TARGET_BACKUP_AFTER"
  printf 'restored_release=%q\n' "$RESTORE_RELEASE"
  printf 'verified_at_utc=%q\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'target_db_identity_preserved=1\n'
  printf 'source_encryption_key_merged=1\n'
  printf 'dependency_preflight=passed\n'
  printf 'offline_smoke=passed\n'
  printf 'phase12_frozen_snapshot=passed\n'
  printf 'representative_reads=passed\n'
  printf 'online_smoke=%q\n' "$ONLINE_SMOKE"
  printf 'migrate_after_restore=%q\n' "$RUN_MIGRATE"
} >"$EVIDENCE"
chmod 600 "$EVIDENCE"

bench_run --site "$TARGET_SITE" set-maintenance-mode off
MAINTENANCE_ENABLED=0
trap - EXIT

ok "non-production restore drill passed: $SOURCE_SITE -> $TARGET_SITE"
ok "recovery evidence: $EVIDENCE"
printf 'restore_drill_complete=true\n'
