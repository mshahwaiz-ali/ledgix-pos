#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
CONFIRM=""
SITE_URL=""
APP="ledgix_saas"
TEMP_REDIS_STARTED=0

usage() {
  cat <<'EOF'
Usage: scripts/run_backup_restore_runtime_gate.sh [SITE] --confirm "RESET AND RESTORE SITE" [--url URL]

Runs the R3 destructive recovery proof in-place on the one canonical local
Ledgix site. It never runs on a production-style domain.

Flow:
  verified backup -> stage outside site -> reset same local site -> restore -> verify

The reset removes every active .local/.localhost site so local development ends
with exactly one canonical site.
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

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
pass() { printf '[PASS] %s\n' "$*"; }
info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }

cleanup() {
  if [[ "$TEMP_REDIS_STARTED" -eq 1 && -f "$REPO_ROOT/deploy/bench_redis.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" stop || true
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm) [[ $# -ge 2 ]] || fail '--confirm requires a value'; CONFIRM="$2"; shift 2 ;;
    --url) [[ $# -ge 2 ]] || fail '--url requires a value'; SITE_URL="${2%/}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) fail "R3 in-place runtime gate is local-only; refusing site: $SITE" ;;
esac
[[ "$CONFIRM" == "RESET AND RESTORE $SITE" ]] || fail "confirmation must be exactly: RESET AND RESTORE $SITE"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "canonical local site not found: $SITE"
[[ -x "$BENCH_DIR/env/bin/python" ]] || fail "bench Python missing: $BENCH_DIR/env/bin/python"
[[ -d "$REPO_ROOT/apps/$APP" ]] || fail "repository Ledgix source missing"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

printf '==================================================\n'
printf ' Ledgix R3 Single-Site Backup / Restore Gate\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf 'Mode: destructive local in-place recovery proof\n'

printf '\n===== STATIC R3 CONTRACT =====\n'
bash "$SCRIPT_DIR/run_backup_restore_static_gate.sh"

printf '\n===== SOURCE SITE CONTRACT =====\n'
SOURCE_APPS="$(bench_run --site "$SITE" list-apps)"
for required_app in frappe erpnext ledgix_saas; do
  if ! printf '%s\n' "$SOURCE_APPS" | awk '{print $1}' | grep -Fxq "$required_app"; then
    fail "source site is missing required app: $required_app"
  fi
  pass "source site has $required_app"
done

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.r3-single-sync.$$"
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$REPO_ROOT/deploy/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/repair_apps_txt.sh"
fi
[[ -f "$DEST_APP/setup/recovery.py" ]] || fail 'bench app is missing R3 recovery verifier after sync'
pass 'bench Ledgix code matches repository source'

printf '\n===== PRE-RESET PHASE 12 / READ PROOF =====\n'
bench_run --site "$SITE" execute ledgix_saas.setup.recovery.verify_recovery_state
pass 'source migrated state is readable and Phase 12 frozen snapshot matches'

printf '\n===== VERIFIED SOURCE RECOVERY POINT =====\n'
CURRENT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
BEFORE="$(find "$BENCH_DIR/sites/$SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
bash "$REPO_ROOT/deploy/backup_safe.sh" \
  --site "$SITE" \
  --bench-dir "$BENCH_DIR" \
  --from-release "$CURRENT_SHA" \
  --to-release "$CURRENT_SHA" \
  --operator "r3-single-site-runtime" \
  --rollback-owner "r3-single-site-runtime"
AFTER="$(find "$BENCH_DIR/sites/$SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
[[ -n "$AFTER" && "$AFTER" != "$BEFORE" ]] || fail 'could not identify newly-created source backup metadata'
bash "$REPO_ROOT/deploy/verify_backup_set.sh" --metadata "$AFTER" --site "$SITE"
pass "verified source backup metadata: $AFTER"

# shellcheck disable=SC1090
source "$AFTER"
[[ "${from_release:-}" == "$CURRENT_SHA" ]] || fail 'backup release does not match repository HEAD'
for required_path in "$database_file" "$public_files_file" "$private_files_file" "$site_config_file" "$sha256_manifest"; do
  [[ -f "$required_path" ]] || fail "backup artifact missing before staging: $required_path"
done

printf '\n===== STAGE RECOVERY SET OUTSIDE SITE =====\n'
STAGE_ROOT="$BENCH_DIR/recovery-staging"
STAGE_DIR="$STAGE_ROOT/${SITE}-$(date -u '+%Y%m%dT%H%M%SZ')"
mkdir -p "$STAGE_DIR"
chmod 700 "$STAGE_ROOT" "$STAGE_DIR" 2>/dev/null || true
cp -p "$database_file" "$public_files_file" "$private_files_file" "$site_config_file" "$sha256_manifest" "$AFTER" "$STAGE_DIR/"
STAGED_DATABASE="$STAGE_DIR/$(basename "$database_file")"
STAGED_PUBLIC="$STAGE_DIR/$(basename "$public_files_file")"
STAGED_PRIVATE="$STAGE_DIR/$(basename "$private_files_file")"
STAGED_CONFIG="$STAGE_DIR/$(basename "$site_config_file")"
STAGED_MANIFEST="$STAGE_DIR/$(basename "$sha256_manifest")"
(
  cd "$STAGE_DIR"
  sha256sum -c "$(basename "$STAGED_MANIFEST")"
)
pass "recovery set staged outside active site: $STAGE_DIR"

printf '\n===== DESTRUCTIVE SINGLE-SITE RESET =====\n'
warn "The local site $SITE is now intentionally wiped and recreated."
bash "$REPO_ROOT/site_setup.sh" \
  --reset \
  --site "$SITE" \
  --confirm "RESET $SITE"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail 'canonical site missing after reset'
ACTIVE_SITES="$(find "$BENCH_DIR/sites" -mindepth 1 -maxdepth 1 -type d ! -name assets ! -name archived ! -name archived_sites -exec test -f '{}/site_config.json' \; -printf '%f\n' 2>/dev/null | sort)"
[[ "$ACTIVE_SITES" == "$SITE" ]] || fail "local bench must contain exactly one active site after reset; found: ${ACTIVE_SITES//$'\n'/, }"
pass "single active local site enforced: $SITE"

printf '\n===== RECOVERY DB IDENTITY / ENCRYPTION KEY =====\n'
TARGET_CONFIG="$BENCH_DIR/sites/$SITE/site_config.json"
SECRET_FILE="$REPO_ROOT/.secrets/sites/$SITE.env"
[[ -f "$SECRET_FILE" ]] || fail "new local site credential file missing: $SECRET_FILE"
chmod 600 "$SECRET_FILE" 2>/dev/null || true
# shellcheck disable=SC1090
source "$SECRET_FILE"
[[ -n "${ADMIN_PASSWORD:-}" ]] || fail 'new local Administrator password is missing from secret file'

DB_IDENTITY_BEFORE="$($BENCH_DIR/env/bin/python - "$TARGET_CONFIG" <<'PY'
import hashlib, json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = ("db_name", "db_password", "db_host", "db_port", "db_type")
value = json.dumps({key: payload.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(value.encode()).hexdigest())
PY
)"

"$BENCH_DIR/env/bin/python" - "$STAGED_CONFIG" "$TARGET_CONFIG" <<'PY'
import json, os, pathlib, sys, tempfile
source_path = pathlib.Path(sys.argv[1])
target_path = pathlib.Path(sys.argv[2])
source = json.loads(source_path.read_text(encoding="utf-8"))
target = json.loads(target_path.read_text(encoding="utf-8"))
key = source.get("encryption_key")
if key:
    target["encryption_key"] = key
fd, tmp_name = tempfile.mkstemp(prefix=".ledgix-local-restore-", dir=str(target_path.parent), text=True)
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

DB_IDENTITY_AFTER_KEY="$($BENCH_DIR/env/bin/python - "$TARGET_CONFIG" <<'PY'
import hashlib, json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = ("db_name", "db_password", "db_host", "db_port", "db_type")
value = json.dumps({key: payload.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(value.encode()).hexdigest())
PY
)"
[[ "$DB_IDENTITY_AFTER_KEY" == "$DB_IDENTITY_BEFORE" ]] || fail 'fresh site DB identity changed while merging source encryption key'
pass 'source encryption key merged without copying old DB credentials'

printf '\n===== RESTORE STAGED DATABASE AND FILES =====\n'
bench_run --site "$SITE" restore "$STAGED_DATABASE" \
  --with-public-files "$STAGED_PUBLIC" \
  --with-private-files "$STAGED_PRIVATE" \
  --admin-password "$ADMIN_PASSWORD" \
  --force

DB_IDENTITY_AFTER_RESTORE="$($BENCH_DIR/env/bin/python - "$TARGET_CONFIG" <<'PY'
import hashlib, json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
keys = ("db_name", "db_password", "db_host", "db_port", "db_type")
value = json.dumps({key: payload.get(key) for key in keys}, sort_keys=True, separators=(",", ":"))
print(hashlib.sha256(value.encode()).hexdigest())
PY
)"
[[ "$DB_IDENTITY_AFTER_RESTORE" == "$DB_IDENTITY_BEFORE" ]] || fail 'fresh local site DB identity changed during restore'
pass 'fresh local DB identity remained isolated after restore'

printf '\n===== POST-RESTORE RUNTIME =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" start
TEMP_REDIS_STARTED=1
bench_run --site "$SITE" clear-cache
bench_run --site "$SITE" clear-website-cache
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"
bash "$REPO_ROOT/deploy/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== RESTORED DATA / PHASE 12 VERIFICATION =====\n'
bench_run --site "$SITE" execute ledgix_saas.setup.recovery.verify_recovery_state
pass 'representative ERPNext/Ledgix reads and Phase 12 frozen snapshot survived destructive recovery'

ONLINE_SMOKE="not_run"
if [[ -n "$SITE_URL" ]]; then
  printf '\n===== OPTIONAL ONLINE SMOKE =====\n'
  bash "$REPO_ROOT/deploy/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --online --url "$SITE_URL"
  ONLINE_SMOKE="passed"
fi

printf '\n===== RECOVERY EVIDENCE =====\n'
EVIDENCE_DIR="$BENCH_DIR/sites/$SITE/private/ledgix-recovery"
mkdir -p "$EVIDENCE_DIR"
chmod 700 "$EVIDENCE_DIR" 2>/dev/null || true
EVIDENCE="$EVIDENCE_DIR/single-site-restore-$(date -u '+%Y%m%dT%H%M%SZ').env"
{
  printf 'site=%q\n' "$SITE"
  printf 'release_sha=%q\n' "$CURRENT_SHA"
  printf 'staged_recovery_dir=%q\n' "$STAGE_DIR"
  printf 'verified_at_utc=%q\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'single_active_site=1\n'
  printf 'destructive_reset_completed=1\n'
  printf 'target_db_identity_preserved=1\n'
  printf 'source_encryption_key_merged=1\n'
  printf 'dependency_preflight=passed\n'
  printf 'offline_smoke=passed\n'
  printf 'phase12_frozen_snapshot=passed\n'
  printf 'representative_reads=passed\n'
  printf 'online_smoke=%q\n' "$ONLINE_SMOKE"
} >"$EVIDENCE"
chmod 600 "$EVIDENCE"

printf '\n===== R3 RUNTIME VERDICT =====\n'
pass 'verified recovery point created before destructive reset'
pass 'recovery set survived because it was staged outside the site directory'
pass 'all local sites were reduced to one canonical site'
pass 'canonical site was freshly recreated with Frappe -> ERPNext -> Ledgix'
pass 'database/public/private files restored to the same canonical site'
pass 'fresh DB credentials stayed isolated while source encryption key was restored'
pass 'Phase 12 frozen snapshot and representative reads passed after recovery'
printf 'backup_restore_runtime_complete=true\n'
printf '[OK] recovery evidence: %s\n' "$EVIDENCE"
printf '[OK] staged recovery set retained at: %s\n' "$STAGE_DIR"
