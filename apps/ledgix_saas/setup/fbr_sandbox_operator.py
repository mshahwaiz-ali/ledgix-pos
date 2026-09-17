from __future__ import annotations

"""Guarded local/integration helpers for real FBR Sandbox certification.

These helpers exist only to bridge operator-supplied client Sandbox details into
an integration site and to exercise the already-authoritative ERPNext-native FBR
adapter. They never configure Production credentials, never arm Production, and
never permit a Production network call.
"""

import json
import os
from pathlib import Path

import frappe
from frappe.utils import cint

from ledgix_saas.api import client_readiness, fbr_activation, fbr_native
from ledgix_saas.api.fbr_settings import get_fbr_settings_internal, save_fbr_settings

SANDBOX_CONFIRMATION = "SEND TO FBR SANDBOX"
PRIVATE_SUBDIR = "ledgix-fbr-activation"
NATIVE_DOCTYPES = ("Sales Invoice", "POS Invoice")
SUCCESSFUL_SANDBOX_STATUSES = {"Validated", "Submitted"}
CONFIG_REQUIRED_FIELDS = (
    "seller_ntn_cnic",
    "seller_business_name",
    "seller_province",
    "seller_address",
    "sandbox_token",
)
CONFIG_ALLOWED_FIELDS = set(CONFIG_REQUIRED_FIELDS) | {"software_registration_number"}


def _assert_local_integration_site() -> str:
    site = str(getattr(frappe.local, "site", "") or "").strip()
    if not (site.endswith(".local") or site.endswith(".localhost")):
        frappe.throw("FBR Sandbox operator helper is restricted to local/integration sites.")
    return site


def _set_administrator() -> None:
    frappe.set_user("Administrator")


