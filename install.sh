#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="${BENCH_DIR:-$SCRIPT_DIR/frappe-bench}"
LOG_DIR="$SCRIPT_DIR/logs/install"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/install-$TIMESTAMP.log"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"
ERPNEXT_BRANCH="${ERPNEXT_BRANCH:-version-15}"
ERPNEXT_REPO="${ERPNEXT_REPO:-https://github.com/frappe/erpnext.git}"
NODE_MAJOR="${NODE_MAJOR:-22}"
NVM_INSTALL_VERSION="${NVM_INSTALL_VERSION:-v0.40.3}"
MODE=""
ASSUME_YES=0
SUDO=()

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export PIPX_BIN_DIR="$HOME/.local/bin"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
err() { printf '[ERROR] %s\n' "$*" >&2; }
die() { err "$*"; err "Log file: $LOG_FILE"; exit 1; }
trap 'rc=$?; err "Failed at line $LINENO: $BASH_COMMAND"; err "Log file: $LOG_FILE"; exit "$rc"' ERR

section() { printf '\n==================================================\n %s\n==================================================\n' "$*"; }
have_cmd() { command -v "$1" >/dev/null 2>&1; }

usage() {
  cat <<EOF2
Usage: ./install.sh [options]

Ledgix POS installer/launcher.

Options:
  --local             Run local/development setup and exit
  --production        Open production/EC2 setup
  --yes, -y           Use safe defaults where possible
  --help, -h          Show this help

Environment:
  FRAPPE_BRANCH       Default: $FRAPPE_BRANCH
  ERPNEXT_BRANCH      Default: $ERPNEXT_BRANCH
  ERPNEXT_REPO        Default: $ERPNEXT_REPO
  NODE_MAJOR          Default: $NODE_MAJOR
  BENCH_DIR           Default: $BENCH_DIR
  ALLOW_INTERACTIVE_SUDO=1
                      Optional local-only escape hatch if your machine does not
                      have passwordless sudo. Default is never to prompt.
EOF2
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --local) MODE="local"; shift ;;
      --production) MODE="production"; shift ;;
      --yes|-y) ASSUME_YES=1; shift ;;
      --help|-h) usage; exit 0 ;;
      *) die "Unknown option: $1" ;;
    esac
  done
}

refresh_path() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    nvm use "$NODE_MAJOR" >/dev/null 2>&1 || true
  fi
}

run() { info "[RUN] $*"; "$@"; }

need_sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then SUDO=(); return 0; fi
  have_cmd sudo || die 'sudo is required for dependency installation'
  if sudo -n true >/dev/null 2>&1; then
    SUDO=(sudo -n)
    return 0
  fi
  if [[ "${ALLOW_INTERACTIVE_SUDO:-0}" == "1" && -t 0 ]]; then
    warn 'ALLOW_INTERACTIVE_SUDO=1: sudo may ask for your local Linux password'
    sudo -v || die 'sudo authentication failed'
    SUDO=(sudo)
    return 0
  fi
  die 'passwordless sudo is unavailable; this installer will not prompt. Set ALLOW_INTERACTIVE_SUDO=1 only on a local machine if you want an interactive sudo prompt.'
}

confirm() {
  local prompt="$1" default="${2:-N}" answer suffix
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    [[ "$default" =~ ^[Yy]$ ]]
    return
  fi
  if [[ "$default" =~ ^[Yy]$ ]]; then suffix='Y/n'; else suffix='y/N'; fi
  read -r -p "$prompt [$suffix]: " answer
  answer="${answer:-$default}"
  [[ "$answer" =~ ^([Yy]|[Yy][Ee][Ss])$ ]]
}

apt_has_candidate() { apt-cache policy "$1" 2>/dev/null | awk '/Candidate:/ {print $2}' | grep -qxv '(none)'; }

install_packages_batch() {
  local required=("$@") missing=() pkg
  for pkg in "${required[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      info "skip installed package: $pkg"
    elif apt_has_candidate "$pkg"; then
      missing+=("$pkg")
    else
      die "required package has no apt candidate: $pkg"
    fi
  done
  [[ "${#missing[@]}" -gt 0 ]] || return 0
  run "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get install -y "${missing[@]}"
}

install_optional_batch() {
  local requested=("$@") available=() pkg
  for pkg in "${requested[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      info "skip installed optional package: $pkg"
    elif apt_has_candidate "$pkg"; then
      available+=("$pkg")
    else
      warn "optional package unavailable: $pkg"
    fi
  done
  [[ "${#available[@]}" -gt 0 ]] && run "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get install -y "${available[@]}"
}

