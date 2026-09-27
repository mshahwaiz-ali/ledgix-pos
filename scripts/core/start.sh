#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
BENCH_DIR="$REPO_ROOT/frappe-bench"
LOG_DIR="$REPO_ROOT/logs"
NODE_MAJOR="${NODE_MAJOR:-22}"
BACKGROUND=0
STOP=0
STATUS=0
SMOKE=0
SMOKE_SITE=""
DEV_PORTS=(8000 9000 11000 12000 13000)
declare -a SITES=()
declare -a SELECTED_SITES=()
SUDO=()
FOREGROUND_BENCH_PID=""

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export NVM_DIR="$HOME/.nvm"

info() { printf '[INFO] %s\n' "$*"; }
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
err() { printf '[ERROR] %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

trap 'err "Failed at line $LINENO: $BASH_COMMAND"' ERR

usage() {
  cat <<'EOF'
Usage: ./scripts/core/start.sh [options]

Development/local runner only. This is not production service management.

Options:
  --bench-dir PATH   Bench directory (default: ./frappe-bench)
  --background       Start bench start in background
  --stop             Stop tracked dev process for this bench
  --status           Show bench/site/process status
  --smoke            Run local smoke checks without starting bench
  --site SITE        Site to smoke test
  --help             Show this help
EOF
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require_cmd() {
  have_cmd "$1" || die "Missing required command: $1"
}

refresh_path() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  export NVM_DIR="$HOME/.nvm"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"
    nvm use "$NODE_MAJOR" >/dev/null 2>&1 || true
  fi
}

need_sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    SUDO=()
    return 0
  fi
  have_cmd sudo || return 1
  sudo -v || return 1
  SUDO=(sudo)
}

make_log_dir() {
  mkdir -p "$LOG_DIR"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --bench-dir)
        [[ $# -ge 2 ]] || die "--bench-dir requires a path"
        BENCH_DIR="$2"
        shift 2
        ;;
      --background) BACKGROUND=1; shift ;;
      --stop) STOP=1; shift ;;
      --status) STATUS=1; shift ;;
      --smoke) SMOKE=1; shift ;;
      --site)
        [[ $# -ge 2 ]] || die "--site requires a site name"
        SMOKE_SITE="$2"
        shift 2
        ;;
      --help|-h) usage; exit 0 ;;
      *) die "Unknown option: $1" ;;
    esac
  done
}

verify_environment() {
  refresh_path
  require_cmd bench
  require_cmd node
  require_cmd yarn
  if ! have_cmd ss && ! have_cmd lsof; then
    warn "neither ss nor lsof is available; port cleanup/status will be limited"
  fi
}

verify_bench() {
  [[ -d "$BENCH_DIR/apps" ]] || die "$BENCH_DIR does not look like a Frappe bench: missing apps"
  [[ -d "$BENCH_DIR/sites" ]] || die "$BENCH_DIR does not look like a Frappe bench: missing sites"
  [[ -d "$BENCH_DIR/env" ]] || die "$BENCH_DIR does not look like a Frappe bench: missing env"
  [[ -f "$BENCH_DIR/Procfile" ]] || die "$BENCH_DIR does not look like a Frappe bench: missing Procfile"
}

list_sites() {
  local dir site
  SITES=()
  while IFS= read -r -d '' dir; do
    site="$(basename "$dir")"
    SITES+=("$site")
    if [[ "$site" != "${site,,}" ]]; then
      warn "WARNING: Site folder contains uppercase. Browsers usually send lowercase hostnames. Rename site folder/config to lowercase: $site"
    fi
  done < <(find "$BENCH_DIR/sites" -mindepth 1 -maxdepth 1 -type d \
    ! -name assets ! -name archived \
    -exec test -f "{}/site_config.json" \; -print0 2>/dev/null | sort -z)
}

