from __future__ import annotations

"""Compatibility shell for the retired pre-V2 FBR invoice HTTP client.

Status remains available for old callers, but invoice validation/submission is
owned exclusively by the company-scoped FBR V2 transport. This module performs
no invoice HTTP request and reads no legacy Ledgix FBR Settings/token.
"""

import frappe

from ledgix_saas.api import fbr_transport
from ledgix_saas.services.fbr_v2_status import (
    assert_fbr_v2_view_permission,
    get_fbr_v2_status_internal,
)


LEGACY_TRANSPORT_RETIRED_MESSAGE = (
    "Legacy FBR invoice transport is retired. "
    "Use the ERPNext-native FBR V2 workflow."
)


def requests_available():
    """Compatibility dependency probe only; this never performs a request."""

    return fbr_transport.requests_available()


def ensure_requests_available():
    """Compatibility dependency check only; this never performs a request."""

    return fbr_transport.ensure_requests_available()


def _retired_result(operation: str, mode=None) -> dict:
    return {
        "success": False,
        "network_call": False,
        "http_status": None,
        "status": "Retired",
        "response": None,
        "error": LEGACY_TRANSPORT_RETIRED_MESSAGE,
        "message": LEGACY_TRANSPORT_RETIRED_MESSAGE,
        "fbr_operation": operation,
        "fbr_mode": str(mode or ""),
        "transport_authority": "FBR V2",
    }


@frappe.whitelist()
def get_client_status():
    assert_fbr_v2_view_permission()
    return get_fbr_v2_status_internal()


def validate_invoice(payload, mode=None):
    """Fail closed for direct callers of the retired legacy validator."""

    return _retired_result("validate", mode)


def post_invoice(payload, mode=None):
    """Fail closed for direct callers of the retired legacy POST client."""

    return _retired_result("post", mode)
