#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
TEMP_REDIS_STARTED=0
INPUT_FILE=""
APP="ledgix_saas"

usage() {
  cat <<'EOF'
Usage: scripts/configure_fbr_sandbox_local.sh [SITE]

Interactive local/integration Sandbox configuration helper.

- seller identity is prompted interactively;
- Sandbox token is read silently and is never a command-line argument;
- plaintext staging JSON is written only under the site's private directory
  with mode 0600 and deleted after Frappe stores the Password field;
- Production credentials are not changed;
- Production posting remains unarmed;
- no FBR network request is made by this command.
EOF
}

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
pass() { printf '[PASS] %s\n' "$*"; }

cleanup() {
  if [[ -n "$INPUT_FILE" ]]; then
    rm -f -- "$INPUT_FILE" 2>/dev/null || true
  fi
  if [[ "$TEMP_REDIS_STARTED" -eq 1 && -f "$REPO_ROOT/deploy/bench_redis.sh" ]]; then
    BENCH_DIR="$BENCH_DIR" bash "$REPO_ROOT/deploy/bench_redis.sh" stop || true
  fi
}
trap cleanup EXIT

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ $# -gt 0 ]]; then
  SITE="$1"
  shift
fi
[[ $# -eq 0 ]] || fail 'unexpected extra arguments'

[[ "$SITE" =~ ^[a-z0-9][a-z0-9.-]*$ ]] || fail "invalid site: $SITE"
case "$SITE" in
  *.local|*.localhost) ;;
  *) fail "Sandbox configuration helper is local/integration-only; refusing: $SITE" ;;
esac

BENCH_PYTHON="$BENCH_DIR/env/bin/python"
[[ -x "$BENCH_PYTHON" ]] || fail "bench Python missing: $BENCH_PYTHON"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site not found: $SITE"
[[ -d "$REPO_ROOT/apps/$APP" ]] || fail 'repository Ledgix app missing'

bench_run() {
  (cd "$BENCH_DIR" && bench "$@")
}

printf '==================================================\n'
printf ' Ledgix FBR Sandbox Configuration\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf '[INFO] This command performs no FBR network request and cannot arm Production.\n'

printf '\n===== STATIC SAFETY CONTRACT =====\n'
bash "$SCRIPT_DIR/run_fbr_activation_static_gate.sh"

printf '\n===== EXACT LEDGIX BENCH APP SYNC =====\n'
SRC_APP="$REPO_ROOT/apps/$APP"
DEST_APP="$BENCH_DIR/apps/$APP"
TMP_APP="$BENCH_DIR/apps/.${APP}.fbr-sandbox-config.$$"
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

printf '\n===== CLIENT SANDBOX INPUT =====\n'
read -r -p 'Seller NTN/CNIC: ' SELLER_NTN_CNIC
read -r -p 'Seller business name: ' SELLER_BUSINESS_NAME
read -r -p 'Seller province: ' SELLER_PROVINCE
read -r -p 'Seller address: ' SELLER_ADDRESS
read -r -p 'Software registration number (optional, press Enter to skip): ' SOFTWARE_REGISTRATION_NUMBER
read -r -s -p 'Sandbox token (hidden): ' SANDBOX_TOKEN
printf '\n'

[[ -n "${SELLER_NTN_CNIC// }" ]] || fail 'Seller NTN/CNIC is required'
[[ -n "${SELLER_BUSINESS_NAME// }" ]] || fail 'Seller business name is required'
[[ -n "${SELLER_PROVINCE// }" ]] || fail 'Seller province is required'
[[ -n "${SELLER_ADDRESS// }" ]] || fail 'Seller address is required'
[[ -n "$SANDBOX_TOKEN" ]] || fail 'Sandbox token is required'

PRIVATE_DIR="$BENCH_DIR/sites/$SITE/private/ledgix-fbr-activation"
mkdir -p "$PRIVATE_DIR"
chmod 700 "$PRIVATE_DIR"
INPUT_FILE="$PRIVATE_DIR/sandbox-config-input.$$.json"

printf '%s\0' \
  "$SELLER_NTN_CNIC" \
  "$SELLER_BUSINESS_NAME" \
  "$SELLER_PROVINCE" \
  "$SELLER_ADDRESS" \
  "$SOFTWARE_REGISTRATION_NUMBER" \
  "$SANDBOX_TOKEN" \
  | "$BENCH_PYTHON" -c '
import json
import os
import sys

path = sys.argv[1]
values = sys.stdin.buffer.read().decode("utf-8").split("\0")
while values and values[-1] == "":
    values.pop()
if len(values) != 6:
    raise SystemExit("invalid sandbox configuration input stream")
keys = [
    "seller_ntn_cnic",
    "seller_business_name",
    "seller_province",
    "seller_address",
    "software_registration_number",
    "sandbox_token",
]
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(dict(zip(keys, values)), handle, ensure_ascii=False)
    handle.write("\n")
' "$INPUT_FILE"
chmod 600 "$INPUT_FILE"

KWARGS_JSON="$($BENCH_PYTHON -c 'import json,sys; print(json.dumps({"config_path":sys.argv[1]}))' "$INPUT_FILE")"
CONFIG_OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.setup.fbr_sandbox_operator.configure_sandbox_from_private_file --kwargs "$KWARGS_JSON")"
printf '%s\n' "$CONFIG_OUTPUT"
rm -f -- "$INPUT_FILE"
INPUT_FILE=""

RELEASE_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD)"
READINESS_KWARGS="$($BENCH_PYTHON -c 'import json,sys; print(json.dumps({"release_sha":sys.argv[1],"operator":"sandbox-config-helper"}))' "$RELEASE_SHA")"
READINESS_OUTPUT="$(bench_run --site "$SITE" execute ledgix_saas.api.fbr_activation.generate_fbr_activation_evidence --kwargs "$READINESS_KWARGS")"
printf '%s\n' "$READINESS_OUTPUT"

SANDBOX_READY="$(printf '%s\n' "$READINESS_OUTPUT" | "$BENCH_PYTHON" -c '
import ast,json,sys
value=None
for line in reversed([x.strip() for x in sys.stdin.read().splitlines() if x.strip()]):
    for loader in (json.loads, ast.literal_eval):
        try: obj=loader(line)
        except Exception: continue
        if isinstance(obj, dict) and "sandbox_ready" in obj:
            value=obj; break
    if value is not None: break
if value is None: raise SystemExit("could not parse Sandbox readiness result")
print("1" if value.get("sandbox_ready") else "0")
')"
[[ "$SANDBOX_READY" == "1" ]] || fail 'Sandbox settings were saved but Sandbox readiness is still blocked; review the evidence above'

printf '\n===== SANDBOX CONFIGURATION VERDICT =====\n'
printf '[PASS] seller identity stored\n'
printf '[PASS] Sandbox token stored through Frappe Password handling\n'
printf '[PASS] plaintext staging file removed\n'
printf '[PASS] Sandbox mode enabled with Manual trigger\n'
printf '[PASS] Production remains unarmed and Production credentials were not changed\n'
printf '[PASS] no FBR network request was made\n'
printf 'fbr_sandbox_configuration_complete=true\n'