require_sites_for_start() {
  if [[ "${#SITES[@]}" -eq 0 ]]; then
    die "No Frappe sites found in $BENCH_DIR/sites. Run ./scripts/core/site_setup.sh first."
  fi
}

select_all_sites() {
  SELECTED_SITES=("${SITES[@]}")
}

hosts_entry_exists() {
  local site="$1"
  awk -v site="$site" '
    $1 == "127.0.0.1" {
      for (i = 2; i <= NF; i++) {
        if ($i == site) {
          found = 1
        }
      }
    }
    END { exit found ? 0 : 1 }
  ' /etc/hosts
}

missing_hosts_entries() {
  local site
  for site in "${SITES[@]}"; do
    hosts_entry_exists "$site" || printf '%s\n' "$site"
  done
}

print_hosts_commands() {
  local site line
  while IFS= read -r site; do
    [[ -n "$site" ]] || continue
    line="127.0.0.1 $site # managed-by-frappe-custom-installer"
    warn "  echo '$line' | sudo tee -a /etc/hosts"
  done < <(missing_hosts_entries)
}

maybe_add_missing_hosts() {
  local missing=()
  mapfile -t missing < <(missing_hosts_entries)
  [[ "${#missing[@]}" -gt 0 ]] || return 0

  warn "Missing /etc/hosts entries:"
  local site line
  for site in "${missing[@]}"; do
    line="127.0.0.1 $site # managed-by-frappe-custom-installer"
    warn "  echo '$line' | sudo tee -a /etc/hosts"
  done

  local answer
  read -r -p "Add missing hosts entries now? y/N: " answer
  case "${answer:-}" in
    y|Y|yes|YES)
      if need_sudo; then
        for site in "${missing[@]}"; do
          line="127.0.0.1 $site # managed-by-frappe-custom-installer"
          printf '%s\n' "$line" | "${SUDO[@]}" tee -a /etc/hosts >/dev/null || warn "could not add hosts entry for $site"
        done
      else
        warn "sudo unavailable; add entries manually:"
        print_hosts_commands
      fi
      ;;
    *)
      warn "hosts entries not added; browser DNS may fail until you add them"
      ;;
  esac
}

print_urls() {
  local site
  printf 'URLs:\n'
  for site in "${SITES[@]}"; do
    printf '  http://%s:8000\n' "$site"
  done
}

site_http_code() {
  local site="$1"
  curl -sS -o /dev/null -w "%{http_code}" --max-time 2 -H "Host: $site" "http://127.0.0.1:8000" 2>/dev/null || true
}

validate_site_after_start() {
  local site="$1" deadline code
  deadline=$((SECONDS + 20))

  while (( SECONDS < deadline )); do
    code="$(site_http_code "$site")"
    if [[ "$code" =~ ^[23] ]]; then
      ok "site reachable: http://$site:8000"
      return 0
    fi
    sleep 1
  done

  warn "site not reachable yet: http://$site:8000"
  return 0
}

validate_sites_after_start() {
  local site
  have_cmd curl || {
    warn "curl unavailable; skipping post-start site validation"
    return 0
  }

  for site in "${SITES[@]}"; do
    validate_site_after_start "$site"
  done
}

print_http_status() {
  local site code
  have_cmd curl || {
    warn "curl unavailable; skipping HTTP checks"
    return 0
  }

  printf 'HTTP status:\n'
  for site in "${SITES[@]}"; do
    code="$(site_http_code "$site")"
    if [[ "$code" =~ ^[23] ]]; then
      printf '  %s: reachable (%s)\n' "$site" "$code"
    elif [[ -n "$code" && "$code" != "000" ]]; then
      printf '  %s: responded (%s)\n' "$site" "$code"
    else
      printf '  %s: not reachable or bench is stopped\n' "$site"
    fi
  done
}

SMOKE_FAILURES=0
SMOKE_WARNINGS=0

smoke_pass() {
  printf '[PASS] %s\n' "$*"
}

