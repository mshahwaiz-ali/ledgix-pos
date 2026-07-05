import re

import frappe

from ledgix_saas.api.fbr_settings import (
    assert_fbr_view_permission,
    get_active_fbr_token,
    get_fbr_settings_internal,
)


SANDBOX_VALIDATE_URL = "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb"
PRODUCTION_VALIDATE_URL = "https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata"
SANDBOX_POST_URL = "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb"
PRODUCTION_POST_URL = "https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata"

try:
    import requests
except Exception:
    requests = None
    frappe.log_error(
        "Python 'requests' is not installed. FBR network calls are disabled until requests is available.",
        "Ledgix FBR requests missing",
    )


def requests_available():
    return requests is not None


def ensure_requests_available():
    if not requests_available():
        frappe.throw(
            "Python 'requests' package is required for FBR. Install it in the bench environment and restart."
        )


def _not_sent(status, message, error=None):
    return {
        "success": False,
        "network_call": False,
        "http_status": None,
        "status": status,
        "response": None,
        "error": error or message,
        "message": message,
    }


def _safe_error(exc):
    text = str(exc or "")
    text = re.sub(r"Bearer\s+[^\s,;]+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    if "Bearer " in text:
        text = text.split("Bearer ", 1)[0].rstrip()
    return text or "FBR request failed."


def _fbr_body_is_valid(response):
    if not isinstance(response, dict):
        return False

    validation_response = response.get("validationResponse") or {}
    if not isinstance(validation_response, dict):
        validation_response = {}

    status = str(validation_response.get("status") or response.get("status") or "").strip().lower()
    status_code = str(validation_response.get("statusCode") or response.get("statusCode") or "").strip()

    if status == "valid" and status_code == "00":
        return True

    invoice_statuses = validation_response.get("invoiceStatuses") or []
    if isinstance(invoice_statuses, list):
        for item in invoice_statuses:
            if not isinstance(item, dict):
                continue
            item_status = str(item.get("status") or "").strip().lower()
            item_code = str(item.get("statusCode") or "").strip()
            if item_status == "invalid" or (item_code and item_code != "00"):
                return False

    return False


def _finalize_fbr_http_result(result):
    if not result.get("network_call"):
        return result

    response = result.get("response")
    if isinstance(response, dict) and result.get("success") and not _fbr_body_is_valid(response):
        validation_response = response.get("validationResponse") or {}
        result["success"] = False
        result["status"] = "FBR Invalid"
        result["error"] = (
            validation_response.get("error")
            or validation_response.get("message")
            or response.get("error")
            or response.get("message")
            or "FBR response body indicates an invalid invoice."
        )

    return result


def _mode_gate(requested_mode, settings, operation):
    if requested_mode not in {"Sandbox", "Production"}:
        return _not_sent("Not Ready", f"FBR {operation} requires Sandbox or Production mode.")
    if settings.get("mode") != requested_mode:
        return _not_sent("Not Ready", f"FBR Settings mode must be {requested_mode} for {operation}.")
    if not settings.get("enabled"):
        return _not_sent("Not Ready", f"FBR Settings must be enabled for {operation}.")
    if settings.get("mode") in {"Disabled", "Paused", "Manual Only"}:
        return _not_sent("Not Ready", f"FBR {operation} is not allowed while settings are {settings.get('mode')}.")
    if requests is None:
        return _not_sent("Not Ready", f"Python requests is not available; FBR {operation} was not sent.")

    token_configured = settings.get("sandbox_token_configured") if requested_mode == "Sandbox" else settings.get("production_token_configured")
    if not token_configured:
        return _not_sent("Not Ready", f"{requested_mode} token is not configured.")

    token = get_active_fbr_token(requested_mode)
    if not token:
        return _not_sent("Not Ready", f"{requested_mode} token is not configured.")

    return token


def _send_fbr_request(url, payload, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        try:
            safe_response = response.json()
        except Exception:
            safe_response = response.text

        return _finalize_fbr_http_result({
            "success": 200 <= response.status_code < 300,
            "network_call": True,
            "http_status": response.status_code,
            "status": "HTTP OK" if 200 <= response.status_code < 300 else "HTTP Error",
            "response": safe_response,
            "error": "" if 200 <= response.status_code < 300 else f"FBR returned HTTP {response.status_code}.",
        })
    except Exception as exc:
        return _finalize_fbr_http_result({
            "success": False,
            "network_call": True,
            "http_status": None,
            "status": "Network Error",
            "response": None,
            "error": _safe_error(exc),
        })


@frappe.whitelist()
def get_client_status():
    assert_fbr_view_permission()
    settings = get_fbr_settings_internal()
    mode = settings.get("mode") or "Disabled"
    enabled = bool(settings.get("enabled")) and mode in {"Sandbox", "Production"}
    requests_ready = requests_available()
    return {
        "mode": mode,
        "requests_available": requests_ready,
        "sandbox_validate_connected": bool(requests_ready and enabled and mode == "Sandbox" and settings.get("sandbox_token_configured")),
        "sandbox_post_connected": bool(requests_ready and enabled and mode == "Sandbox" and settings.get("sandbox_token_configured")),
        "production_validate_connected": bool(requests_ready and enabled and mode == "Production" and settings.get("production_token_configured")),
        "production_post_connected": bool(requests_ready and enabled and mode == "Production" and settings.get("production_token_configured")),
        "token_configured": bool(
            (mode == "Sandbox" and settings.get("sandbox_token_configured"))
            or (mode == "Production" and settings.get("production_token_configured"))
        ),
        "network_enabled": enabled and requests_ready,
    }


def validate_invoice(payload, mode=None):
    settings = get_fbr_settings_internal()
    requested_mode = mode or settings.get("mode")
    token = _mode_gate(requested_mode, settings, "validation")

    if isinstance(token, dict):
        token["fbr_operation"] = "validate"
        token["fbr_mode"] = requested_mode
        return token

    url = SANDBOX_VALIDATE_URL if requested_mode == "Sandbox" else PRODUCTION_VALIDATE_URL
    result = _send_fbr_request(url, payload, token)
    result["fbr_operation"] = "validate"
    result["fbr_mode"] = requested_mode
    return result


def post_invoice(payload, mode=None):
    settings = get_fbr_settings_internal()
    requested_mode = mode or settings.get("mode")
    token = _mode_gate(requested_mode, settings, "post")

    if isinstance(token, dict):
        token["fbr_operation"] = "post"
        token["fbr_mode"] = requested_mode
        return token

    url = SANDBOX_POST_URL if requested_mode == "Sandbox" else PRODUCTION_POST_URL
    result = _send_fbr_request(url, payload, token)
    result["fbr_operation"] = "post"
    result["fbr_mode"] = requested_mode
    return result