def _private_activation_root() -> Path:
    root = Path(frappe.get_site_path("private", PRIVATE_SUBDIR)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def _resolve_private_input(path_value: str) -> Path:
    raw = str(path_value or "").strip()
    if not raw:
        frappe.throw("Sandbox configuration input path is required.")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path(frappe.get_site_path()) / candidate
    candidate = candidate.resolve()
    root = _private_activation_root()
    if candidate == root or root not in candidate.parents:
        frappe.throw("Sandbox configuration input must be inside private/ledgix-fbr-activation.")
    if candidate.is_symlink():
        frappe.throw("Sandbox configuration input cannot be a symlink.")
    if not candidate.is_file():
        frappe.throw("Sandbox configuration input file was not found.")
    stat = candidate.stat()
    if stat.st_mode & 0o077:
        frappe.throw("Sandbox configuration input must not be readable or writable by group/other users.")
    if stat.st_size <= 0 or stat.st_size > 65536:
        frappe.throw("Sandbox configuration input file size is invalid.")
    return candidate


def _load_private_config(path_value: str) -> tuple[Path, dict]:
    path = _resolve_private_input(path_value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        frappe.throw(f"Sandbox configuration input is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        frappe.throw("Sandbox configuration input must be a JSON object.")
    unknown = sorted(set(payload) - CONFIG_ALLOWED_FIELDS)
    if unknown:
        frappe.throw("Unsupported Sandbox configuration field(s): " + ", ".join(unknown))
    missing = [key for key in CONFIG_REQUIRED_FIELDS if not str(payload.get(key) or "").strip()]
    if missing:
        frappe.throw("Missing Sandbox configuration field(s): " + ", ".join(missing))
    return path, payload


def _safe_settings_summary() -> dict:
    settings = get_fbr_settings_internal()
    return {
        "enabled": bool(settings.get("enabled")),
        "mode": settings.get("mode") or "Disabled",
        "submit_trigger": settings.get("submit_trigger") or "Manual",
        "production_post_armed": bool(settings.get("production_post_armed")),
        "sandbox_token_configured": bool(settings.get("sandbox_token_configured")),
        "production_token_configured": bool(settings.get("production_token_configured")),
    }


def configure_sandbox_from_private_file(config_path: str) -> dict:
    """Apply real Sandbox identity/token to a local integration site only."""

    site = _assert_local_integration_site()
    _set_administrator()

    operational = client_readiness.evaluate_client_readiness(strict_evidence=0)
    if not operational.get("ready"):
        frappe.throw("R5 client readiness must be green before Sandbox configuration.")
    if not (operational.get("features") or {}).get("enable_fbr"):
        frappe.throw("The selected Ledgix Business Profile does not enable FBR.")

    before = _safe_settings_summary()
    if before["production_post_armed"] or before["mode"] == "Production":
        frappe.throw("Refusing Sandbox configuration while Production is active or armed.")

    input_path, payload = _load_private_config(config_path)
    values = {
        "enabled": 1,
        "mode": "Sandbox",
        "submit_trigger": "Manual",
        "production_post_armed": 0,
        "block_sale_if_fbr_fails": 0,
        "sandbox_post_on_submit": 0,
        "retry_enabled": 0,
        "max_retry_count": 0,
        "seller_ntn_cnic": str(payload["seller_ntn_cnic"]).strip(),
        "seller_business_name": str(payload["seller_business_name"]).strip(),
        "seller_province": str(payload["seller_province"]).strip(),
        "seller_address": str(payload["seller_address"]).strip(),
        "software_registration_number": str(payload.get("software_registration_number") or "").strip(),
        "sandbox_token": str(payload["sandbox_token"]).strip(),
    }
    save_fbr_settings(values)
    frappe.db.commit()

    # Do not retain the plaintext token staging file after Frappe encrypts it.
    input_path.unlink(missing_ok=True)

    after = _safe_settings_summary()
    if not (
        after["enabled"]
        and after["mode"] == "Sandbox"
        and after["submit_trigger"] == "Manual"
        and after["sandbox_token_configured"]
        and not after["production_post_armed"]
    ):
        frappe.throw("Sandbox settings did not persist in the required fail-closed state.")

    readiness = fbr_activation.evaluate_fbr_activation_readiness()
    return {
        "site": site,
        "configured": True,
        "sandbox_ready": bool(readiness.get("sandbox_ready")),
        "settings": after,
        "plaintext_input_removed": not input_path.exists(),
        "contains_secrets": False,
        "production_credentials_changed": False,
        "production_armed": False,
    }


def _parse_log_response(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _existing_sandbox_proof(reference_doctype: str, reference_name: str, operation: str) -> dict:
    rows = frappe.get_all(
        "Ledgix FBR Submission Log",
        filters={"reference_doctype": reference_doctype, "reference_name": reference_name},
        fields=["name", "fbr_status", "submitted_at", "response_json"],
        order_by="submitted_at desc, modified desc",
        limit_page_length=0,
    )
    for row in rows:
        response = _parse_log_response(row.get("response_json"))
        if str(response.get("fbr_mode") or "") != "Sandbox":
            continue
        if str(response.get("fbr_operation") or "").strip().lower() != operation:
            continue
        if row.get("fbr_status") not in SUCCESSFUL_SANDBOX_STATUSES:
            continue
        if not response.get("network_call") or not response.get("success"):
            continue
        return {
            "proven": True,
            "log_name": row.get("name") or "",
            "status": row.get("fbr_status") or "",
            "submitted_at": str(row.get("submitted_at") or ""),
        }
    return {"proven": False, "log_name": "", "status": "", "submitted_at": ""}


def _reference_summary(doctype: str, name: str) -> dict:
    doc = frappe.get_doc(doctype, name)
    return {
        "doctype": doctype,
        "name": name,
        "posting_date": str(doc.get("posting_date") or ""),
        "customer": doc.get("customer") or "",
        "grand_total": doc.get("grand_total") or 0,
        "is_return": bool(cint(doc.get("is_return"))),
        "fbr_status": doc.get("custom_ledgix_fbr_status") or "Not Submitted",
        "has_fbr_reference": bool(str(doc.get("custom_ledgix_fbr_invoice_number") or "").strip()),
    }


def list_sandbox_candidates(limit: int | str = 12) -> dict:
    """List recent native invoices with local payload-readiness only; no network."""

    site = _assert_local_integration_site()
    _set_administrator()
    limit_value = max(1, min(50, cint(limit or 12)))
    rows = []
    for doctype in NATIVE_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        names = frappe.get_all(
            doctype,
            filters={"docstatus": 1},
            pluck="name",
            order_by="posting_date desc, modified desc",
            limit_page_length=limit_value,
        )
        for name in names:
            try:
                validation = fbr_native.validate_native_readiness_internal(doctype, name)
                summary = _reference_summary(doctype, name)
                summary.update(
                    {
                        "payload_ready": bool(validation.get("valid")),
                        "errors": list(validation.get("errors") or []),
                        "warnings": list(validation.get("warnings") or []),
                        "sandbox_validate_proof": _existing_sandbox_proof(doctype, name, "validate"),
                        "sandbox_post_proof": _existing_sandbox_proof(doctype, name, "post"),
                    }
                )
                rows.append(summary)
            except Exception as exc:
                rows.append(
                    {
                        "doctype": doctype,
                        "name": name,
                        "payload_ready": False,
                        "errors": [str(exc)],
                        "warnings": [],
                    }
                )
    return {
        "site": site,
        "mode": _safe_settings_summary()["mode"],
        "network_call_made": False,
        "candidates": rows,
        "candidate_count": len(rows),
    }


def _result_summary(result: dict) -> dict:
    result = result or {}
    response = result.get("response") or {}
    return {
        "network_call": bool(result.get("network_call")),
        "status": result.get("status") or "",
        "log_name": result.get("log_name") or (result.get("reference_status") or {}).get("fbr_submission_log") or "",
        "fbr_invoice_number": result.get("fbr_invoice_number") or "",
        "fbr_qr_code_present": bool(result.get("fbr_qr_code")),
        "error_code": result.get("error_code") or "",
        "error_message": result.get("error_message") or "",
        "transport_success": bool(response.get("success")) if isinstance(response, dict) else False,
        "fbr_mode": response.get("fbr_mode") if isinstance(response, dict) else "",
        "fbr_operation": response.get("fbr_operation") if isinstance(response, dict) else "",
    }


def exercise_sandbox_reference(reference_doctype: str, reference_name: str, confirmation: str) -> dict:
    """Validate then POST one explicit ERPNext-native reference to FBR Sandbox."""

    site = _assert_local_integration_site()
    _set_administrator()
    if str(confirmation or "").strip() != SANDBOX_CONFIRMATION:
        frappe.throw(f"Confirmation must be exactly: {SANDBOX_CONFIRMATION}")

    doctype = str(reference_doctype or "").strip()
    name = str(reference_name or "").strip()
    if doctype not in NATIVE_DOCTYPES:
        frappe.throw("Sandbox exercise source must be Sales Invoice or POS Invoice.")
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name or ''} was not found.")

    settings = _safe_settings_summary()
    if not (
        settings["enabled"]
        and settings["mode"] == "Sandbox"
        and settings["sandbox_token_configured"]
        and not settings["production_post_armed"]
    ):
        frappe.throw("Sandbox exercise requires enabled Sandbox mode, a Sandbox token, and Production unarmed.")

    readiness_before = fbr_activation.evaluate_fbr_activation_readiness()
    if not readiness_before.get("sandbox_ready"):
        blockers = [row.get("key") for row in readiness_before.get("sandbox_checks") or [] if not row.get("passed")]
        frappe.throw("Sandbox configuration is not ready: " + ", ".join(blockers))

    doc = frappe.get_doc(doctype, name)
    if not fbr_native.is_native_fbr_source(doc):
        frappe.throw("Reference is not a submitted ERPNext-native FBR source invoice.")

    validate_proof = _existing_sandbox_proof(doctype, name, "validate")
    post_proof = _existing_sandbox_proof(doctype, name, "post")
    if str(doc.get("custom_ledgix_fbr_invoice_number") or "").strip() and not post_proof["proven"]:
        frappe.throw("Reference already has an FBR invoice number but no matching persisted Sandbox POST proof; refusing retransmission.")

    validate_result = {"skipped_existing_proof": True, **validate_proof}
    if not validate_proof["proven"]:
        raw_validate = fbr_native.validate_native_with_fbr_internal(doctype, name, mode="Sandbox")
        frappe.db.commit()
        validate_result = _result_summary(raw_validate)
        validate_result["skipped_existing_proof"] = False
        validate_ok = bool(validate_result["network_call"] and validate_result["status"] == "Validated")
        if not validate_ok:
            return {
                "site": site,
                "reference": _reference_summary(doctype, name),
                "validate": validate_result,
                "post": {"attempted": False},
                "passed": False,
                "production_armed": False,
                "contains_secrets": False,
            }

    post_result = {"skipped_existing_proof": True, **post_proof}
    if not post_proof["proven"]:
        raw_post = fbr_native.submit_native_to_fbr_internal(doctype, name)
        frappe.db.commit()
        post_result = _result_summary(raw_post)
        post_result["skipped_existing_proof"] = False

    proof_after_validate = _existing_sandbox_proof(doctype, name, "validate")
    proof_after_post = _existing_sandbox_proof(doctype, name, "post")
    passed = bool(proof_after_validate["proven"] and proof_after_post["proven"])
    activation_after = fbr_activation.evaluate_fbr_activation_readiness()
    return {
        "site": site,
        "reference": _reference_summary(doctype, name),
        "validate": validate_result,
        "post": post_result,
        "proof_after": {"validate": proof_after_validate, "post": proof_after_post},
        "passed": passed,
        "sandbox_proven_overall": bool(activation_after.get("sandbox_proven")),
        "production_switch_ready": bool(activation_after.get("production_switch_ready")),
        "production_armed": False,
        "contains_secrets": False,
    }
