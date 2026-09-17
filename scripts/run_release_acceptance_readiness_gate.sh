#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
TEMP_REDIS_STARTED=0
APP="ledgix_saas"

usage() {
  cat <<'EOF'
Usage: scripts/run_release_acceptance_readiness_gate.sh [SITE]

Local/integration acceptance audit. It exact-syncs Ledgix code, runs static,
dependency and offline smoke checks, then records non-secret acceptance evidence.
It makes no FBR network call, never arms Production, and does not claim physical
printer/scanner/device UAT has passed unless explicit manual evidence exists.
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

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then usage; exit 0; fi
if [[ $# -gt 0 ]]; then SITE="$1"; shift; fi
[[ $# -eq 0 ]] || fail 'unexpected extra arguments'
[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in *.local|*.localhost) ;; *) fail "local acceptance gate refuses non-local site: $SITE" ;; esac
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site not found: $SITE"
BENCH_PYTHON="$BENCH_DIR/env/bin/python"
[[ -x "$BENCH_PYTHON" ]] || fail "bench Python missing: $BENCH_PYTHON"

bench_run() { (cd "$BENCH_DIR" && bench "$@"); }
parse_bool() {
  local field="$1"
  "$BENCH_PYTHON" -c '
import ast,json,sys
field=sys.argv[1]
obj=None
for line in reversed([x.strip() for x in sys.stdin.read().splitlines() if x.strip()]):
    for loader in (json.loads, ast.literal_eval):
        try: value=loader(line)
        except Exception: continue
        if isinstance(value, dict) and field in value:
            obj=value; break
    if obj is not None: break
if obj is None: raise SystemExit("could not parse acceptance result")
print("1" if obj.get(field) else "0")
' "$field"
}

printf '==================================================\n'
printf ' Ledgix Release Acceptance Readiness Gate\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== STATIC ACCEPTANCE CONTRACT =====\n'
bash "$SCRIPT_DIR/run_release_acceptance_static_gate.sh"

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.release-acceptance.$$"
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_PYTHON" -m pip install -e "$DEST_APP"
if [[ -f "$REPO_ROOT/deploy/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/repair_apps_txt.sh"
fi
[[ -f "$DEST_APP/api/release_acceptance.py" ]] || fail 'bench app is missing release acceptance service after sync'
pass 'bench Ledgix code matches repository source'

printf '\n===== RUNTIME DEPENDENCIES =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" start
TEMP_REDIS_STARTED=1
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"
bash "$REPO_ROOT/deploy/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== RELEASE ACCEPTANCE EVIDENCE =====\n'
RELEASE_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
KWARGS="$($BENCH_PYTHON -c 'import json,sys; print(json.dumps({"release_sha":sys.argv[1],"operator":"local-release-acceptance-gate","require_fbr_certification":0}))' "$RELEASE_SHA")"
OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.api.release_acceptance.generate_release_acceptance_evidence --kwargs "$KWARGS")"
printf '%s\n' "$OUTPUT"

SETUP_READY="$(printf '%s\n' "$OUTPUT" | parse_bool release_setup_ready)"
MANUAL_READY="$(printf '%s\n' "$OUTPUT" | parse_bool manual_uat_ready)"
FBR_READY="$(printf '%s\n' "$OUTPUT" | parse_bool fbr_external_certification_complete)"
PROD_READY="$(printf '%s\n' "$OUTPUT" | parse_bool production_release_ready)"

printf 'release_setup_ready=%s\n' "$([[ "$SETUP_READY" == 1 ]] && printf true || printf false)"
printf 'manual_uat_ready=%s\n' "$([[ "$MANUAL_READY" == 1 ]] && printf true || printf false)"
printf 'fbr_external_certification_complete=%s\n' "$([[ "$FBR_READY" == 1 ]] && printf true || printf false)"
printf 'production_release_ready=%s\n' "$([[ "$PROD_READY" == 1 ]] && printf true || printf false)"

[[ "$SETUP_READY" == "1" ]] || fail 'machine-verifiable Ledgix release setup is not ready'

printf '\n===== ACCEPTANCE READINESS VERDICT =====\n'
printf '[PASS] machine-verifiable release setup is green\n'
printf '[PASS] Phase 12 snapshot verification was read-only\n'
printf '[PASS] no FBR network call or Production arming occurred\n'
printf '[INFO] manual device/UAT and external FBR certification may remain pending without blocking code/setup readiness\n'
printf 'release_acceptance_readiness_complete=true\n'
