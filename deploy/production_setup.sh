#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LEGACY_SECRETS_FILE="$SCRIPT_DIR/production.secrets.md"
SAFE_SECRETS_FILE="${LEDGIX_PRODUCTION_SECRETS_FILE:-$HOME/.config/ledgix/production-sites.md}"

# Production actions run in fresh non-login shells on EC2. Node is installed
# with nvm, so explicitly load the selected Node version before invoking any
# bench command. Frappe's build subprocesses inherit this PATH.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
NODE_MAJOR="${NODE_MAJOR:-22}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
  nvm use "$NODE_MAJOR" >/dev/null 2>&1 || true
fi

# Fresh bench init can leave sites/apps.txt without a trailing newline.
if [[ -f "$SCRIPT_DIR/repair_apps_txt.sh" ]]; then
  bash "$SCRIPT_DIR/repair_apps_txt.sh"
fi

fail() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

find_action() {
  local args=("$@") i
  for ((i = 0; i < ${#args[@]}; i++)); do
    if [[ "${args[$i]}" == "--action" && $((i + 1)) -lt ${#args[@]} ]]; then
      printf '%s\n' "${args[$((i + 1))]}"
      return 0
    fi
  done
  printf '\n'
}

relocate_legacy_secrets() {
  [[ -f "$LEGACY_SECRETS_FILE" ]] || return 0
  local target_dir
  target_dir="$(dirname "$SAFE_SECRETS_FILE")"
  umask 077
  mkdir -p "$target_dir"
  chmod 700 "$target_dir" 2>/dev/null || true
  if [[ -s "$SAFE_SECRETS_FILE" ]]; then
    printf '\n' >>"$SAFE_SECRETS_FILE"
  fi
  cat "$LEGACY_SECRETS_FILE" >>"$SAFE_SECRETS_FILE"
  chmod 600 "$SAFE_SECRETS_FILE"
  rm -f "$LEGACY_SECRETS_FILE"
  printf '[OK] production credentials moved outside the repository: %s\n' "$SAFE_SECRETS_FILE"
}

require_production_site() {
  [[ -n "${PRODUCTION_SITE:-}" ]] || fail 'PRODUCTION_SITE is required for production site/full/backup/update actions'
  [[ "$PRODUCTION_SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid PRODUCTION_SITE: $PRODUCTION_SITE"
}

require_deploy_target() {
  require_production_site
  [[ -n "${DEPLOY_RELEASE:-}" ]] || fail 'DEPLOY_RELEASE is required and must be a full commit SHA or immutable tag'
  [[ -n "${PRODUCTION_URL:-}" ]] || fail 'PRODUCTION_URL is required for post-deploy online smoke checks'
}

run_ec2() {
  bash "$SCRIPT_DIR/ec2_setup.sh" "$@"
}

ensure_erpnext_bench() {
  [[ -f "$SCRIPT_DIR/ensure_erpnext.sh" ]] || {
    printf '[ERROR] missing ERPNext dependency helper: %s\n' "$SCRIPT_DIR/ensure_erpnext.sh" >&2
    return 1
  }
  bash "$SCRIPT_DIR/ensure_erpnext.sh"
}

start_temp_redis() {
  [[ -f "$SCRIPT_DIR/bench_redis.sh" ]] || return 0
  bash "$SCRIPT_DIR/bench_redis.sh" start
}

stop_temp_redis() {
  [[ -f "$SCRIPT_DIR/bench_redis.sh" ]] || return 0
  bash "$SCRIPT_DIR/bench_redis.sh" stop || true
}

run_services() {
  [[ -f "$SCRIPT_DIR/production_services_fix.sh" ]] || {
    printf '[ERROR] missing production services helper: %s\n' "$SCRIPT_DIR/production_services_fix.sh" >&2
    return 1
  }
  bash "$SCRIPT_DIR/production_services_fix.sh"
}

post_build_refresh() {
  [[ -f "$SCRIPT_DIR/post_build_refresh.sh" ]] || return 0
  bash "$SCRIPT_DIR/post_build_refresh.sh"
}

run_safe_backup() {
  [[ -f "$SCRIPT_DIR/backup_safe.sh" ]] || {
    printf '[ERROR] missing backup helper: %s\n' "$SCRIPT_DIR/backup_safe.sh" >&2
    return 1
  }
  require_production_site
  bash "$SCRIPT_DIR/backup_safe.sh" --site "$PRODUCTION_SITE"
}

run_safe_deploy_update() {
  [[ -f "$SCRIPT_DIR/deploy_update_safe.sh" ]] || {
    printf '[ERROR] missing deploy update helper: %s\n' "$SCRIPT_DIR/deploy_update_safe.sh" >&2
    return 1
  }
  require_deploy_target
  bash "$SCRIPT_DIR/deploy_update_safe.sh" \
    --site "$PRODUCTION_SITE" \
    --release "$DEPLOY_RELEASE" \
    --url "$PRODUCTION_URL"
}

ACTION="$(find_action "$@")"

# Clean up any credential file left by an interrupted older run before doing
# anything else. New production credentials are retained outside the Git repo.
relocate_legacy_secrets

case "$ACTION" in
  site|full|backup) require_production_site ;;
  deploy-update) require_deploy_target ;;
esac

if [[ "$ACTION" == "backup" ]]; then
  run_safe_backup
  exit $?
fi

if [[ "$ACTION" == "deploy-update" ]]; then
  run_safe_deploy_update
  exit $?
fi

# The underlying site creator generates a strong Administrator password when
# FRAPPE_ADMIN_PASSWORD is omitted. Never provide an implicit weak default here.
if [[ "$ACTION" == "site" ]]; then
  ensure_erpnext_bench
  trap 'stop_temp_redis; relocate_legacy_secrets' EXIT
  start_temp_redis
  run_ec2 "$@"
  stop_temp_redis
  relocate_legacy_secrets
  trap - EXIT
  exit 0
fi

if [[ "$ACTION" == "apps" ]]; then
  ensure_erpnext_bench
  run_ec2 "$@"
  post_build_refresh
  exit $?
fi

if [[ "$ACTION" == "services" ]]; then
  run_services
  exit $?
fi

if [[ "$ACTION" == "full" ]]; then
  original=("$@")
  base=()
  for ((i = 0; i < ${#original[@]}; i++)); do
    if [[ "${original[$i]}" == "--action" && $((i + 1)) -lt ${#original[@]} && "${original[$((i + 1))]}" == "full" ]]; then
      i=$((i + 1))
      continue
    fi
    base+=("${original[$i]}")
  done

  trap relocate_legacy_secrets EXIT
  run_ec2 "${base[@]}" --action preflight
  run_ec2 "${base[@]}" --action packages
  run_ec2 "${base[@]}" --action bench
  ensure_erpnext_bench
  run_ec2 "${base[@]}" --action apps
  post_build_refresh

  trap 'stop_temp_redis; relocate_legacy_secrets' EXIT
  start_temp_redis
  run_ec2 "${base[@]}" --action site
  stop_temp_redis

  run_services
  if [[ -n "${PRODUCTION_DOMAIN:-}" && -n "${LETSENCRYPT_EMAIL:-}" ]]; then
    run_ec2 "${base[@]}" --action ssl
  fi
  run_ec2 "${base[@]}" --action status
  relocate_legacy_secrets
  trap - EXIT
  exit 0
fi

exec bash "$SCRIPT_DIR/ec2_setup.sh" "$@"
