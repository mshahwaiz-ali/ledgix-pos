#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE=""
URL=""
RELEASE=""
REQUIRE_FBR=0

usage() {
  cat <<'EOF'
Usage: scripts/run_ledgix_production_release_gate.sh \
  --site SITE --url https://client.example.com --release <full-sha-or-immutable-tag> \
  [--require-fbr-production]

Audit-only final production acceptance gate. It does not checkout/sync/deploy
code, does not submit anything to FBR, and does not arm Production. Deploy/update
must already have completed through the approved deployment tooling.
EOF
}
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) [[ $# -ge 2 ]] || fail '--site requires a value'; SITE="$2"; shift 2 ;;
    --url) [[ $# -ge 2 ]] || fail '--url requires a value'; URL="${2%/}"; shift 2 ;;
    --release) [[ $# -ge 2 ]] || fail '--release requires a value'; RELEASE="$2"; shift 2 ;;
    --require-fbr-production) REQUIRE_FBR=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ -n "$SITE" && -n "$URL" && -n "$RELEASE" ]] || { usage; fail '--site, --url and --release are required'; }
[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
[[ "$URL" =~ ^https://[^[:space:]]+$ ]] || fail '--url must be an https URL'
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site not found: $SITE"
[[ -x "$BENCH_DIR/env/bin/python" ]] || fail "bench Python missing"

if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]]; then
  fail 'repository must be clean for final production acceptance'
fi

git -C "$REPO_ROOT" fetch --tags origin >/dev/null 2>&1 || fail 'could not refresh immutable release refs'
if [[ "$RELEASE" =~ ^[0-9a-fA-F]{40}$ ]]; then
  TARGET_SHA="$(git -C "$REPO_ROOT" rev-parse "$RELEASE^{commit}" 2>/dev/null || true)"
else
  if ! git -C "$REPO_ROOT" show-ref --verify --quiet "refs/tags/$RELEASE"; then
    fail 'release must be a full 40-character commit SHA or immutable tag; moving branch names are not accepted'
  fi
  TARGET_SHA="$(git -C "$REPO_ROOT" rev-parse "refs/tags/$RELEASE^{commit}")"
fi
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'release could not be resolved to a commit'
HEAD_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$HEAD_SHA" == "$TARGET_SHA" ]] || fail "deployed repository HEAD $HEAD_SHA does not equal approved release $TARGET_SHA"

bench_run() { (cd "$BENCH_DIR" && bench "$@"); }
parse_ready() {
  "$BENCH_DIR/env/bin/python" -c '
import ast,json,sys
obj=None
for line in reversed([x.strip() for x in sys.stdin.read().splitlines() if x.strip()]):
    for loader in (json.loads, ast.literal_eval):
        try: value=loader(line)
        except Exception: continue
        if isinstance(value, dict) and "production_release_ready" in value:
            obj=value; break
    if obj is not None: break
if obj is None: raise SystemExit("could not parse production acceptance result")
print("1" if obj.get("production_release_ready") else "0")
'
}

printf '==================================================\n'
printf ' Ledgix Final Production Release Gate\n'
printf '==================================================\n'
printf 'Site: %s\nURL: %s\nApproved release: %s\nRequire FBR Production: %s\n' "$SITE" "$URL" "$TARGET_SHA" "$REQUIRE_FBR"

printf '\n===== CLIENT PREFLIGHT =====\n'
BENCH_DIR="$BENCH_DIR" bash "$SCRIPT_DIR/run_ledgix_client_preflight.sh" "$SITE"

printf '\n===== OFFLINE + ONLINE SMOKE =====\n'
bash "$REPO_ROOT/deploy/smoke_test.sh" --site "$SITE" --bench-dir "$BENCH_DIR" --all --url "$URL"

printf '\n===== STRICT RELEASE ACCEPTANCE =====\n'
KWARGS="$($BENCH_DIR/env/bin/python -c 'import json,sys; print(json.dumps({"release_sha":sys.argv[1],"operator":"production-release-gate","require_fbr_certification":int(sys.argv[2])}))' "$TARGET_SHA" "$REQUIRE_FBR")"
OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.api.release_acceptance.generate_release_acceptance_evidence --kwargs "$KWARGS")"
printf '%s\n' "$OUTPUT"
READY="$(printf '%s\n' "$OUTPUT" | parse_ready)"
[[ "$READY" == "1" ]] || fail 'final production acceptance is not green; review manual UAT, backup/release evidence and requested FBR certification'

printf '\n===== FINAL RELEASE VERDICT =====\n'
printf '[PASS] immutable deployed release identity matches approval\n'
printf '[PASS] dependency preflight and online/offline smoke are green\n'
printf '[PASS] Phase 12 historical snapshot remains frozen and matched read-only\n'
printf '[PASS] profile-specific manual UAT evidence is complete\n'
printf '[PASS] strict release/backup evidence is complete\n'
printf '[PASS] requested FBR production prerequisite is satisfied without this gate making an FBR call\n'
printf 'ledgix_production_release_gate_complete=true\n'
