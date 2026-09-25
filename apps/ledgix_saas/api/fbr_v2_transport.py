from __future__ import annotations

'''Company-scoped authenticated transport policy for FBR V2 invoices.

Credentials come only from Ledgix FBR Integration Profile. Endpoint selection,
mode checks, Production arming and ambiguity classification live here. HTTP
mechanics remain in the credential-agnostic fbr_transport module.

This module does not build payloads, calculate tax, write accounting, persist
submission logs, change profile state, or retry ambiguous Production POSTs.
'''

import frappe
from frappe.utils import cint
from frappe.utils.password import get_decrypted_password

from ledgix_saas.api import fbr_transport
from ledgix_saas.services import fbr_v2_readiness


PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"

SANDBOX_VALIDATE_URL = "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb"
PRODUCTION_VALIDATE_URL = "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata"
SANDBOX_POST_URL = "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
PRODUCTION_POST_URL = "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata"


def _text(value) -> str:
    return str(value or "").strip()


def _not_sent(
    *,
    operation: str,
    company: str,
    mode: str,
    message: str,
    profile_name: str = "",
) -> dict:
    return {
        "success": False,
        "network_call": False,
        "http_status": None,
        "status": "Not Ready",
        "response": None,
        "error": message,
        "fbr_operation": operation,
        "fbr_mode": mode,
        "company": company,
        "profile_name": profile_name,
        "ambiguous_outcome": False,
        "requires_reconciliation": False,
        "contains_secrets": False,
    }


def _profile_for_company(company: str):
    company = _text(company)
    if not company:
        return None

    profile_name = frappe.db.get_value(
        PROFILE_DOCTYPE,
        {"company": company},
        "name",
    )
    if not profile_name:
        return None
    return frappe.get_doc(PROFILE_DOCTYPE, profile_name)


def _token(profile, mode: str) -> str:
    fieldname = "sandbox_token" if mode == "Sandbox" else "production_token"
    return (
        get_decrypted_password(
            PROFILE_DOCTYPE,
            profile.name,
            fieldname,
            raise_exception=False,
        )
        or ""
    )


def _production_certification(profile) -> dict:
    # Fail closed on re-derived, company/profile-scoped Sandbox evidence.
    return fbr_v2_readiness.get_sandbox_certification_state(profile)


def _transport_context(
    *,
    company: str,
    operation: str,
    requested_mode: str | None,
) -> tuple[dict | None, dict | None]:
    company = _text(company)
    operation = _text(operation).lower()

    if operation not in {"validate", "post"}:
        return None, _not_sent(
            operation=operation or "unknown",
            company=company,
            mode=_text(requested_mode),
            message="Unsupported FBR V2 transport operation.",
        )

    profile = _profile_for_company(company)
    if not profile:
        return None, _not_sent(
            operation=operation,
            company=company,
            mode=_text(requested_mode),
            message="Company has no Ledgix FBR Integration Profile.",
        )

    profile_mode = _text(profile.get("mode")) or "Disabled"
    mode = _text(requested_mode) or profile_mode

    if mode not in {"Sandbox", "Production"}:
        return None, _not_sent(
            operation=operation,
            company=company,
            mode=mode,
            profile_name=profile.name,
            message="FBR V2 transport requires Sandbox or Production mode.",
        )

    if profile_mode != mode:
        return None, _not_sent(
            operation=operation,
            company=company,
            mode=mode,
            profile_name=profile.name,
            message=(
                f"FBR Integration Profile mode is {profile_mode}; "
                f"{operation} requested {mode}."
            ),
        )

    if not cint(profile.get("enabled")):
        return None, _not_sent(
            operation=operation,
            company=company,
            mode=mode,
            profile_name=profile.name,
            message="FBR Integration Profile must be enabled before invoice transport.",
        )

    if mode == "Production" and operation == "post":
        certification = _production_certification(profile)
        if not certification.get("complete"):
            return None, _not_sent(
                operation=operation,
                company=company,
                mode=mode,
                profile_name=profile.name,
                message=(
                    "Production posting requires a completed Sandbox Certification "
                    "with complete evidence."
                ),
            )

        if not cint(profile.get("production_post_armed")):
            return None, _not_sent(
                operation=operation,
                company=company,
                mode=mode,
                profile_name=profile.name,
                message=(
                    "Production posting is not armed. Arm Production Posting only "
                    "after Sandbox certification and go-live approval."
                ),
            )

    if not fbr_transport.requests_available():
        return None, _not_sent(
            operation=operation,
            company=company,
            mode=mode,
            profile_name=profile.name,
            message="Python requests is not available; FBR V2 transport was not sent.",
        )

    token = _token(profile, mode)
    if not token:
        return None, _not_sent(
            operation=operation,
            company=company,
            mode=mode,
            profile_name=profile.name,
            message=f"{mode} token is not configured on the FBR Integration Profile.",
        )

    return {
        "company": company,
        "profile_name": profile.name,
        "mode": mode,
        "operation": operation,
        "token": token,
    }, None


