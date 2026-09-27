from __future__ import annotations

"""Credential-agnostic HTTP helpers for FBR integration services.

This module knows nothing about credential-storage models, invoice lifecycle,
Production arming or accounting. Callers resolve their own credentials and
policy before invoking transport.
"""

import re

import frappe

try:
    import requests
except Exception:
    requests = None


def requests_available() -> bool:
    return requests is not None


def ensure_requests_available() -> None:
    if requests is None:
        frappe.throw(
            "Python requests is required for FBR network access. "
            "Install it in the bench environment and restart."
        )


def safe_error(exc: Exception) -> str:
    value = str(exc or "")
    value = re.sub(
        r"Bearer\s+[^\s,;]+",
        "Bearer [REDACTED]",
        value,
        flags=re.IGNORECASE,
    )
    if "Bearer " in value:
        value = value.split("Bearer ", 1)[0].rstrip()
    return value or "FBR request failed."


def get_json(
    *,
    url: str,
    token: str,
    params: dict | None = None,
    timeout: int = 30,
) -> dict:
    """Perform an authenticated FBR GET and return JSON.

    URL selection, credential selection and authorization policy belong to the
    caller. This helper never accepts or persists credentials other than the
    in-memory Bearer token required for this request.
    """

    ensure_requests_available()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            url,
            params=params or {},
            headers=headers,
            timeout=timeout,
        )
        if not (200 <= response.status_code < 300):
            frappe.throw(f"FBR GET returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except Exception:
            frappe.throw("FBR GET returned a non-JSON response.")
    except frappe.ValidationError:
        raise
    except Exception as exc:
        frappe.throw(safe_error(exc))

    return {
        "http_status": response.status_code,
        "payload": payload,
    }


def post_json(
    *,
    url: str,
    token: str,
    payload: dict,
    timeout: int = 30,
) -> dict:
    # Business policy belongs to the caller. This helper only performs the
    # authenticated JSON POST and returns a redacted structured result.
    if not requests_available():
        return {
            "success": False,
            "network_call": False,
            "http_status": None,
            "status": "Not Ready",
            "response": None,
            "error": "Python requests is not available; FBR POST was not sent.",
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        try:
            safe_response = response.json()
        except Exception:
            safe_response = response.text

        success = 200 <= response.status_code < 300
        return {
            "success": success,
            "network_call": True,
            "http_status": response.status_code,
            "status": "HTTP OK" if success else "HTTP Error",
            "response": safe_response,
            "error": "" if success else f"FBR returned HTTP {response.status_code}.",
        }
    except Exception as exc:
        return {
            "success": False,
            "network_call": True,
            "http_status": None,
            "status": "Network Error",
            "response": None,
            "error": safe_error(exc),
        }
