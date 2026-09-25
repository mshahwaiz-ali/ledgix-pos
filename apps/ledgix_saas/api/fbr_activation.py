from __future__ import annotations

"""FBR Sandbox -> Production activation readiness over ERPNext-native invoices.

This module is deliberately split from transport. It never reads token values,
never sends a network request, and never arms Production posting. It evaluates
whether the site is ready to exercise Sandbox and whether persisted Sandbox +
release/backup evidence is strong enough to permit a separate Production switch.
"""

import json
import os
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_default_address
from frappe.utils import cint, now_datetime

from ledgix_saas.api import client_readiness, fbr_transport
from ledgix_saas.services import fbr_v2_readiness

ACTIVATION_SCHEMA_VERSION = 1
ADMIN_ROLES = {"System Manager", "Ledgix Admin"}
NATIVE_DOCTYPES = ("Sales Invoice", "POS Invoice")
SUCCESSFUL_SANDBOX_STATUSES = {"Validated", "Submitted"}
PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
DEFAULT_MAX_BACKUP_AGE_HOURS = 24


def _require_admin() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(ADMIN_ROLES):
        frappe.throw(_("FBR activation readiness requires Ledgix Admin or System Manager access."), frappe.PermissionError)


def _check(key: str, passed: bool, message: str, *, category: str, details: dict | None = None) -> dict:
    return {
        "key": key,
        "passed": bool(passed),
        "blocking": True,
        "category": category,
        "message": message,
        "details": details or {},
    }


def _configured(value) -> bool:
    """Treat None/blank optional profile values as not configured."""
    return bool(str(value or "").strip())


