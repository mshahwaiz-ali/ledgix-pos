from __future__ import annotations

"""Final client acceptance over the completed ERPNext-backed Ledgix product.

This service does not submit to FBR, arm Production, create business masters, or
modify ERPNext transactions. It combines machine-verifiable setup/print/freeze
checks with explicit manual UAT evidence retained under the site private tree.
"""

import json
import os
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from ledgix_saas.api import client_readiness, fbr_activation
from ledgix_saas.setup.phase12_read_only import verify_frozen_snapshot_read_only

ACCEPTANCE_SCHEMA_VERSION = 1
ADMIN_ROLES = {"System Manager", "Ledgix Admin"}
MANUAL_UAT_CONFIRMATION = "RECORD LEDGIX MANUAL UAT"
A4_PRINT_FORMAT = "Ledgix ERPNext Tax Invoice"
POS_PRINT_FORMAT = "Ledgix ERPNext POS Receipt"
BASE_UAT_KEYS = (
    "sales_invoice_a4",
    "role_boundary",
)
POS_UAT_KEYS = (
    "pos_thermal_receipt",
    "barcode_item_selection",
    "checkout_payment",
    "pos_return",
    "pos_closing",
    "stock_effect",
    "cashier_device_login",
)
BUYING_UAT_KEYS = (
    "purchase_receipt_valuation",
    "stock_entry_reconciliation",
)


def _require_admin() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(ADMIN_ROLES):
        frappe.throw(_("Release acceptance requires Ledgix Admin or System Manager access."), frappe.PermissionError)


def _check(key: str, passed: bool, message: str, *, category: str, details: dict | None = None) -> dict:
    return {
        "key": key,
        "passed": bool(passed),
        "blocking": True,
        "category": category,
        "message": message,
        "details": details or {},
    }


def _required_uat_keys(features: dict) -> list[str]:
    keys = list(BASE_UAT_KEYS)
    if features.get("enable_pos"):
        keys.extend(POS_UAT_KEYS)
    if features.get("enable_buying"):
        keys.extend(BUYING_UAT_KEYS)
    return keys


def _print_format_state(name: str, doctype: str) -> dict:
    exists = bool(frappe.db.exists("Print Format", name))
    if not exists:
        return {"name": name, "doctype": doctype, "exists": False, "enabled": False, "native": False}
    row = frappe.db.get_value(
        "Print Format",
        name,
        ["doc_type", "disabled", "html"],
        as_dict=True,
    ) or {}
    html = str(row.get("html") or "")
    return {
        "name": name,
        "doctype": row.get("doc_type") or "",
        "exists": True,
        "enabled": not bool(cint(row.get("disabled"))),
        "native": row.get("doc_type") == doctype and "get_native_invoice_print_context" in html and "Ledgix Sale" not in html,
        "has_fbr_reference": "fbr_invoice_number" in html,
        "has_qr": "fbr_qr_data_uri" in html,
    }


def _print_checks(features: dict) -> tuple[list[dict], dict]:
    a4 = _print_format_state(A4_PRINT_FORMAT, "Sales Invoice")
    states = {"sales_invoice_a4": a4}
    checks = [
        _check(
            "native_sales_invoice_print",
            a4["exists"] and a4["enabled"] and a4["native"],
            "Native ERPNext Sales Invoice A4 print format must be installed and enabled.",
            category="Printing",
            details=a4,
        ),
        _check(
            "a4_fbr_reference_surface",
            bool(a4.get("has_fbr_reference") and a4.get("has_qr")),
            "A4 print must support persisted FBR reference and QR rendering.",
            category="Printing",
            details=a4,
        ),
    ]
    if features.get("enable_pos"):
        pos = _print_format_state(POS_PRINT_FORMAT, "POS Invoice")
        states["pos_thermal"] = pos
        checks.extend(
            [
                _check(
                    "native_pos_print",
                    pos["exists"] and pos["enabled"] and pos["native"],
                    "Native ERPNext POS Invoice thermal print format must be installed and enabled.",
                    category="Printing",
                    details=pos,
                ),
                _check(
                    "pos_fbr_reference_surface",
                    bool(pos.get("has_fbr_reference") and pos.get("has_qr")),
                    "POS receipt must support persisted FBR reference and QR rendering.",
                    category="Printing",
                    details=pos,
                ),
            ]
        )
    return checks, states


