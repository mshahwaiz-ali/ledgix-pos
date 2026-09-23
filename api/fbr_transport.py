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
