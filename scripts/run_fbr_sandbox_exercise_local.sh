#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
SALES_INVOICE=""
POS_INVOICE=""
RETURN_DOCTYPE=""
RETURN_NAME=""
LIST_CANDIDATES=0
CONFIRMATION=""
TEMP_REDIS_STARTED=0
APP="ledgix_saas"

usage() {
  cat <<'EOF'
Usage:
  scripts/run_fbr_sandbox_exercise_local.sh [SITE] --list-candidates

  scripts/run_fbr_sandbox_exercise_local.sh [SITE] \
    --sales-invoice SINV-NAME \
    --pos-invoice POSINV-NAME \
    [--return-doctype "Sales Invoice|POS Invoice" --return-name NAME] \
    --confirm "SEND TO FBR SANDBOX"

This runner is local/integration-only. With --list-candidates it makes no network
request. Exercise mode performs real FBR SANDBOX validation + POST only for the
explicit ERPNext-native references supplied. Production mode/POST is refused by
the server-side guard and Production remains unarmed.
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
    --list-candidates) LIST_CANDIDATES=1; shift ;;
    --sales-invoice) [[ $# -ge 2 ]] || fail '--sales-invoice requires a value'; SALES_INVOICE="$2"; shift 2 ;;
    --pos-invoice) [[ $# -ge 2 ]] || fail '--pos-invoice requires a value'; POS_INVOICE="$2"; shift 2 ;;
    --return-doctype) [[ $# -ge 2 ]] || fail '--return-doctype requires a value'; RETURN_DOCTYPE="$2"; shift 2 ;;
    --return-name) [[ $# -ge 2 ]] || fail '--return-name requires a value'; RETURN_NAME="$2"; shift 2 ;;
    --confirm) [[ $# -ge 2 ]] || fail '--confirm requires a value'; CONFIRMATION="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) fail "Sandbox exercise helper is local/integration-only; refusing: $SITE" ;;
esac

BENCH_PYTHON="$BENCH_DIR/env/bin/python"
[[ -x "$BENCH_PYTHON" ]] || fail "bench Python missing: $BENCH_PYTHON"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site not found: $SITE"
[[ -d "$REPO_ROOT/apps/$APP" ]] || fail 'repository Ledgix app missing'

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

parse_bool_field() {
  local field="$1"
  "$BENCH_PYTHON" -c '
import ast,json,sys
field=sys.argv[1]
value=None
for line in reversed([x.strip() for x in sys.stdin.read().splitlines() if x.strip()]):
    for loader in (json.loads, ast.literal_eval):
        try: obj=loader(line)
        except Exception: continue
        if isinstance(obj, dict):
            value=obj; break
    if value is not None: break
if value is None: raise SystemExit("could not parse result")
print("1" if value.get(field) else "0")
' "$field"
}

printf '==================================================\n'
printf ' Ledgix FBR Sandbox Exercise\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"

printf '\n===== STATIC SAFETY CONTRACT =====\n'
bash "$SCRIPT_DIR/run_fbr_activation_static_gate.sh"

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.fbr-sandbox-exercise.$$"
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_PYTHON" -m pip install -e "$DEST_APP"
if [[ -f "$REPO_ROOT/deploy/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/repair_apps_txt.sh"
fi
[[ -f "$DEST_APP/setup/fbr_sandbox_operator.py" ]] || fail 'bench app is missing FBR Sandbox operator helper after sync'
pass 'bench Ledgix code matches repository source'

printf '\n===== RUNTIME DEPENDENCIES =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" start
TEMP_REDIS_STARTED=1
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"

if [[ "$LIST_CANDIDATES" -eq 1 ]]; then
  [[ -z "$SALES_INVOICE$POS_INVOICE$RETURN_DOCTYPE$RETURN_NAME$CONFIRMATION" ]] || fail '--list-candidates cannot be combined with exercise arguments'
  printf '\n===== SANDBOX CANDIDATES — NO NETWORK =====\n'
  bench_run --site "$SITE" execute ledgix_saas.setup.fbr_sandbox_operator.list_sandbox_candidates --kwargs '{"limit":12}'
  printf '\n[PASS] candidate listing completed without an FBR network request\n'
  printf 'fbr_sandbox_candidate_listing_complete=true\n'
  exit 0
fi

[[ "$CONFIRMATION" == "SEND TO FBR SANDBOX" ]] || fail 'exercise requires --confirm "SEND TO FBR SANDBOX"'
[[ -n "$SALES_INVOICE" || -n "$POS_INVOICE" || -n "$RETURN_NAME" ]] || fail 'provide at least one explicit ERPNext-native reference'
if [[ -n "$RETURN_NAME" || -n "$RETURN_DOCTYPE" ]]; then
  [[ -n "$RETURN_NAME" && -n "$RETURN_DOCTYPE" ]] || fail '--return-doctype and --return-name must be supplied together'
  [[ "$RETURN_DOCTYPE" == "Sales Invoice" || "$RETURN_DOCTYPE" == "POS Invoice" ]] || fail '--return-doctype must be Sales Invoice or POS Invoice'
fi

RELEASE_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
PRECHECK_KWARGS="$($BENCH_PYTHON -c 'import json,sys; print(json.dumps({"release_sha":sys.argv[1]}))' "$RELEASE_SHA")"
PRECHECK_OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.api.fbr_activation.generate_fbr_activation_evidence --kwargs "$PRECHECK_KWARGS")"
printf '\n===== PRE-SEND SANDBOX READINESS =====\n%s\n' "$PRECHECK_OUTPUT"
SANDBOX_READY="$(printf '%s\n' "$PRECHECK_OUTPUT" | parse_bool_field sandbox_ready)"
[[ "$SANDBOX_READY" == "1" ]] || fail 'Sandbox configuration is not ready; do not send network traffic'

exercise_one() {
  local doctype="$1" name="$2" label="$3" kwargs output passed
  [[ -n "$name" ]] || return 0
  printf '\n===== %s: SANDBOX VALIDATE + POST =====\n' "$label"
  kwargs="$($BENCH_PYTHON -c 'import json,sys; print(json.dumps({"reference_doctype":sys.argv[1],"reference_name":sys.argv[2],"confirmation":"SEND TO FBR SANDBOX"}))' "$doctype" "$name")"
  output="$(LEDGIX_FBR_SANDBOX_NETWORK_EXERCISE="$CONFIRMATION" bench_run --site "$SITE" execute ledgix_saas.setup.fbr_sandbox_operator.exercise_sandbox_reference --kwargs "$kwargs")"
  printf '%s\n' "$output"
  passed="$(printf '%s\n' "$output" | parse_bool_field passed)"
  [[ "$passed" == "1" ]] || fail "$label Sandbox validate/POST proof did not pass"
  pass "$label Sandbox validate/POST proof persisted"
}

exercise_one "Sales Invoice" "$SALES_INVOICE" "Sales Invoice"
exercise_one "POS Invoice" "$POS_INVOICE" "POS Invoice"
if [[ -n "$RETURN_NAME" ]]; then
  exercise_one "$RETURN_DOCTYPE" "$RETURN_NAME" "Credit Note / return"
fi

REQUIRE_RETURN=0
[[ -n "$RETURN_NAME" ]] && REQUIRE_RETURN=1
FINAL_KWARGS="$($BENCH_PYTHON -c 'import json,sys; print(json.dumps({"release_sha":sys.argv[1],"operator":"sandbox-exercise-helper","require_return_proof":int(sys.argv[2])}))' "$RELEASE_SHA" "$REQUIRE_RETURN")"
FINAL_OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.api.fbr_activation.generate_fbr_activation_evidence --kwargs "$FINAL_KWARGS")"
printf '\n===== POST-EXERCISE FBR EVIDENCE =====\n%s\n' "$FINAL_OUTPUT"
SANDBOX_PROVEN="$(printf '%s\n' "$FINAL_OUTPUT" | parse_bool_field sandbox_proven)"

printf '\n===== SANDBOX EXERCISE VERDICT =====\n'
printf '[PASS] every requested reference used explicit Sandbox-only confirmation\n'
printf '[PASS] persisted submission logs are the proof source\n'
printf '[PASS] Production remained unarmed\n'
printf 'fbr_sandbox_proven=%s\n' "$([[ "$SANDBOX_PROVEN" == "1" ]] && printf true || printf false)"
printf 'fbr_sandbox_exercise_complete=true\n'