def _acceptance_dir() -> Path:
    path = Path(frappe.get_site_path("private", "ledgix-acceptance"))
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _manual_uat_path() -> Path:
    return Path(frappe.get_site_path("private", "ledgix-acceptance", "manual-uat.json"))


def _load_manual_uat() -> dict:
    path = _manual_uat_path()
    if not path.exists():
        return {"present": False, "results": {}, "operator": "", "recorded_at": "", "notes": ""}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"present": True, "valid": False, "results": {}, "operator": "", "recorded_at": "", "notes": ""}
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
        return {"present": True, "valid": False, "results": {}, "operator": "", "recorded_at": "", "notes": ""}
    return {
        "present": True,
        "valid": True,
        "results": {str(k): bool(v) for k, v in payload.get("results", {}).items()},
        "operator": str(payload.get("operator") or ""),
        "recorded_at": str(payload.get("recorded_at") or ""),
        "notes": str(payload.get("notes") or ""),
    }


def _parse_results(results_json) -> dict:
    if isinstance(results_json, dict):
        payload = results_json
    else:
        try:
            payload = json.loads(str(results_json or "{}"))
        except Exception as exc:
            frappe.throw(_(f"results_json must be valid JSON: {exc}"))
    if not isinstance(payload, dict):
        frappe.throw(_("results_json must be a JSON object."))
    return {str(key): bool(value) for key, value in payload.items()}


@frappe.whitelist()
def record_manual_uat_evidence(
    results_json,
    confirmation: str,
    operator: str = "",
    notes: str = "",
) -> dict:
    """Record explicit human/device UAT evidence. This never auto-passes a check."""

    _require_admin()
    if str(confirmation or "").strip() != MANUAL_UAT_CONFIRMATION:
        frappe.throw(_(f"Confirmation must be exactly: {MANUAL_UAT_CONFIRMATION}"))

    readiness = client_readiness.evaluate_client_readiness(strict_evidence=0)
    required = _required_uat_keys(dict(readiness.get("features") or {}))
    results = _parse_results(results_json)
    unknown = sorted(set(results) - set(required))
    if unknown:
        frappe.throw(_("Unsupported UAT key(s): " + ", ".join(unknown)))

    recorded_at = now_datetime()
    payload = {
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "site": getattr(frappe.local, "site", ""),
        "business_profile": readiness.get("business_profile") or "",
        "required_keys": required,
        "results": {key: bool(results.get(key)) for key in required},
        "operator": str(operator or frappe.session.user or "").strip(),
        "recorded_at": recorded_at,
        "notes": str(notes or "")[:2000],
        "contains_secrets": False,
        "manual_human_evidence": True,
    }
    path = _manual_uat_path()
    _acceptance_dir()
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return {
        "recorded": True,
        "required_keys": required,
        "passed_keys": [key for key in required if payload["results"].get(key)],
        "failed_keys": [key for key in required if not payload["results"].get(key)],
        "evidence_file": "private/ledgix-acceptance/manual-uat.json",
        "contains_secrets": False,
    }


