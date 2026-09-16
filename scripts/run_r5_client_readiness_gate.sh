#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
SITE_URL=""
REQUIRE_READY=0
STRICT_EVIDENCE=0
APPLY_SETUP=0
TEMP_REDIS_STARTED=0
APP="ledgix_saas"

usage() {
  cat <<'EOF'
Usage: scripts/run_r5_client_readiness_gate.sh [SITE] [options]

Evaluates R5 client onboarding/readiness on the canonical local/integration site.
The gate never creates ERPNext business masters or activates FBR Production. It
writes a private non-secret readiness evidence snapshot under the target site's
private folder.

Options:
  --url URL           Optional site URL to record in evidence
  --strict-evidence   Treat missing release/backup evidence as blockers
  --apply-setup       If the only blocker is the unapplied Ledgix setup marker,
                      apply the already-resolved Business Profile/configuration
                      and re-evaluate readiness
  --require-ready     Exit non-zero if any blocking readiness check remains
  --help, -h          Show this help
EOF
}

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
pass() { printf '[PASS] %s\n' "$*"; }
info() { printf '[INFO] %s\n' "$*"; }

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
    --url) [[ $# -ge 2 ]] || fail '--url requires a value'; SITE_URL="${2%/}"; shift 2 ;;
    --strict-evidence) STRICT_EVIDENCE=1; shift ;;
    --apply-setup) APPLY_SETUP=1; shift ;;
    --require-ready) REQUIRE_READY=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) fail "R5 integration gate only exact-syncs code on local/integration sites; refusing: $SITE" ;;