ensure_service() {
  local svc="$1"
  if have_cmd systemctl && systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
    run "${SUDO[@]}" systemctl enable --now "$svc"
  elif have_cmd service; then
    run "${SUDO[@]}" service "$svc" start
  fi
}

preflight() {
  section 'Preflight'
  printf 'Repo: %s\nBench: %s\nFrappe: %s\nERPNext: %s\nNode: %s\nOS: %s\nRAM: %s\nSwap: %s\nDisk free: %s\n' \
    "$SCRIPT_DIR" "$BENCH_DIR" "$FRAPPE_BRANCH" "$ERPNEXT_BRANCH" "$NODE_MAJOR" \
    "$(. /etc/os-release 2>/dev/null && printf '%s' "${PRETTY_NAME:-unknown}" || printf unknown)" \
    "$(free -h 2>/dev/null | awk '/^Mem:/ {print $2}')" \
    "$(free -h 2>/dev/null | awk '/^Swap:/ {print $2}')" \
    "$(df -h "$SCRIPT_DIR" 2>/dev/null | awk 'NR==2 {print $4}')"
  local cmd
  for cmd in git curl python3 node npm yarn mariadb redis-server bench; do
    if have_cmd "$cmd"; then printf '  %-14s %s\n' "$cmd" "$("$cmd" --version 2>&1 | head -n1 || true)"; else printf '  %-14s missing\n' "$cmd"; fi
  done
}

install_dependencies() {
  section 'System Dependencies'
  need_sudo
  run "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get update
  run "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get --fix-broken install -y
  local required=(
    git curl ca-certificates gnupg build-essential pkg-config
    python3 python3-dev python3-pip python3-venv python3-setuptools pipx
    redis-server mariadb-server mariadb-client cron
    libffi-dev libssl-dev libmysqlclient-dev libjpeg-dev zlib1g-dev
    liblcms2-dev libwebp-dev libxrender1 libxext6 fontconfig xfonts-75dpi xfonts-base
  )
  install_packages_batch "${required[@]}"
  if apt_has_candidate libtiff-dev; then install_packages_batch libtiff-dev; elif apt_has_candidate libtiff5-dev; then install_packages_batch libtiff5-dev; fi
  install_optional_batch wkhtmltopdf
  ensure_service mariadb
  ensure_service redis-server
}

ensure_nvm_node_yarn() {
  section 'Node + Yarn'
  refresh_path
  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    run bash -c "curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_INSTALL_VERSION}/install.sh | bash"
  fi
  [[ -s "$NVM_DIR/nvm.sh" ]] || die 'nvm installation failed'
  # shellcheck disable=SC1090
  . "$NVM_DIR/nvm.sh"
  run nvm install "$NODE_MAJOR"
  run nvm alias default "$NODE_MAJOR"
  run nvm use "$NODE_MAJOR"
  refresh_path
  if ! have_cmd yarn; then run npm install -g yarn@1.22.22; fi
  ok "node $(node -v); yarn $(yarn --version)"
}

ensure_cli_tools() {
  section 'Python CLI Tools'
  refresh_path
  have_cmd pipx || die 'pipx is missing'
  run pipx ensurepath || true
  if ! have_cmd uv; then run pipx install uv; fi
  if ! have_cmd bench; then run pipx install frappe-bench; fi
  refresh_path
  have_cmd bench || die 'bench is unavailable after installation'
}

valid_bench() {
  [[ -d "$BENCH_DIR/apps/frappe" && -d "$BENCH_DIR/sites" && -x "$BENCH_DIR/env/bin/python" && -f "$BENCH_DIR/Procfile" && -f "$BENCH_DIR/sites/common_site_config.json" ]]
}

ensure_bench() {
  section 'Frappe Bench'
  refresh_path
  if valid_bench; then
    ok "reusing valid bench: $BENCH_DIR"
    return 0
  fi
  if [[ -e "$BENCH_DIR" ]]; then
    local moved="$SCRIPT_DIR/frappe-bench.incomplete-$TIMESTAMP"
    if [[ "$ASSUME_YES" -eq 1 ]] || confirm "Bench is incomplete. Move it to $moved and recreate?" 'Y'; then
      run mv "$BENCH_DIR" "$moved"
    else
      die 'incomplete bench must be fixed or moved'
    fi
  fi
  run bench init --frappe-branch "$FRAPPE_BRANCH" "$BENCH_DIR"
  valid_bench || die 'bench init completed but validation failed'
  ok "bench initialized: $BENCH_DIR"
}