smoke_warn() {
  SMOKE_WARNINGS=$((SMOKE_WARNINGS + 1))
  printf '[WARN] %s\n' "$*" >&2
}

smoke_fail() {
  SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
  printf '[FAIL] %s\n' "$*" >&2
}

select_smoke_site() {
  local -n _site="$1"
  local candidate
  if [[ -n "$SMOKE_SITE" ]]; then
    for candidate in "${SITES[@]}"; do
      if [[ "$candidate" == "$SMOKE_SITE" ]]; then
        _site="$candidate"
        return 0
      fi
    done
    die "smoke site was not found in $BENCH_DIR/sites: $SMOKE_SITE"
  fi

  if [[ "${#SITES[@]}" -eq 1 ]]; then
    _site="${SITES[0]}"
    return 0
  fi

  die "multiple sites found; pass --site SITE for smoke checks"
}

site_path_http_code() {
  local site="$1"
  local path="$2"
  curl -sS -o /dev/null -w "%{http_code}" --max-time 5 -H "Host: $site" "http://127.0.0.1:8000$path" 2>/dev/null || true
}

smoke_http_path() {
  local site="$1"
  local path="$2"
  local label="$3"
  local code
  if ! have_cmd curl; then
    smoke_fail "curl is required for HTTP smoke checks"
    return 0
  fi
  code="$(site_path_http_code "$site" "$path")"
  if [[ "$code" =~ ^[23] ]]; then
    smoke_pass "$label responded with $code"
  elif [[ "$code" =~ ^4 ]]; then
    smoke_warn "$label responded with $code"
  elif [[ -n "$code" && "$code" != "000" ]]; then
    smoke_fail "$label responded with $code"
  else
    smoke_fail "$label did not respond"
  fi
}

smoke_site_app() {
  local site="$1"
  local app="${2:-ledgix_saas}"
  local output
  if output="$(cd "$BENCH_DIR" && bench --site "$site" list-apps 2>&1)"; then
    if awk '{print $1}' <<<"$output" | grep -Fxq "$app"; then
      smoke_pass "$app is installed on $site"
    else
      smoke_fail "$app is not installed on $site"
    fi
  else
    smoke_warn "could not verify installed apps with bench list-apps; DB may be stopped or sandboxed"
    if grep -Eq "Operation not permitted|Can't connect to MySQL" <<<"$output"; then
      printf '  MariaDB connection failed or was blocked by the current execution environment.\n' >&2
    else
      printf '%s\n' "$output" | tail -n 12 | sed 's/^/  /' >&2
    fi
  fi
}

run_smoke() {
  local site pid_count
  require_sites_for_start
  select_smoke_site site
  printf 'Local smoke site: %s\n' "$site"

  [[ -f "$BENCH_DIR/sites/$site/site_config.json" ]] &&
    smoke_pass "site_config.json exists" ||
    smoke_fail "site_config.json is missing for $site"

  hosts_entry_exists "$site" &&
    smoke_pass "/etc/hosts maps $site to 127.0.0.1" ||
    smoke_fail "/etc/hosts does not map $site to 127.0.0.1"

  pid_count="$(bench_owned_port_pids 8000 | wc -l | tr -d ' ')"
  if [[ "$pid_count" =~ ^[1-9] ]]; then
    smoke_pass "port 8000 is served by this bench"
  elif [[ -n "$(port_pids 8000 || true)" ]]; then
    smoke_warn "port 8000 is occupied by another process"
  else
    smoke_fail "port 8000 is not listening; start local bench first"
  fi

  smoke_http_path "$site" "/login" "/login"
  smoke_http_path "$site" "/app" "/app"
  smoke_site_app "$site" "ledgix_saas"

  printf '\nSmoke summary: %s failure(s), %s warning(s)\n' "$SMOKE_FAILURES" "$SMOKE_WARNINGS"
  if [[ "$SMOKE_FAILURES" -eq 0 ]]; then
    return 0
  fi
  return 1
}

