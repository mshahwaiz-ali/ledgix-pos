#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$REPO_ROOT/frappe-bench}"
SITE="${LEDGIX_LOCAL_SITE:-ledgix-erpnext.local}"
BENCH_PYTHON="$BENCH_DIR/env/bin/python"

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

if [[ $# -gt 0 && "${1:-}" != --* ]]; then SITE="$1"; shift; fi
[[ $# -eq 0 ]] || fail "unexpected arguments"
case "$SITE" in *.local|*.localhost) ;; *) fail "local/integration-only: $SITE" ;; esac
[[ -x "$BENCH_PYTHON" ]] || fail "bench Python missing"
[[ -f "$BENCH_DIR/sites/$SITE/site_config.json" ]] || fail "site missing"

printf '==================================================\n'
printf ' Ledgix FBR Client-Certification Handoff Gate\n'
printf '==================================================\n'
printf 'Site: %s\n' "$SITE"
printf 'Commit: %s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD)"
printf '[INFO] Read-only: no FBR network, no token decryption, no DB writes, no Production arm.\n'

bash "$SCRIPT_DIR/run_fbr_redesign_static_gate.sh"
bash "$SCRIPT_DIR/run_fbr_activation_static_gate.sh"

PYTHONPATH="$REPO_ROOT/apps${PYTHONPATH:+:$PYTHONPATH}" \
"$BENCH_PYTHON" -m unittest -v \
  ledgix_saas.setup.test_fbr_client_certification_handoff_contract

cd "$BENCH_DIR/sites"
FRAPPE_STREAM_LOGGING=1 \
PYTHONPATH="$REPO_ROOT/apps:$BENCH_DIR/apps${PYTHONPATH:+:$PYTHONPATH}" \
"$BENCH_PYTHON" - "$BENCH_DIR" "$SITE" <<'PY'
import json
import sys
from pathlib import Path

bench = Path(sys.argv[1])
site = sys.argv[2]

import frappe
frappe.init(site=site, sites_path=str(bench / "sites"))
frappe.connect()

from ledgix_saas.api import fbr_native
from ledgix_saas.api.fbr_offline import list_offline_queue_internal
from ledgix_saas.services import erpnext_fbr_identity

def count(dt, filters=None):
    return int(frappe.db.count(dt, filters or {}))

try:
    meta = frappe.get_meta("Ledgix FBR Integration Profile")
    logo = meta.get_field("digital_invoicing_logo")
    if not logo or logo.fieldtype != "Attach Image":
        raise AssertionError("DI-logo field missing")
    if fbr_native.V2_NETWORK_CUTOVER_ACTIVE is not False:
        raise AssertionError("global V2 cutover must remain false")

    profiles = frappe.get_all(
        "Ledgix FBR Integration Profile",
        fields=["name","company","enabled","mode","production_post_armed","offline_policy","offline_upload_window_hours","reference_sync_status","onboarding_status"],
        order_by="name",
        limit_page_length=0,
    )
    external = []
    for row in profiles:
        seller = erpnext_fbr_identity.resolve_company_seller_identity(row.get("company") or "")
        if not seller.get("ready"):
            external.append({"key":"seller_identity","company":row.get("company") or "","missing":list(seller.get("errors") or [])})

    needs_review = count("Ledgix FBR Item Mapping", {"active":1,"needs_review":1})
    if needs_review:
        external.append({"key":"mapping_review","count":needs_review})
    refs = count("Ledgix FBR Reference Data", {"active":1})
    if not refs:
        external.append({"key":"official_reference_cache","count":0})
    cert = count("Ledgix FBR Sandbox Certification", {"status":"Complete","evidence_complete":1})
    if not cert:
        external.append({"key":"real_sandbox_certification","count":0})

    queue = list_offline_queue_internal()
    print(json.dumps({
        "software_ready_for_client_certification": True,
        "sandbox_certified": False,
        "production_ready": False,
        "offline_queue_count": queue.get("count") or 0,
        "external_client_certification_blockers": external,
        "database_write": False,
        "fbr_network_call": False,
        "token_values_accessed": False,
        "contains_secrets": False,
    }, indent=2, sort_keys=True, default=str))
finally:
    frappe.db.rollback()
    frappe.destroy()
PY

printf 'software_ready_for_client_certification=true\n'
printf 'sandbox_certified=false\n'
printf 'production_ready=false\n'
printf 'fbr_client_certification_handoff_gate_complete=true\n'