def evaluate_release_acceptance(
    release_sha: str = "",
    require_fbr_certification: int | str = 0,
) -> dict:
    """Read-only acceptance evaluation; no FBR calls, transaction writes or arming."""

    _require_admin()
    release_sha = str(release_sha or "").strip()
    if release_sha and not re.fullmatch(r"[0-9a-fA-F]{40}", release_sha):
        frappe.throw(_("release_sha must be a full 40-character Git commit SHA."))
    require_fbr = bool(cint(require_fbr_certification))

    operational = client_readiness.evaluate_client_readiness(strict_evidence=0)
    strict_operational = client_readiness.evaluate_client_readiness(strict_evidence=1)
    features = dict(operational.get("features") or {})
    phase12 = verify_frozen_snapshot_read_only()
    print_checks, print_formats = _print_checks(features)
    manual = _load_manual_uat()
    required_uat = _required_uat_keys(features)
    manual_results = dict(manual.get("results") or {})
    manual_missing = [key for key in required_uat if not manual_results.get(key)]

    setup_checks = [
        _check(
            "r5_client_ready",
            bool(operational.get("ready")),
            "R5 client readiness must remain green.",
            category="Client readiness",
            details={"blockers": [row.get("key") for row in operational.get("blockers") or []]},
        ),
        _check(
            "phase12_frozen",
            bool(phase12.get("frozen")),
            "Phase 12 historical Ledgix business data must remain frozen.",
            category="Legacy retirement",
            details={"read_only": phase12.get("read_only")},
        ),
        _check(
            "phase12_snapshot_matches",
            bool(phase12.get("matches")),
            "Frozen Phase 12 historical snapshot must still match.",
            category="Legacy retirement",
            details={"read_only": phase12.get("read_only")},
        ),
    ]
    setup_checks.extend(print_checks)
    release_setup_ready = all(row["passed"] for row in setup_checks)

    fbr = None
    if features.get("enable_fbr"):
        fbr = fbr_activation.evaluate_fbr_activation_readiness(release_sha=release_sha)
    fbr_external_certification_complete = bool(not features.get("enable_fbr") or (fbr or {}).get("sandbox_proven"))
    fbr_production_ready = bool(not features.get("enable_fbr") or (fbr or {}).get("production_switch_ready"))
    manual_uat_ready = bool(manual.get("valid") and not manual_missing)
    strict_client_evidence_ready = bool(strict_operational.get("ready"))

    production_release_ready = bool(
        release_setup_ready
        and manual_uat_ready
        and strict_client_evidence_ready
        and (not require_fbr or fbr_production_ready)
    )

    external_pending = []
    if features.get("enable_fbr") and not fbr_external_certification_complete:
        external_pending.append("FBR Sandbox certification pending real client seller identity/token and real Sandbox proof.")
    if not manual_uat_ready:
        external_pending.append("Physical/browser/device manual UAT evidence is incomplete.")
    if not strict_client_evidence_ready:
        external_pending.append("Production release/provisioning and verified-backup evidence is incomplete.")

    return {
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "site": getattr(frappe.local, "site", ""),
        "release_sha": release_sha,
        "business_profile": operational.get("business_profile") or "",
        "features": features,
        "setup_checks": setup_checks,
        "print_formats": print_formats,
        "phase12": phase12,
        "manual_uat": manual,
        "required_manual_uat": required_uat,
        "missing_manual_uat": manual_missing,
        "fbr": fbr,
        "release_setup_ready": release_setup_ready,
        "manual_uat_ready": manual_uat_ready,
        "fbr_external_certification_complete": fbr_external_certification_complete,
        "strict_client_evidence_ready": strict_client_evidence_ready,
        "production_release_ready": production_release_ready,
        "require_fbr_certification": require_fbr,
        "external_pending": external_pending,
        "network_call_made": False,
        "production_armed_by_gate": False,
        "business_data_authority": "ERPNext",
    }


@frappe.whitelist()
def get_release_acceptance(release_sha: str = "", require_fbr_certification: int | str = 0) -> dict:
    return evaluate_release_acceptance(
        release_sha=release_sha,
        require_fbr_certification=require_fbr_certification,
    )


@frappe.whitelist()
def generate_release_acceptance_evidence(
    release_sha: str = "",
    operator: str = "",
    require_fbr_certification: int | str = 0,
) -> dict:
    """Persist a non-secret acceptance snapshot without changing business state."""

    _require_admin()
    result = evaluate_release_acceptance(
        release_sha=release_sha,
        require_fbr_certification=require_fbr_certification,
    )
    generated_at = now_datetime()
    payload = {
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "operator": str(operator or frappe.session.user or "").strip(),
        "acceptance": result,
        "contains_secrets": False,
        "network_call_made": False,
        "production_armed": False,
    }
    directory = _acceptance_dir()
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    evidence = directory / f"release-acceptance-{timestamp}.json"
    latest = directory / "latest.json"
    content = json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n"
    evidence.write_text(content, encoding="utf-8")
    latest.write_text(content, encoding="utf-8")
    os.chmod(evidence, 0o600)
    os.chmod(latest, 0o600)
    return {
        **result,
        "evidence_written": True,
        "evidence_file": f"private/ledgix-acceptance/{evidence.name}",
        "latest_evidence_file": "private/ledgix-acceptance/latest.json",
    }