esac
if [[ -n "$SITE_URL" ]]; then
  [[ "$SITE_URL" =~ ^https?://[^[:space:]]+$ ]] || fail "invalid --url: $SITE_URL"
fi
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site not found: $SITE"
[[ -x "$BENCH_DIR/env/bin/python" ]] || fail "bench Python missing: $BENCH_DIR/env/bin/python"
[[ -d "$REPO_ROOT/apps/$APP" ]] || fail "repository Ledgix app missing"

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

parse_readiness_field() {
  local field="$1"
  "$BENCH_DIR/env/bin/python" - "$field" <<'PY'
import ast
import json
import sys

field = sys.argv[1]
lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
value = None
for line in reversed(lines):
    for loader in (json.loads, ast.literal_eval):
        try:
            obj = loader(line)
        except Exception:
            continue
        if isinstance(obj, dict) and "ready" in obj:
            value = obj
            break
    if value is not None:
        break
if value is None:
    raise SystemExit("could not parse readiness result")
if field == "ready":
    print("1" if value.get("ready") else "0")
elif field == "apply_kwargs":
    blockers = [row.get("key") for row in value.get("blockers", [])]
    current_ok = any(
        row.get("key") == "client_setup_current_readiness" and row.get("passed")
        for row in value.get("checks", [])
    )
    if blockers != ["client_setup_applied"] or not current_ok:
        raise SystemExit(3)
    resolved = value.get("resolved") or {}
    payload = {
        "business_profile": value.get("business_profile") or "",
        "company": resolved.get("company") or "",
        "selling_price_list": resolved.get("selling_price_list") or "",
        "warehouse": resolved.get("warehouse") or "",
        "pos_profile": resolved.get("pos_profile") or "",
        "apply_standard_defaults": 1,
    }
    print(json.dumps({"payload": payload}, separators=(",", ":")))
else:
    raise SystemExit(f"unknown readiness field: {field}")
PY
}

generate_readiness() {
  local release_sha kwargs_json
  release_sha="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  kwargs_json="$($BENCH_DIR/env/bin/python - "$release_sha" "$SITE_URL" "$STRICT_EVIDENCE" <<'PY'
import json
import sys
print(json.dumps({
    "release_sha": sys.argv[1],
    "site_url": sys.argv[2],
    "operator": "r5-runtime-gate",
    "strict_evidence": int(sys.argv[3]),
}))
PY
)"
  bench_run --site "$SITE" execute ledgix_saas.api.client_readiness.generate_client_readiness_evidence --kwargs "$kwargs_json"
}

printf '==================================================\n'
printf ' Ledgix R5 Client Readiness Gate\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf 'Strict evidence: %s\n' "$STRICT_EVIDENCE"
printf 'Apply setup: %s\n' "$APPLY_SETUP"
printf 'Require ready: %s\n' "$REQUIRE_READY"

printf '\n===== STATIC R5 CONTRACT =====\n'
bash "$SCRIPT_DIR/run_r5_static_gate.sh"

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.r5-sync.$$"
rm -rf "$TMP_APP"
cp -a "$SRC_APP" "$TMP_APP"
rm -rf "$DEST_APP"
mv "$TMP_APP" "$DEST_APP"
"$BENCH_DIR/env/bin/python" -m pip install -e "$DEST_APP"
if [[ -f "$REPO_ROOT/deploy/repair_apps_txt.sh" ]]; then
  BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/repair_apps_txt.sh"
fi
[[ -f "$DEST_APP/api/client_readiness.py" ]] || fail 'bench app is missing R5 readiness service after sync'
pass 'bench Ledgix code matches repository source'

printf '\n===== RUNTIME DEPENDENCIES =====\n'
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" start
TEMP_REDIS_STARTED=1
BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/scripts/run_ledgix_client_preflight.sh" "$SITE"
bash "$REPO_ROOT/deploy/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --offline

printf '\n===== CLIENT READINESS EVIDENCE =====\n'
READINESS_OUTPUT="$(generate_readiness)"
printf '%s\n' "$READINESS_OUTPUT"
READY="$(parse_readiness_field ready <<<"$READINESS_OUTPUT")"

if [[ "$APPLY_SETUP" -eq 1 && "$READY" != "1" ]]; then
  printf '\n===== APPLY EXISTING LEDGIX SETUP CONFIGURATION =====\n'
  set +e
  APPLY_KWARGS="$(parse_readiness_field apply_kwargs <<<"$READINESS_OUTPUT")"
  APPLY_RC=$?
  set -e
  if [[ "$APPLY_RC" -eq 3 ]]; then
    fail '--apply-setup refused: client_setup_applied is not the sole blocker or current setup prerequisites are not green'
  elif [[ "$APPLY_RC" -ne 0 || -z "$APPLY_KWARGS" ]]; then
    fail 'could not derive safe existing setup payload from readiness evidence'
  fi

  bench_run --site "$SITE" execute ledgix_saas.api.client_setup.apply_client_setup --kwargs "$APPLY_KWARGS"
  pass 'existing Business Profile and resolved ERPNext configuration applied; no business masters were created by R5'

  printf '\n===== POST-APPLY CLIENT READINESS EVIDENCE =====\n'
  READINESS_OUTPUT="$(generate_readiness)"
  printf '%s\n' "$READINESS_OUTPUT"
  READY="$(parse_readiness_field ready <<<"$READINESS_OUTPUT")"
fi

if [[ "$READY" == "1" ]]; then
  pass 'client onboarding has no blocking readiness checks'
  printf 'r5_client_ready=true\n'
else
  printf '[INFO] client onboarding still has blocking checks; review the JSON above and resolve them before production acceptance.\n'
  printf 'r5_client_ready=false\n'
fi

if [[ "$REQUIRE_READY" -eq 1 && "$READY" != "1" ]]; then
  fail 'client is not yet operationally ready'
fi

printf '\n===== R5 RUNTIME VERDICT =====\n'
printf '[PASS] dependency preflight and offline smoke completed\n'
printf '[PASS] profile-specific operational readiness evaluated\n'
printf '[PASS] private non-secret readiness evidence written\n'
if [[ "$APPLY_SETUP" -eq 1 ]]; then
  printf '[PASS] setup apply was limited to the existing resolved profile/configuration and re-evaluated\n'
fi
printf 'r5_readiness_evaluation_complete=true\n'