is_process_in_bench() {
  local pid="$1" proc_dir cwd_path cmdline_path cwd="" cmd=""
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  proc_dir="/proc/$pid"
  cwd_path="$proc_dir/cwd"
  cmdline_path="$proc_dir/cmdline"
  [[ -d "$proc_dir" ]] || return 1
  if [[ -e "$cwd_path" ]]; then
    cwd="$(readlink -f "$cwd_path" 2>/dev/null || true)"
  fi
  [[ -d "$proc_dir" ]] || return 1
  if [[ -r "$cmdline_path" ]]; then
    cmd="$(tr '\0' ' ' 2>/dev/null <"$cmdline_path" || true)"
  fi
  [[ "$cwd" == "$BENCH_DIR"* || "$cmd" == *"$BENCH_DIR"* ]]
}

kill_pid_safely() {
  local pid="$1" signal="${2:-TERM}" pgid current_pgid
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  if [[ "$pid" == "$$" || "$pid" == "${BASHPID:-$$}" || "$pid" == "$PPID" ]]; then
    return 0
  fi
  if is_process_in_bench "$pid"; then
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    current_pgid="$(ps -o pgid= -p "$$" 2>/dev/null | tr -d ' ' || true)"
    if [[ -n "$pgid" && "$pgid" != "$current_pgid" ]]; then
      kill "-$signal" "-$pgid" 2>/dev/null || true
    else
      kill "-$signal" "$pid" 2>/dev/null || true
    fi
  else
    warn "not stopping unrelated process: $pid"
  fi
}

port_pids() {
  local port="$1" pids=""
  if have_cmd ss; then
    pids="$(ss -ltnp 2>/dev/null | awk -v suffix=":$port" '
      $4 ~ suffix "$" {
        line = $0
        while (match(line, /pid=[0-9]+/)) {
          print substr(line, RSTART + 4, RLENGTH - 4)
          line = substr(line, RSTART + RLENGTH)
        }
      }
    ' | sort -u || true)"
  fi
  if [[ -z "$pids" ]] && have_cmd lsof; then
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  fi
  [[ -n "$pids" ]] && printf '%s\n' "$pids"
}

bench_owned_port_pids() {
  local port="$1" pid pids
  pids="$(port_pids "$port" || true)"
  [[ -n "$pids" ]] || return 0
  for pid in $pids; do
    is_process_in_bench "$pid" && printf '%s\n' "$pid"
  done | sort -u
}

kill_port_processes() {
  local signal="${1:-TERM}" port pid pids action
  if [[ "$signal" == "KILL" ]]; then
    action="force stopping"
  else
    action="stopping"
  fi
  for port in "${DEV_PORTS[@]}"; do
    pids="$(port_pids "$port" || true)"
    [[ -n "$pids" ]] || continue

    for pid in $pids; do
      if is_process_in_bench "$pid"; then
        warn "port $port is used by this bench; $action PID $pid"
        kill_pid_safely "$pid" "$signal"
      else
        warn "port $port is occupied by unrelated PID $pid; leaving it running"
      fi
    done
  done
}

wait_for_bench_ports_free() {
  local timeout="${1:-15}" attempt port pids busy
  for ((attempt = 0; attempt < timeout; attempt++)); do
    busy=0
    for port in "${DEV_PORTS[@]}"; do
      pids="$(bench_owned_port_pids "$port" || true)"
      if [[ -n "$pids" ]]; then
        busy=1
        break
      fi
    done
    [[ "$busy" -eq 0 ]] && return 0
    sleep 1
  done
  return 1
}

ensure_dev_ports_free() {
  local port pid pids busy=0
  for port in "${DEV_PORTS[@]}"; do
    pids="$(port_pids "$port" || true)"
    [[ -n "$pids" ]] || continue
    for pid in $pids; do
      if is_process_in_bench "$pid"; then
        warn "port $port is still occupied by this bench PID $pid"
      else
        warn "port $port is occupied by unrelated PID $pid"
      fi
      busy=1
    done
  done
  [[ "$busy" -eq 0 ]]
}