def _fbr_body_state(response) -> str:
    # Return valid, invalid, or unknown without guessing malformed replies.
    if not isinstance(response, dict):
        return "unknown"

    validation = response.get("validationResponse")
    if validation is None:
        validation = {}
    if not isinstance(validation, dict):
        return "unknown"

    status = _text(validation.get("status") or response.get("status")).lower()
    status_code = _text(
        validation.get("statusCode") or response.get("statusCode")
    )

    invoice_statuses = validation.get("invoiceStatuses") or []
    if isinstance(invoice_statuses, list):
        for row in invoice_statuses:
            if not isinstance(row, dict):
                continue
            item_status = _text(row.get("status")).lower()
            item_code = _text(row.get("statusCode"))
            if item_status == "invalid" or (item_code and item_code != "00"):
                return "invalid"

    if status == "valid" and status_code == "00":
        return "valid"

    explicit_signal = bool(
        status
        or status_code
        or _text(validation.get("error"))
        or _text(validation.get("message"))
        or _text(response.get("error"))
        or _text(response.get("message"))
    )
    return "invalid" if explicit_signal else "unknown"


def _fbr_body_is_valid(response) -> bool:
    return _fbr_body_state(response) == "valid"


def _invoice_number(response) -> str:
    if not isinstance(response, dict):
        return ""
    validation = response.get("validationResponse") or {}
    if not isinstance(validation, dict):
        validation = {}
    return _text(
        response.get("invoiceNumber")
        or validation.get("invoiceNumber")
    )


def _production_post_is_ambiguous(result: dict, response) -> bool:
    # Fail closed when a Production POST may have reached FBR but is uncertain.
    if not result.get("network_call"):
        return False

    if result.get("status") == "Network Error":
        return True

    http_status = result.get("http_status")
    if http_status in (408,):
        return True
    if isinstance(http_status, int) and http_status >= 500:
        return True

    if result.get("status") == "FBR Response Uncertain":
        return True

    if (
        result.get("success")
        and _fbr_body_state(response) == "valid"
        and not _invoice_number(response)
    ):
        return True

    return False


def _endpoint(mode: str, operation: str) -> str:
    if mode == "Sandbox":
        return SANDBOX_VALIDATE_URL if operation == "validate" else SANDBOX_POST_URL
    return PRODUCTION_VALIDATE_URL if operation == "validate" else PRODUCTION_POST_URL


def _send(
    *,
    company: str,
    payload: dict,
    operation: str,
    mode: str | None = None,
) -> dict:
    if not isinstance(payload, dict) or not payload:
        return _not_sent(
            operation=operation,
            company=_text(company),
            mode=_text(mode),
            message="FBR V2 transport requires a non-empty payload object.",
        )

    context, blocked = _transport_context(
        company=company,
        operation=operation,
        requested_mode=mode,
    )
    if blocked:
        return blocked

    result = fbr_transport.post_json(
        url=_endpoint(context["mode"], operation),
        token=context["token"],
        payload=payload,
        timeout=30,
    )

    response = result.get("response")
    body_state = _fbr_body_state(response)
    if (
        result.get("network_call")
        and result.get("success")
        and body_state != "valid"
    ):
        validation = (
            response.get("validationResponse") or {}
            if isinstance(response, dict)
            else {}
        )
        if not isinstance(validation, dict):
            validation = {}

        result["success"] = False
        if body_state == "invalid":
            result["status"] = "FBR Invalid"
            result["error"] = _text(
                validation.get("error")
                or validation.get("message")
                or (response.get("error") if isinstance(response, dict) else "")
                or (response.get("message") if isinstance(response, dict) else "")
                or "FBR response body indicates an invalid invoice."
            )
        else:
            result["status"] = "FBR Response Uncertain"
            result["error"] = (
                "FBR returned a successful HTTP response without a conclusive "
                "valid/invalid invoice body."
            )

    ambiguous = bool(
        context["mode"] == "Production"
        and operation == "post"
        and _production_post_is_ambiguous(result, response)
    )

    error = _text(result.get("error"))
    if ambiguous:
        error = (
            f"{error} Production POST outcome may be ambiguous. "
            "Reconcile the invoice with FBR/PRAL before any retransmission; "
            "automatic recovery is intentionally disabled."
        ).strip()

    return {
        **result,
        "error": error,
        "fbr_operation": operation,
        "fbr_mode": context["mode"],
        "company": context["company"],
        "profile_name": context["profile_name"],
        "ambiguous_outcome": ambiguous,
        "requires_reconciliation": ambiguous,
        "contains_secrets": False,
    }


def validate_invoice(
    *,
    company: str,
    payload: dict,
    mode: str | None = None,
) -> dict:
    return _send(
        company=company,
        payload=payload,
        operation="validate",
        mode=mode,
    )


def post_invoice(
    *,
    company: str,
    payload: dict,
    mode: str | None = None,
) -> dict:
    return _send(
        company=company,
        payload=payload,
        operation="post",
        mode=mode,
    )
