#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
APP="ledgix_saas"
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.r3-sync.$$"

usage() {
  cat <<'EOF'
Usage: scripts/run_backup_restore_runtime_gate.sh SOURCE_SITE TARGET_SITE --confirm "RESTORE SOURCE_SITE TO TARGET_SITE" [--url URL]

Runs the consolidated R3 non-production recovery proof. TARGET_SITE is
destructively overwritten and must be a disposable recovery site.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

SOURCE_SITE="${1:-}"
TARGET_SITE="${2:-}"
if [[ $# -ge 2 ]]; then
  shift 2
else
  shift "$#"
fi
CONFIRM=""
TARGET_URL=""

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
pass() { printf '[PASS] %s\n' "$*"; }

cleanup() {
  rm -rf "$TMP_APP" 2>/dev/null || true
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm) [[ $# -ge 2 ]] || fail '--confirm requires a value'; CONFIRM="$2"; shift 2 ;;
    --url) [[ $# -ge 2 ]] || fail '--url requires a value'; TARGET_URL="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ -n "$SOURCE_SITE" && -n "$TARGET_SITE" ]] || fail 'source and target sites are required'
[[ "$SOURCE_SITE" != "$TARGET_SITE" ]] || fail 'source and recovery target must be different sites'
[[ "$CONFIRM" == "RESTORE $SOURCE_SITE TO $TARGET_SITE" ]] || fail 'explicit restore confirmation phrase is required'
[[ -f "$BENCH_DIR/sites/$SOURCE_SITE/site_config.json" ]] || fail "source site not found: $SOURCE_SITE"
[[ -f "$BENCH_DIR/sites/$TARGET_SITE/site_config.json" ]] || fail "recovery target site not found: $TARGET_SITE"
[[ -d "$SRC_APP" ]] || fail "repository Ledgix app source not found: $SRC_APP"
[[ -x "$BENCH_DIR/env/bin/python" ]] || fail "bench Python not found: $BENCH_DIR/env/bin/python"

printf '==================================================\n'
printf ' Ledgix R3 Backup / Restore Runtime Gate\n'
printf '==================================================\n'
printf 'Source: %s\n' "$SOURCE_SITE"
printf 'Recovery target: %s\n' "$TARGET_SITE"
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== STATIC R3 CONTRACT =====\n'
bash "$SCRIPT_DIR/run_backup_restore_static_gate.sh"

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
# Repository main is the source of truth. The integration bench may still hold
# an older copied app from a previous gate, so make the bench app exactly mirror
# the current repository release before creating backup/restore evidence.
if [[ -e "$DEST_APP" && "$(readlink -f "$SRC_APP")" == "$(readlink -f "$DEST_APP")" ]]; then
  pass 'bench Ledgix app already resolves to repository source'
else
  rm -rf "$TMP_APP"
  cp -a "$SRC_APP" "$TMP_APP"
  rm -rf "$DEST_APP"
  mv "$TMP_APP" "$DEST_APP"
  pass 'bench Ledgix app replaced from exact repository source'
fi
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$REPO_ROOT/deploy/repair_apps_txt.sh" ]]; then
  bash "$REPO_ROOT/deploy/repair_apps_txt.sh"
fi
[[ -f "$DEST_APP/setup/recovery.py" ]] || fail 'bench app sync is missing the R3 recovery verifier'
pass "bench app synced to repository commit $(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== RECOVERY TARGET APP CONTRACT =====\n'
TARGET_APPS="$(cd "$BENCH_DIR" && bench --site "$TARGET_SITE" list-apps)"
for app in frappe erpnext ledgix_saas; do
  if ! printf '%s\n' "$TARGET_APPS" | grep -Eq "^${app}[[:space:]]"; then
    fail "recovery target is missing required app: $app"
  fi
  pass "recovery target has $app installed"
done

printf '\n===== MARK EXPLICIT NON-PRODUCTION TARGET =====\n'
MARKER="$BENCH_DIR/sites/$TARGET_SITE/private/.ledgix-non-production-recovery-target"
mkdir -p "$(dirname "$MARKER")"
printf 'NON_PRODUCTION_RECOVERY_TARGET=%s\n' "$TARGET_SITE" >"$MARKER"
chmod 600 "$MARKER"
pass "recovery target marker written: $MARKER"

printf '\n===== CREATE SOURCE RECOVERY POINT =====\n'
CURRENT_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
BEFORE="$(find "$BENCH_DIR/sites/$SOURCE_SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
bash "$REPO_ROOT/deploy/backup_safe.sh" \
  --site "$SOURCE_SITE" \
  --bench-dir "$BENCH_DIR" \
  --from-release "$CURRENT_SHA" \
  --to-release "$CURRENT_SHA" \
  --operator "r3-runtime-gate" \
  --rollback-owner "r3-runtime-gate"
AFTER="$(find "$BENCH_DIR/sites/$SOURCE_SITE/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
[[ -n "$AFTER" && "$AFTER" != "$BEFORE" ]] || fail 'could not identify newly-created source backup metadata'
pass "source backup metadata: $AFTER"

printf '\n===== NON-PRODUCTION RESTORE PROOF =====\n'
RESTORE_ARGS=(
  --source-site "$SOURCE_SITE"
  --target-site "$TARGET_SITE"
  --metadata "$AFTER"
  --bench-dir "$BENCH_DIR"
  --confirm "$CONFIRM"
)
if [[ -n "$TARGET_URL" ]]; then
  RESTORE_ARGS+=(--url "$TARGET_URL")
fi
bash "$REPO_ROOT/deploy/restore_drill.sh" "${RESTORE_ARGS[@]}"

printf '\n===== R3 RUNTIME VERDICT =====\n'
pass 'exact repository Ledgix code was synced to the recovery bench'
pass 'source recovery point is checksum-verified'
pass 'database/public/private/config recovery set is complete'
pass 'recovery target safety backup created before overwrite'
pass 'source backup restored to disposable non-production site'
pass 'target database identity remained isolated'
pass 'source encryption key was restored without source DB credentials'
pass 'dependency + offline smoke passed after restore'
pass 'representative ERPNext/Ledgix reads passed'
pass 'Phase 12 frozen snapshot survived restore'
if [[ -n "$TARGET_URL" ]]; then
  pass 'online recovery smoke passed'
fi
printf 'backup_restore_runtime_complete=true\n'
