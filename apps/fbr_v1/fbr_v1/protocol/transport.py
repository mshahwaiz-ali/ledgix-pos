from __future__ import annotations

from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from fbr_v1.protocol.constants import (
    CLOUD_PRODUCTION_URL,
    CLOUD_SANDBOX_URL,
    LOCAL_HEALTH_URL,
    LOCAL_POST_URL,
)
from fbr_v1.protocol.response import parse_fiscal_response


V1_NETWORK_CUTOVER_ACTIVE = False


class TransportUnavailable(RuntimeError):
    pass


def _site_gate(key):
    try:
        import frappe
        value = frappe.conf.get(key, 0)
        return value is True or type(value) is int and value == 1 or value == "1"
    except Exception:
        return False


def network_cutover_active():
    # Retained as an explicit test override; deployed default remains False.
    return V1_NETWORK_CUTOVER_ACTIVE is True or _site_gate("fbr_v1_network_cutover_active")


def production_cutover_active():
    return network_cutover_active() and _site_gate("fbr_v1_production_cutover_active")


def _client(http_client=None, *, production=False):
    real_client = http_client is None or (requests is not None and (http_client is requests or isinstance(http_client, requests.Session)))
    if real_client and not network_cutover_active():
        raise TransportUnavailable("V1 network cutover is disabled.")
    if real_client and production and not production_cutover_active():
        raise TransportUnavailable("V1 Production network cutover is disabled.")
    client = http_client or requests
    if client is None:
        raise TransportUnavailable("Python requests is required for FBR V1 transport.")
    return client


def _response_body(response) -> Any:
    try:
        return response.json()
    except Exception:
        return getattr(response, "text", "") or ""


def health_local(*, timeout: int = 5, http_client=None) -> dict[str, Any]:
    response = _client(http_client).get(LOCAL_HEALTH_URL, timeout=timeout)
    return {
        "network_call": True,
        "url": LOCAL_HEALTH_URL,
        "http_status": getattr(response, "status_code", None),
        "ok": bool(getattr(response, "ok", False)),
        "body": _response_body(response),
        "contains_secrets": False,
    }


def post_local(payload: dict[str, Any], *, environment: str = "Production", timeout: int = 30, http_client=None) -> dict[str, Any]:
    if environment not in {"Sandbox", "Production"}:
        raise TransportUnavailable("Explicit Sandbox or Production environment is required.")
    response = _client(http_client, production=environment == "Production").post(
        LOCAL_POST_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    body = _response_body(response)
    return {
        "network_call": True,
        "url": LOCAL_POST_URL,
        "http_status": getattr(response, "status_code", None),
        "http_ok": bool(getattr(response, "ok", False)),
        "fiscal": parse_fiscal_response(body),
        "body": body,
        "contains_secrets": False,
    }


def post_cloud(
    payload: dict[str, Any],
    *,
    token: str,
    environment: str,
    timeout: int = 30,
    http_client=None,
) -> dict[str, Any]:
    token = str(token or "").strip()
    if not token:
        raise TransportUnavailable("FBR V1 cloud Bearer token is required.")

    mode = str(environment or "").strip().lower()
    if mode == "sandbox":
        url = CLOUD_SANDBOX_URL
    elif mode == "production":
        url = CLOUD_PRODUCTION_URL
    else:
        raise ValueError("environment must be 'sandbox' or 'production'.")

    response = _client(http_client, production=mode == "production").post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    body = _response_body(response)
    return {
        "network_call": True,
        "url": url,
        "http_status": getattr(response, "status_code", None),
        "http_ok": bool(getattr(response, "ok", False)),
        "fiscal": parse_fiscal_response(body),
        "body": body,
        "contains_secrets": False,
    }
