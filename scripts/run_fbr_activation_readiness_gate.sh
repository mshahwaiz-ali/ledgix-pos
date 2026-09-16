#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
REQUIRE_SANDBOX_READY=0
REQUIRE_SANDBOX_PROOF=0
REQUIRE_PRODUCTION_READY=0
REQUIRE_RETURN_PROOF=0
MAX_BACKUP_AGE_HOURS=24
TEMP_REDIS_STARTED=0
APP="ledgix_saas"

usage() {
  cat <<'EOF'
Usage: scripts/run_fbr_activation_readiness_gate.sh [SITE] [options]

Read-only FBR Sandbox -> Production activation readiness audit for a local /
integration site. This command makes NO FBR network call and NEVER arms
Production posting. It records a private non-secret readiness snapshot.

Options:
  --require-sandbox-ready       Exit non-zero unless Sandbox configuration is ready
  --require-sandbox-proof       Exit non-zero unless required Sandbox validate+POST evidence exists
  --require-production-ready    Exit non-zero unless Production switch prerequisites are green
  --require-return-proof        Require Sandbox Credit Note/return validate+POST evidence
  --max-backup-age-hours N      Fresh-backup window for Production readiness (default: 24)
  --help, -h                    Show this help
EOF
}

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
pass() { printf '[PASS] %s\n' "$*"; }

cleanup() {
  if [[ "$TEMP_REDIS_STARTED" -eq 1 && -f "$REPO_ROOT/deploy/bench_redis.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" stop || true
  fi
}
trap cleanup EXIT

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
    --require-sandbox-ready) REQUIRE_SANDBOX_READY=1; shift ;;
    --require-sandbox-proof) REQUIRE_SANDBOX_PROOF=1; shift ;;
    --require-production-ready) REQUIRE_PRODUCTION_READY=1; shift ;;
    --require-return-proof) REQUIRE_RETURN_PROOF=1; shift ;;
    --max-backup-age-hours)
      [[ $# -ge 2 ]] || fail '--max-backup-age-hours requires a value'
      MAX_BACKUP_AGE_HOURS="$2"
      shift 2
      ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) fail "FBR integration readiness gate exact-syncs only local/integration sites; refusing: $SITE" ;;
esac
[[ "$MAX_BACKUP_AGE_HOURS" =~ ^[0-9]+$ ]] || fail '--max-backup-age-hours must be an integer'
[[ "$MAX_BACKUP_AGE_HOURS" -ge 1 && "$MAX_BACKUP_AGE_HOURS" -le 168 ]] || fail '--max-backup-age-hours must be between 1 and 168'
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site not found: $SITE"
[[ -x "$BENCH_DIR/env/bin/python" ]] || fail "bench Python missing: $BENCH_DIR/env/bin/python"
[[ -d "$REPO_ROOT/apps/$APP" ]] || fail 'repository Ledgix app missing'

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

parse_field() {
  local field="$1"
  "$BENCH_DIR/env/bin/python" -c '
import ast
import json
import sys
field=sys.argv[1]
value=None
for line in reversed([x.strip() for x in sys.stdin.read().splitlines() if x.strip()]):
    for loader in (json.loads, ast.literal_eval):
        try:
            obj=loader(line)
        except Exception:
            continue
        if isinstance(obj, dict) and "sandbox_ready" in obj:
            value=obj
            break
    if value is not None:
        break
if value is None:
    raise SystemExit("could not parse FBR readiness result")
print("1" if value.get(field) else "0")
' "$field"
}

printf '==================================================\n'
printf ' Ledgix FBR Sandbox -> Production Readiness Gate\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf 'Require Sandbox ready: %s\n' "$REQUIRE_SANDBOX_READY"
printf 'Require Sandbox proof: %s\n' "$REQUIRE_SANDBOX_PROOF"
printf 'Require Production ready: %s\n' "$REQUIRE_PRODUCTION_READY"
printf 'Require return proof: %s\n' "$REQUIRE_RETURN_PROOF"
printf 'Fresh backup window (hours): %s\n' "$MAX_BACKUP_AGE_HOURS"

printf '\n===== STATIC FBR ACTIVATION CONTRACT =====\n'
bash "$SCRIPT_DIR/run_fbr_activation_static_gate.sh"

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.fbr-activation.$$"
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$REPO_ROOT/deploy/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/repair_apps_txt.sh"
fi
[[ -f "$DEST_APP/api/fbr_activation.py" ]] || fail 'bench app is missing FBR activation service after sync'
pass 'bench Ledgix code matches repository source'

printf '\n===== RUNTIME DEPENDENCIES =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" start
TEMP_REDIS_STARTED=1
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"
bash "$REPO_ROOT/deploy/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== FBR ACTIVATION READINESS EVIDENCE =====\n'
RELEASE_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
KWARGS_JSON="$($BENCH_DIR/env/bin/python - "$RELEASE_SHA" "$REQUIRE_RETURN_PROOF" "$MAX_BACKUP_AGE_HOURS" <<'PY'
import json
import sys
print(json.dumps({
    "release_sha": sys.argv[1],
    "operator": "fbr-activation-readiness-gate",
    "require_return_proof": int(sys.argv[2]),
    "max_backup_age_hours": int(sys.argv[3]),
}))
PY
)"
READINESS_OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.api.fbr_activation.generate_fbr_activation_evidence --kwargs "$KWARGS_JSON")"
printf '%s\n' "$READINESS_OUTPUT"

SANDBOX_READY="$(parse_field sandbox_ready <<<"$READINESS_OUTPUT")"
SANDBOX_PROVEN="$(parse_field sandbox_proven <<<"$READINESS_OUTPUT")"
PRODUCTION_READY="$(parse_field production_switch_ready <<<"$READINESS_OUTPUT")"

printf 'fbr_sandbox_ready=%s\n' "$([[ "$SANDBOX_READY" == "1" ]] && printf true || printf false)"
printf 'fbr_sandbox_proven=%s\n' "$([[ "$SANDBOX_PROVEN" == "1" ]] && printf true || printf false)"
printf 'fbr_production_switch_ready=%s\n' "$([[ "$PRODUCTION_READY" == "1" ]] && printf true || printf false)"

if [[ "$REQUIRE_SANDBOX_READY" -eq 1 && "$SANDBOX_READY" != "1" ]]; then
  fail 'Sandbox configuration is not ready'
fi
if [[ "$REQUIRE_SANDBOX_PROOF" -eq 1 && "$SANDBOX_PROVEN" != "1" ]]; then
  fail 'required Sandbox validation/POST proof is incomplete'
fi
if [[ "$REQUIRE_PRODUCTION_READY" -eq 1 && "$PRODUCTION_READY" != "1" ]]; then
  fail 'Production switch prerequisites are not green'
fi

printf '\n===== FBR READINESS VERDICT =====\n'
printf '[PASS] activation audit made no FBR network call\n'
printf '[PASS] Production posting was not armed by this gate\n'
printf '[PASS] private non-secret FBR readiness evidence written\n'
printf 'fbr_readiness_evaluation_complete=true\n'