def _safe_json(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _seller_identity_summary(company: str) -> dict:
    company = str(company or "").strip()
    if not company or not frappe.db.exists("Company", company):
        return {
            "company": company,
            "complete": False,
            "missing_fields": [
                "ERPNext Company",
                "Company Tax ID",
                "Company Address",
                "Company Address State/Province",
            ],
            "address_name": "",
            "contains_secrets": False,
        }

    company_doc = frappe.get_doc("Company", company)
    address_name = str(get_default_address("Company", company) or "").strip()
    address = (
        frappe.get_cached_doc("Address", address_name)
        if address_name and frappe.db.exists("Address", address_name)
        else None
    )

    tax_id = str(company_doc.get("tax_id") or "").strip()
    business_name = str(
        company_doc.get("company_name") or company_doc.name or ""
    ).strip()
    province = str(address.get("state") or "").strip() if address else ""

    address_text = ""
    if address:
        parts = []
        for fieldname in (
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
        ):
            value = str(address.get(fieldname) or "").strip()
            if value and value not in parts:
                parts.append(value)
        address_text = ", ".join(parts)

    missing = []
    if not tax_id:
        missing.append("Company Tax ID")
    if not business_name:
        missing.append("Company Name")
    if not address_name:
        missing.append("Company Address")
    if not province:
        missing.append("Company Address State/Province")
    if not address_text:
        missing.append("Company Address")

    return {
        "company": company,
        "complete": not missing,
        "missing_fields": missing,
        "address_name": address_name,
        "contains_secrets": False,
    }


def get_v2_configuration_summary_internal(
    operational: dict | None = None,
) -> dict:
    operational = operational or client_readiness.evaluate_client_readiness(
        strict_evidence=0
    )
    company = str(
        (operational.get("identity") or {}).get("company") or ""
    ).strip()

    bundle = fbr_v2_readiness.get_company_profile_state(company)
    state = dict(bundle.get("profile") or {})
    certification = dict(bundle.get("sandbox_certification") or {})
    seller = _seller_identity_summary(company)

    profile_name = state.get("name") or ""
    profile_doc = (
        frappe.get_doc(PROFILE_DOCTYPE, profile_name)
        if profile_name and frappe.db.exists(PROFILE_DOCTYPE, profile_name)
        else None
    )

    return {
        "source": "Ledgix FBR Integration Profile",
        "company": company,
        "profile_name": profile_name,
        "profile_exists": bool(state.get("exists")),
        "enabled": bool(state.get("enabled")),
        "mode": state.get("mode") or "Disabled",
        "submit_trigger": state.get("submit_trigger") or "Manual",
        "production_post_armed": bool(
            state.get("production_post_armed")
        ),
        "sandbox_token_configured": bool(
            state.get("sandbox_token_configured")
        ),
        "production_token_configured": bool(
            state.get("production_token_configured")
        ),
        "seller_identity_complete": bool(seller.get("complete")),
        "missing_seller_identity_fields": list(
            seller.get("missing_fields") or []
        ),
        "seller_identity_source": "ERPNext Company + Company Address",
        "software_registration_number_configured": _configured(
            profile_doc.get("software_registration_number")
            if profile_doc
            else ""
        ),
        "digital_invoicing_logo_configured": _configured(
            profile_doc.get("digital_invoicing_logo")
            if profile_doc
            else ""
        ),
        "requests_available": bool(fbr_transport.requests_available()),
        "sandbox_certification_name": certification.get("name") or "",
        "sandbox_certification_status": certification.get("status") or "",
        "sandbox_certification_evidence_complete": bool(
            certification.get("evidence_complete")
        ),
        "sandbox_certification_complete": bool(
            certification.get("complete")
        ),
        "contains_secrets": False,
    }



def _native_reference_is_return(doctype: str, name: str) -> bool:
    if not doctype or not name or not frappe.db.exists(doctype, name):
        return False
    return bool(cint(frappe.db.get_value(doctype, name, "is_return") or 0))


def _sandbox_proof_summary(company: str, profile_name: str) -> dict:
    summary = {
        "Sales Invoice": {"validate": 0, "post": 0},
        "POS Invoice": {"validate": 0, "post": 0},
        "return": {"validate": 0, "post": 0},
        "latest_success_at": "",
        "successful_log_names": [],
    }
    company = str(company or "").strip()
    profile_name = str(profile_name or "").strip()
    if not company or not profile_name:
        return summary
    if not frappe.db.exists("DocType", "Ledgix FBR Submission Log"):
        return summary

    rows = frappe.get_all(
        "Ledgix FBR Submission Log",
        filters={"reference_doctype": ["in", list(NATIVE_DOCTYPES)]},
        fields=[
            "name",
            "reference_doctype",
            "reference_name",
            "fbr_status",
            "submitted_at",
            "response_json",
        ],
        order_by="submitted_at desc, modified desc",
        limit_page_length=0,
    )
    for row in rows:
        response = _safe_json(row.get("response_json"))
        if str(response.get("fbr_mode") or "") != "Sandbox":
            continue
        if str(response.get("company") or "").strip() != company:
            continue
        if str(response.get("profile_name") or "").strip() != profile_name:
            continue

        operation = str(response.get("fbr_operation") or "").strip().lower()
        if operation not in {"validate", "post"}:
            continue
        expected_status = "Validated" if operation == "validate" else "Submitted"
        if row.get("fbr_status") != expected_status:
            continue
        if response.get("network_call") is not True or response.get("success") is not True:
            continue

        doctype = row.get("reference_doctype")
        reference_name = row.get("reference_name")
        if doctype not in NATIVE_DOCTYPES:
            continue
        if str(frappe.db.get_value(doctype, reference_name, "company") or "").strip() != company:
            continue

        summary[doctype][operation] += 1
        if _native_reference_is_return(doctype, reference_name):
            summary["return"][operation] += 1
        if row.get("name"):
            summary["successful_log_names"].append(row.get("name"))
        if not summary["latest_success_at"] and row.get("submitted_at"):
            summary["latest_success_at"] = str(row.get("submitted_at"))

    summary["successful_log_names"] = summary["successful_log_names"][:20]
    return summary


def _reconciliation_summary(company: str) -> dict:
    company = str(company or "").strip()
    rows = []
    if not company:
        return {"count": 0, "references": rows}
    for doctype in NATIVE_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        names = frappe.get_all(
            doctype,
            filters={
                "docstatus": 1,
                "company": company,
                "custom_ledgix_fbr_status": "Reconciliation Required",
            },
            pluck="name",
            limit_page_length=0,
        )
        rows.extend({"doctype": doctype, "name": name} for name in names)
    return {"count": len(rows), "references": rows[:50]}


def _backup_summary(max_age_hours: int) -> dict:
    backup_dir = Path(frappe.get_site_path("private", "backups"))
    candidates = sorted(
        backup_dir.glob("ledgix-backup-*.env"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if backup_dir.exists() else []
    if not candidates:
        return {"present": False, "fresh": False, "latest": "", "age_hours": None, "max_age_hours": max_age_hours}

    latest = candidates[0]
    age_seconds = max(0.0, now_datetime().timestamp() - latest.stat().st_mtime)
    age_hours = round(age_seconds / 3600.0, 2)
    return {
        "present": True,
        "fresh": age_hours <= max_age_hours,
        "latest": latest.name,
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
    }


def evaluate_fbr_activation_readiness(
    release_sha: str = "",
    require_return_proof: int | str = 0,
    max_backup_age_hours: int | str = DEFAULT_MAX_BACKUP_AGE_HOURS,
) -> dict:
    """Read-only FBR activation readiness. No token values and no network calls."""

    _require_admin()
    release_sha = str(release_sha or "").strip()
    if release_sha and not re.fullmatch(r"[0-9a-fA-F]{40}", release_sha):
        frappe.throw(_("release_sha must be a full 40-character Git commit SHA."))
    require_return = bool(cint(require_return_proof))
    max_backup_age = max(1, min(168, cint(max_backup_age_hours or DEFAULT_MAX_BACKUP_AGE_HOURS)))

    operational = client_readiness.evaluate_client_readiness(strict_evidence=0)
    production_operational = client_readiness.evaluate_client_readiness(strict_evidence=1)
    features = dict(operational.get("features") or {})
    settings = get_v2_configuration_summary_internal(operational)
    proof = _sandbox_proof_summary(
        settings.get("company") or "",
        settings.get("profile_name") or "",
    )
    reconciliation = _reconciliation_summary(settings.get("company") or "")
    backup = _backup_summary(max_backup_age)
    require_pos = bool(features.get("enable_pos"))

    sandbox_checks = [
        _check("r5_client_ready", bool(operational.get("ready")), "R5 client onboarding must be green before FBR Sandbox testing.", category="Client readiness"),
        _check("fbr_feature_enabled", bool(features.get("enable_fbr")), "The selected Ledgix Business Profile must enable FBR.", category="FBR configuration"),
        _check("seller_identity_complete", settings["seller_identity_complete"], "Complete seller NTN/CNIC, business name, province and address.", category="FBR configuration", details={"missing_fields": settings["missing_seller_identity_fields"]}),
        _check("requests_available", settings["requests_available"], "Python requests transport must be available in the bench environment.", category="FBR transport"),
        _check("sandbox_mode_selected", settings["enabled"] and settings["mode"] == "Sandbox", "Enable FBR in Sandbox mode before exercising Sandbox traffic.", category="FBR configuration", details={"enabled": settings["enabled"], "mode": settings["mode"]}),
        _check("sandbox_token_configured", settings["sandbox_token_configured"], "Configure the client Sandbox token securely.", category="FBR credentials"),
        _check("production_unarmed", not settings["production_post_armed"], "Production posting must remain unarmed during Sandbox certification.", category="Production interlock"),
        _check("no_reconciliation_required", reconciliation["count"] == 0, "Resolve every ambiguous Production FBR outcome before any activation work.", category="Reconciliation", details=reconciliation),
    ]
    sandbox_ready = all(row["passed"] for row in sandbox_checks)

    proof_checks = [
        _check("sandbox_sales_invoice_validate", proof["Sales Invoice"]["validate"] > 0, "Retain a successful Sandbox validation log for an ERPNext Sales Invoice.", category="Sandbox proof", details=proof["Sales Invoice"]),
        _check("sandbox_sales_invoice_post", proof["Sales Invoice"]["post"] > 0, "Retain a successful Sandbox POST log for an ERPNext Sales Invoice.", category="Sandbox proof", details=proof["Sales Invoice"]),
    ]
    if require_pos:
        proof_checks.extend([
            _check("sandbox_pos_invoice_validate", proof["POS Invoice"]["validate"] > 0, "Retain a successful Sandbox validation log for an ERPNext POS Invoice.", category="Sandbox proof", details=proof["POS Invoice"]),
            _check("sandbox_pos_invoice_post", proof["POS Invoice"]["post"] > 0, "Retain a successful Sandbox POST log for an ERPNext POS Invoice.", category="Sandbox proof", details=proof["POS Invoice"]),
        ])
    if require_return:
        proof_checks.extend([
            _check("sandbox_return_validate", proof["return"]["validate"] > 0, "Retain successful Sandbox validation evidence for a native return/note.", category="Sandbox proof", details=proof["return"]),
            _check("sandbox_return_post", proof["return"]["post"] > 0, "Retain successful Sandbox POST evidence for a native return/note.", category="Sandbox proof", details=proof["return"]),
        ])
    sandbox_proven = sandbox_ready and all(row["passed"] for row in proof_checks)

    production_checks = [
        _check("sandbox_proven", sandbox_proven, "Required Sandbox validation/POST evidence must be complete before Production switch.", category="Production gate"),
        _check("sandbox_certification_complete", settings["sandbox_certification_complete"], "Complete Ledgix FBR Sandbox Certification with complete evidence before Production switch.", category="Production gate", details={"certification": settings["sandbox_certification_name"], "status": settings["sandbox_certification_status"], "evidence_complete": settings["sandbox_certification_evidence_complete"]}),
        _check("production_token_configured", settings["production_token_configured"], "Configure the client Production token securely before activation.", category="FBR credentials"),
        _check("digital_invoicing_logo_configured", settings["digital_invoicing_logo_configured"], "Attach the authoritative FBR Digital Invoicing System logo confirmed for this client/provider before Production activation.", category="Print compliance"),
        _check("production_still_unarmed", not settings["production_post_armed"], "Production must remain unarmed until the explicit activation action.", category="Production interlock"),
        _check("not_already_production", settings["mode"] != "Production", "The readiness gate expects a pre-Production state; Production switching is a separate explicit action.", category="Production interlock", details={"mode": settings["mode"]}),
        _check("strict_client_evidence", bool(production_operational.get("ready")), "Strict client release/provisioning and verified-backup evidence must be green.", category="Operational evidence", details={"blockers": [row.get("key") for row in production_operational.get("blockers") or []]}),
        _check("fresh_verified_backup", backup["fresh"], f"Capture a verified backup no older than {max_backup_age} hours before Production activation.", category="Operational evidence", details=backup),
        _check("release_sha_recorded", bool(release_sha), "Record the exact approved 40-character release SHA before Production activation.", category="Operational evidence", details={"release_sha": release_sha}),
        _check("no_unreconciled_production_state", reconciliation["count"] == 0, "No native invoice may remain in Reconciliation Required state.", category="Reconciliation", details=reconciliation),
    ]
    production_switch_ready = all(row["passed"] for row in production_checks)

    return {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "site": getattr(frappe.local, "site", ""),
        "release_sha": release_sha,
        "business_profile": operational.get("business_profile") or "",
        "require_pos_proof": require_pos,
        "require_return_proof": require_return,
        "settings": settings,
        "sandbox_proof": proof,
        "reconciliation": reconciliation,
        "backup": backup,
        "sandbox_checks": sandbox_checks,
        "sandbox_proof_checks": proof_checks,
        "production_checks": production_checks,
        "sandbox_ready": sandbox_ready,
        "sandbox_proven": sandbox_proven,
        "production_switch_ready": production_switch_ready,
        "network_call_made": False,
        "production_armed_by_gate": False,
        "contains_secrets": False,
        "authority": "ERPNext native Sales Invoice/POS Invoice + Ledgix FBR audit/safety layer",
        "next_action": (
            "Production switch approval" if production_switch_ready
            else "Complete Sandbox configuration/proof and production release evidence"
        ),
    }


@frappe.whitelist()
def get_fbr_activation_readiness(
    release_sha: str = "",
    require_return_proof: int | str = 0,
    max_backup_age_hours: int | str = DEFAULT_MAX_BACKUP_AGE_HOURS,
) -> dict:
    return evaluate_fbr_activation_readiness(
        release_sha=release_sha,
        require_return_proof=require_return_proof,
        max_backup_age_hours=max_backup_age_hours,
    )


@frappe.whitelist()
def generate_fbr_activation_evidence(
    release_sha: str = "",
    operator: str = "",
    require_return_proof: int | str = 0,
    max_backup_age_hours: int | str = DEFAULT_MAX_BACKUP_AGE_HOURS,
) -> dict:
    """Persist a non-secret read-only FBR activation readiness snapshot."""

    _require_admin()
    readiness = evaluate_fbr_activation_readiness(
        release_sha=release_sha,
        require_return_proof=require_return_proof,
        max_backup_age_hours=max_backup_age_hours,
    )
    generated_at = now_datetime()
    payload = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "operator": str(operator or frappe.session.user or "").strip(),
        "release_sha": readiness.get("release_sha") or "",
        "readiness": readiness,
        "contains_secrets": False,
        "network_call_made": False,
        "production_armed": False,
    }

    evidence_dir = Path(frappe.get_site_path("private", "ledgix-fbr-activation"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence_dir, 0o700)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    evidence_path = evidence_dir / f"fbr-activation-readiness-{timestamp}.json"
    latest_path = evidence_dir / "latest-readiness.json"
    content = json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n"
    evidence_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    os.chmod(evidence_path, 0o600)
    os.chmod(latest_path, 0o600)

    return {
        **readiness,
        "evidence_written": True,
        "evidence_file": f"private/ledgix-fbr-activation/{evidence_path.name}",
        "latest_evidence_file": "private/ledgix-fbr-activation/latest-readiness.json",
    }
