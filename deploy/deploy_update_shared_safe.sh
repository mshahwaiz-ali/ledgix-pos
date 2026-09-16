#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR_INPUT="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
APP="${APP_NAME:-ledgix_saas}"
RELEASE=""
TMP_APP=""
TMP_CONTRACT=""
TARGET_SHA=""
PREVIOUS_SHA=""
MAINTENANCE_ARMED=0

declare -a APPROVED_SITES=()
declare -A SITE_URLS=()
declare -A BACKUP_METADATA=()

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
Usage:
  deploy/deploy_update_shared_safe.sh --release REF \
    --site SITE=URL --site SITE=URL [--site SITE=URL ...] [options]

Safely deploys one immutable Ledgix release to every Ledgix tenant on a shared
bench as one approved cohort. Every Ledgix-consuming site on the bench must be
listed explicitly. Partial shared-bench releases are refused.

Options:
  --release REF       Full 40-character commit SHA or immutable Git tag
  --site SITE=URL     Approved tenant and its public smoke-test URL; repeat
  --bench-dir PATH    Bench path (default: ./frappe-bench)
  --app APP           Custom app name (default: ledgix_saas)
  --help, -h          Show this help

Safety sequence:
  validate full cohort -> backup every site -> maintenance every site ->
  checkout/sync/build once -> migrate+preflight+offline smoke every site ->
  restart once -> maintenance off all -> online smoke every site -> evidence
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release)
      [[ $# -ge 2 ]] || die '--release requires a value'
      RELEASE="$2"
      shift 2
      ;;
    --site)
      [[ $# -ge 2 ]] || die '--site requires SITE=URL'
      spec="$2"
      [[ "$spec" == *=* ]] || die '--site must be SITE=URL'
      site="${spec%%=*}"
      url="${spec#*=}"
      [[ "$site" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || die "invalid site name: $site"
      [[ "$url" =~ ^https?://[^[:space:]]+$ ]] || die "invalid URL for $site: $url"
      [[ -z "${SITE_URLS[$site]+x}" ]] || die "duplicate approved site: $site"
      APPROVED_SITES+=("$site")
      SITE_URLS["$site"]="${url%/}"
      shift 2
      ;;
    --bench-dir)
      [[ $# -ge 2 ]] || die '--bench-dir requires a value'
      BENCH_DIR_INPUT="$2"
      shift 2
      ;;
    --app)
      [[ $# -ge 2 ]] || die '--app requires a value'
      APP="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
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
TMP_APP="$BENCH_DIR/apps/.${APP}.shared-deploy.$$"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

cleanup() {
  rm -rf "$TMP_APP" 2>/dev/null || true
  [[ -z "$TMP_CONTRACT" ]] || rm -f "$TMP_CONTRACT" 2>/dev/null || true
  if [[ "$MAINTENANCE_ARMED" -eq 1 ]]; then
    warn 'shared-bench release exited before success; maintenance mode remains ON for the approved cohort'
    warn "restore each tenant from its verified pre-update backup and application release $PREVIOUS_SHA"
  fi
}
trap cleanup EXIT

[[ -n "$RELEASE" ]] || die '--release is required'
[[ "${#APPROVED_SITES[@]}" -ge 2 ]] || die 'shared-bench release requires at least two explicitly approved sites'
[[ "$APP" =~ ^[A-Za-z0-9_]+$ ]] || die "invalid app name: $APP"
[[ -d "$REPO_ROOT/.git" ]] || die "repository not found: $REPO_ROOT"
[[ -d "$BENCH_DIR/apps/frappe" && -x "$BENCH_DIR/env/bin/python" ]] || die "invalid bench: $BENCH_DIR"
[[ -d "$SRC_APP" ]] || die "source app missing: $SRC_APP"
command -v bench >/dev/null 2>&1 || die 'bench is not available in PATH'
command -v sha256sum >/dev/null 2>&1 || die 'sha256sum is required'
sudo -n true >/dev/null 2>&1 || die 'passwordless sudo is required'
[[ -z "$(git -C "$REPO_ROOT" status --short)" ]] || die 'repository has local changes; commit or stash them before deployment'

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
  die 'release must be a full 40-character commit SHA or immutable tag'
fi
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || die "could not resolve immutable release: $RELEASE"
info "previous release: $PREVIOUS_SHA"
info "approved target SHA: $TARGET_SHA"

TMP_CONTRACT="$(mktemp)"
git -C "$REPO_ROOT" show "$TARGET_SHA:deploy/release_contract.env" >"$TMP_CONTRACT" \
  || die 'target release does not contain deploy/release_contract.env'
# shellcheck disable=SC1090
source "$TMP_CONTRACT"
[[ "${LEDGIX_APP:-}" == "$APP" ]] || die "release contract app mismatch: expected ${LEDGIX_APP:-missing}, deploying $APP"

printf '\n===== DISCOVER LEDGIX TENANT COHORT =====\n'
declare -a ACTUAL_LEDgIX_SITES=()
for config in "$BENCH_DIR"/sites/*/site_config.json; do
  [[ -f "$config" ]] || continue
  candidate="$(basename "$(dirname "$config")")"
  apps="$(bench_run --site "$candidate" list-apps 2>/dev/null || true)"
  if printf '%s\n' "$apps" | awk '{print $1}' | grep -Fxq "$APP"; then
    ACTUAL_LEDgIX_SITES+=("$candidate")
  fi
done
[[ "${#ACTUAL_LEDgIX_SITES[@]}" -ge 2 ]] || die 'bench does not contain at least two Ledgix tenant sites'

mapfile -t ACTUAL_SORTED < <(printf '%s\n' "${ACTUAL_LEDgIX_SITES[@]}" | sort -u)
mapfile -t APPROVED_SORTED < <(printf '%s\n' "${APPROVED_SITES[@]}" | sort -u)
[[ "$(printf '%s\n' "${ACTUAL_SORTED[@]}")" == "$(printf '%s\n' "${APPROVED_SORTED[@]}")" ]] \
  || die "approved cohort must exactly match every $APP tenant on this bench"
printf 'Approved shared-bench cohort:\n'
printf '  %s\n' "${APPROVED_SORTED[@]}"
COHORT_DIGEST="$(printf '%s\n' "${APPROVED_SORTED[@]}" | sha256sum | awk '{print $1}')"
ok "full Ledgix tenant cohort approved: $COHORT_DIGEST"

printf '\n===== PRE-MUTATION SITE CONTRACTS =====\n'
for site in "${APPROVED_SORTED[@]}"; do
  [[ -f "$BENCH_DIR/sites/$site/site_config.json" ]] || die "site not found: $site"
  apps="$(bench_run --site "$site" list-apps)"
  for required_app in frappe erpnext "$APP"; do
    printf '%s\n' "$apps" | awk '{print $1}' | grep -Fxq "$required_app" \
      || die "$site is missing required app: $required_app"
  done
  frappe_version="$(printf '%s\n' "$apps" | awk '$1=="frappe" {print $2; exit}')"
  erpnext_version="$(printf '%s\n' "$apps" | awk '$1=="erpnext" {print $2; exit}')"
  [[ "$frappe_version" == "${LEDGIX_EXPECTED_FRAPPE_VERSION:-}" ]] \
    || die "$site Frappe version mismatch: expected ${LEDGIX_EXPECTED_FRAPPE_VERSION:-unset}, found ${frappe_version:-missing}"
  [[ "$erpnext_version" == "${LEDGIX_EXPECTED_ERPNEXT_VERSION:-}" ]] \
    || die "$site ERPNext version mismatch: expected ${LEDGIX_EXPECTED_ERPNEXT_VERSION:-unset}, found ${erpnext_version:-missing}"
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$site"
  ok "$site pre-mutation contract passed"
done

printf '\n===== VERIFIED BACKUP FOR EVERY TENANT =====\n'
for site in "${APPROVED_SORTED[@]}"; do
  before="$(find "$BENCH_DIR/sites/$site/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
  bash "$SCRIPT_DIR/backup_safe.sh" \
    --site "$site" \
    --bench-dir "$BENCH_DIR" \
    --from-release "$PREVIOUS_SHA" \
    --to-release "$TARGET_SHA" \
    --operator "shared-bench-release" \
    --rollback-owner "shared-bench-release"
  after="$(find "$BENCH_DIR/sites/$site/private/backups" -maxdepth 1 -type f -name 'ledgix-backup-*.env' -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {$1=""; sub(/^ /,""); print; exit}')"
  [[ -n "$after" && "$after" != "$before" ]] || die "could not identify new backup metadata for $site"
  bash "$SCRIPT_DIR/verify_backup_set.sh" --metadata "$after" --site "$site"
  BACKUP_METADATA["$site"]="$after"
  ok "$site recovery point verified"
done

printf '\n===== MAINTENANCE MODE FOR FULL COHORT =====\n'
for site in "${APPROVED_SORTED[@]}"; do
  bench_run --site "$site" set-maintenance-mode on
done
MAINTENANCE_ARMED=1
ok 'all approved tenants are in maintenance before shared code movement'

printf '\n===== CHECKOUT APPROVED RELEASE =====\n'
git -C "$REPO_ROOT" checkout --detach "$TARGET_SHA"
[[ "$(git -C "$REPO_ROOT" rev-parse HEAD)" == "$TARGET_SHA" ]] || die 'repository did not land on approved release SHA'
[[ -d "$SRC_APP" ]] || die "source app missing after checkout: $SRC_APP"

printf '\n===== EXACT SHARED APP SYNC + BUILD ONCE =====\n'
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$SCRIPT_DIR/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/repair_apps_txt.sh"
fi
bench_run build --app "$APP"
ok 'approved Ledgix release synced and built once for the shared bench'

printf '\n===== MIGRATE + VERIFY EVERY TENANT =====\n'
for site in "${APPROVED_SORTED[@]}"; do
  bench_run --site "$site" migrate
  bench_run --site "$site" clear-cache
  bench_run --site "$site" clear-website-cache
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$site"
  bash "$SCRIPT_DIR/smoke_test.sh" --site "$site" --bench-dir "$BENCH_DIR" --offline
  ok "$site migration and offline verification passed"
done

printf '\n===== REFRESH SHARED PROCESSES =====\n'
if [[ -f "$SCRIPT_DIR/post_build_refresh.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/post_build_refresh.sh"
else
  sudo -n supervisorctl restart frappe-bench-web:
  sudo -n supervisorctl restart frappe-bench-workers:
fi
sudo -n nginx -t
sudo -n systemctl reload nginx
sudo -n supervisorctl status

printf '\n===== RELEASE FULL COHORT =====\n'
for site in "${APPROVED_SORTED[@]}"; do
  bench_run --site "$site" set-maintenance-mode off
done

printf '\n===== ONLINE SMOKE EVERY TENANT =====\n'
ONLINE_FAILED=0
for site in "${APPROVED_SORTED[@]}"; do
  if ! bash "$SCRIPT_DIR/smoke_test.sh" \
      --site "$site" \
      --bench-dir "$BENCH_DIR" \
      --online \
      --url "${SITE_URLS[$site]}"; then
    warn "$site online smoke failed"
    ONLINE_FAILED=1
  else
    ok "$site online smoke passed"
  fi
done
if [[ "$ONLINE_FAILED" -ne 0 ]]; then
  warn 'at least one tenant failed online smoke; putting the full cohort back into maintenance'
  for site in "${APPROVED_SORTED[@]}"; do
    bench_run --site "$site" set-maintenance-mode on || true
  done
  die 'shared-bench online verification failed'
fi

printf '\n===== PER-SITE RELEASE EVIDENCE =====\n'
DEPLOYED_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$DEPLOYED_SHA" == "$TARGET_SHA" ]] || die 'deployed SHA changed unexpectedly during shared release'
for site in "${APPROVED_SORTED[@]}"; do
  record_dir="$BENCH_DIR/sites/$site/private/ledgix-release"
  mkdir -p "$record_dir"
  record="$record_dir/last-successful.env"
  {
    printf 'site=%q\n' "$site"
    printf 'url=%q\n' "${SITE_URLS[$site]}"
    printf 'released_at_utc=%q\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'release_input=%q\n' "$RELEASE"
    printf 'previous_sha=%q\n' "$PREVIOUS_SHA"
    printf 'deployed_sha=%q\n' "$DEPLOYED_SHA"
    printf 'shared_bench=1\n'
    printf 'shared_bench_cohort_sha256=%q\n' "$COHORT_DIGEST"
    printf 'backup_metadata=%q\n' "${BACKUP_METADATA[$site]}"
    printf 'dependency_preflight=passed\n'
    printf 'offline_smoke=passed\n'
    printf 'online_smoke=passed\n'
  } >"$record"
  chmod 600 "$record"
  ok "$site release evidence: $record"
done
MAINTENANCE_ARMED=0

printf '\n===== SHARED-BENCH RELEASE VERDICT =====\n'
ok "all ${#APPROVED_SORTED[@]} Ledgix tenants moved together to $DEPLOYED_SHA"
printf 'shared_bench_release_complete=true\n'