cleanup_runner_pidfile() {
  local pidfile="$BENCH_DIR/.runner/bench_start.pid" pid
  [[ -f "$pidfile" ]] || return 0
  pid="$(tr -d '[:space:]' 2>/dev/null <"$pidfile" || true)"
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || ! is_process_in_bench "$pid"; then
    rm -f "$pidfile" 2>/dev/null || true
  fi
}

cleanup_stale_pid_files() {
  local pfile pid
  cleanup_runner_pidfile
  [[ -d "$BENCH_DIR/config/pids" ]] || return 0

  while IFS= read -r -d '' pfile; do
    [[ -f "$pfile" ]] || continue
    pid="$(tr -d '[:space:]' 2>/dev/null <"$pfile" || true)"
    if [[ ! "$pid" =~ ^[0-9]+$ ]] || ! is_process_in_bench "$pid"; then
      rm -f "$pfile" 2>/dev/null || true
    fi
  done < <(find "$BENCH_DIR/config/pids" -type f -name '*.pid' -print0 2>/dev/null)
}

stop_bench() {
  local pidfile="$BENCH_DIR/.runner/bench_start.pid" pid pfile proc
  if [[ -f "$pidfile" ]]; then
    pid="$(tr -d '[:space:]' 2>/dev/null <"$pidfile" || true)"
    kill_pid_safely "$pid" TERM
  fi

  if [[ -d "$BENCH_DIR/config/pids" ]]; then
    while IFS= read -r -d '' pfile; do
      [[ -f "$pfile" ]] || continue
      pid="$(tr -d '[:space:]' 2>/dev/null <"$pfile" || true)"
      kill_pid_safely "$pid" TERM
    done < <(find "$BENCH_DIR/config/pids" -type f -name '*.pid' -print0)
  fi

  while IFS= read -r -d '' proc; do
    pid="$(basename "$proc")"
    is_process_in_bench "$pid" && kill_pid_safely "$pid" TERM
  done < <(find /proc -maxdepth 1 -type d -regex '/proc/[0-9]+' -print0 2>/dev/null)

  sleep 1
  kill_port_processes TERM
  if ! wait_for_bench_ports_free 12; then
    warn "bench-owned ports are still busy after SIGTERM; forcing only those bench PIDs"
    kill_port_processes KILL
    wait_for_bench_ports_free 5 || warn "some bench-owned ports are still busy; run ./scripts/core/start.sh --status"
  fi
  cleanup_stale_pid_files
  info "Stopped tracked dev processes for this bench where possible."
}

bench_pid_status() {
  local pidfile="$BENCH_DIR/.runner/bench_start.pid" pid
  if [[ ! -f "$pidfile" ]]; then
    printf 'none'
    return 0
  fi
  pid="$(tr -d '[:space:]' 2>/dev/null <"$pidfile" || true)"
  if is_process_in_bench "$pid"; then
    printf 'running (PID %s)' "$pid"
  else
    rm -f "$pidfile"
    printf 'stale PID file removed'
  fi
}

print_port_status() {
  local port pid pids owner
  printf 'Ports:\n'
  for port in "${DEV_PORTS[@]}"; do
    pids="$(port_pids "$port" || true)"
    if [[ -z "$pids" ]]; then
      printf '  %s: free\n' "$port"
      continue
    fi
    for pid in $pids; do
      if is_process_in_bench "$pid"; then
        owner="this bench"
      else
        owner="unrelated process"
      fi
      printf '  %s: PID %s (%s)\n' "$port" "$pid" "$owner"
    done
  done
}