ensure_bench_app_registered() {
  local app="$1"
  local apps_txt="$BENCH_DIR/sites/apps.txt"
  [[ -f "$apps_txt" ]] || : >"$apps_txt"
  if grep -Fxq "$app" "$apps_txt" 2>/dev/null; then
    return 0
  fi
  if [[ -s "$apps_txt" && -n "$(tail -c 1 "$apps_txt" 2>/dev/null || true)" ]]; then
    printf '\n' >>"$apps_txt"
  fi
  printf '%s\n' "$app" >>"$apps_txt"
  ok "registered bench app: $app"
}

ensure_erpnext_app() {
  section 'ERPNext v15 Dependency'
  valid_bench || die "valid bench not found: $BENCH_DIR"
  local app_dir="$BENCH_DIR/apps/erpnext"

  if [[ -d "$app_dir" ]]; then
    [[ -d "$app_dir/.git" ]] || die "ERPNext app directory exists but is not a git checkout: $app_dir"
    info "reusing ERPNext app: $app_dir"
  else
    info "fetching ERPNext $ERPNEXT_BRANCH from $ERPNEXT_REPO"
    (cd "$BENCH_DIR" && bench get-app --branch "$ERPNEXT_BRANCH" erpnext "$ERPNEXT_REPO")
  fi

  [[ -d "$app_dir" ]] || die "ERPNext was not prepared in bench: $app_dir"
  ensure_bench_app_registered erpnext
  "$BENCH_DIR/env/bin/python" -c 'import erpnext' >/dev/null 2>&1 || die 'ERPNext import failed after bench setup'
  ok 'ERPNext is available on the bench'
}

validate_framework_alignment() {
  section 'Frappe / ERPNext Alignment'
  local app expected branch app_dir
  for app in frappe erpnext; do
    if [[ "$app" == "frappe" ]]; then expected="$FRAPPE_BRANCH"; else expected="$ERPNEXT_BRANCH"; fi
    app_dir="$BENCH_DIR/apps/$app"
    [[ -d "$app_dir/.git" ]] || die "$app is not a git checkout: $app_dir"
    branch="$(git -C "$app_dir" branch --show-current)"
    if [[ -n "$branch" && "$branch" != "$expected" ]]; then
      die "$app branch mismatch: expected $expected, found $branch"
    fi
    if [[ -z "$branch" ]]; then
      warn "$app is on a detached HEAD; expected branch policy is $expected"
    else
      ok "$app branch: $branch"
    fi
  done

  info 'bench application versions:'
  (cd "$BENCH_DIR" && bench version --format plain) || die 'could not read bench app versions'
}

wsl_note() {
  if grep -qiE 'microsoft|wsl' /proc/version /proc/sys/kernel/osrelease 2>/dev/null; then
    warn 'WSL detected: Windows browser can normally use http://localhost:8000.'
  fi
}

local_flow() {
  section 'Local / Development Setup'
  preflight
  if [[ "$ASSUME_YES" -eq 0 ]]; then confirm 'Continue local setup?' 'Y' || die 'cancelled'; fi
  install_dependencies
  ensure_nvm_node_yarn
  ensure_cli_tools
  ensure_bench
  ensure_erpnext_app
  validate_framework_alignment
  wsl_note
  section 'Local Setup Complete'
  ok "bench ready: $BENCH_DIR"
  ok "framework stack: Frappe $FRAPPE_BRANCH + ERPNext $ERPNEXT_BRANCH"
  info 'Next: ./site_setup.sh'
  if [[ "$ASSUME_YES" -eq 0 && -f "$SCRIPT_DIR/site_setup.sh" ]] && confirm 'Run site setup now?' 'N'; then
    exec "$SCRIPT_DIR/site_setup.sh"
  fi
}

production_flow() {
  local script="$SCRIPT_DIR/deploy/production_setup.sh"
  [[ -x "$script" ]] || chmod +x "$script"
  if [[ "$ASSUME_YES" -eq 1 ]]; then exec "$script" --yes; else exec "$script"; fi
}

menu() {
  preflight
  printf '\n========================\n Ledgix POS Installer\n========================\n1) Local / Development Setup\n2) Production / EC2 Setup\n3) Exit\n'
  local choice
  read -r -p 'Choose: ' choice
  case "${choice:-}" in
    1) local_flow ;;
    2) production_flow ;;
    3) exit 0 ;;
    *) die 'invalid option' ;;
  esac
}

main() {
  parse_args "$@"
  case "$MODE" in
    local) local_flow ;;
    production) production_flow ;;
    '') menu ;;
    *) die "invalid mode: $MODE" ;;
  esac
}

main "$@"