show_status() {
  printf 'Bench dir: %s\n' "$BENCH_DIR"
  printf 'Tracked bench start: %s\n' "$(bench_pid_status)"
  printf 'Detected sites:\n'
  if [[ "${#SITES[@]}" -eq 0 ]]; then
    printf '  none\n'
  else
    printf '  %s\n' "${SITES[@]}"
    print_urls
  fi
  print_port_status
  print_http_status
  printf '\nNote:\n'
  printf '  http://site.local:8000 goes to Frappe bench start.\n'
  printf '  http://site.local without :8000 may show nginx/default page if another web server is installed.\n'
}

foreground_signal_cleanup() {
  local signal="$1" exit_code=130
  [[ "$signal" == "TERM" ]] && exit_code=143
  trap - INT TERM
  if [[ -n "${FOREGROUND_BENCH_PID:-}" ]] && is_process_in_bench "$FOREGROUND_BENCH_PID"; then
    warn "stopping foreground bench process..."
    kill_pid_safely "$FOREGROUND_BENCH_PID" TERM
    set +e
    wait "$FOREGROUND_BENCH_PID" >/dev/null 2>&1
    set -e
  fi
  FOREGROUND_BENCH_PID=""
  cleanup_stale_pid_files
  exit "$exit_code"
}

start_foreground() {
  local pidfile="$BENCH_DIR/.runner/bench_start.pid" rc
  mkdir -p "$BENCH_DIR/.runner"
  info "Stopping existing tracked dev processes for this bench..."
  stop_bench
  ensure_dev_ports_free || die "Cannot start bench because one or more dev ports are still busy."
  maybe_add_missing_hosts
  print_urls
  info "Starting bench in foreground. Press Ctrl+C to stop."
  cd "$BENCH_DIR"
  bench start &
  FOREGROUND_BENCH_PID="$!"
  printf '%s\n' "$FOREGROUND_BENCH_PID" >"$pidfile"
  trap 'foreground_signal_cleanup INT' INT
  trap 'foreground_signal_cleanup TERM' TERM
  validate_sites_after_start
  set +e
  wait "$FOREGROUND_BENCH_PID"
  rc="$?"
  set -e
  trap - INT TERM
  FOREGROUND_BENCH_PID=""
  cleanup_stale_pid_files
  exit "$rc"
}

start_background() {
  local log_file="$LOG_DIR/bench-start.log" pidfile="$BENCH_DIR/.runner/bench_start.pid"
  make_log_dir
  mkdir -p "$BENCH_DIR/.runner"
  info "Stopping existing tracked dev processes for this bench..."
  stop_bench
  ensure_dev_ports_free || die "Cannot start bench because one or more dev ports are still busy."
  maybe_add_missing_hosts
  cd "$BENCH_DIR"
  nohup setsid bench start >"$log_file" 2>&1 &
  printf '%s\n' "$!" >"$pidfile"
  sleep 3
  local pid
  pid="$(tr -d '[:space:]' 2>/dev/null <"$pidfile" || true)"
  if is_process_in_bench "$pid"; then
    info "PID: $pid"
  else
    warn "bench start process exited quickly. Check log: $log_file"
    rm -f "$pidfile" 2>/dev/null || true
    cleanup_stale_pid_files
  fi
  info "Log: $log_file"
  print_urls
  if is_process_in_bench "$pid"; then
    validate_sites_after_start
  fi
  info "Stop command: ./scripts/core/start.sh --stop"
}

main() {
  parse_args "$@"
  info "Development/local runner only. This is not production service management."
  verify_environment
  verify_bench
  list_sites

  if [[ "$STOP" -eq 1 ]]; then
    stop_bench
    exit 0
  fi
  if [[ "$STATUS" -eq 1 ]]; then
    show_status
    exit 0
  fi
  if [[ "$SMOKE" -eq 1 ]]; then
    if run_smoke; then
      exit 0
    fi
    exit 1
  fi

  require_sites_for_start
  select_all_sites
  if [[ "$BACKGROUND" -eq 1 ]]; then
    start_background
  else
    start_foreground
  fi
}

main "$@"
