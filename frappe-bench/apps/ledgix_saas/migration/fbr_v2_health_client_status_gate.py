from __future__ import annotations

"""Read-only proof for V2 health/client status after legacy client retirement."""

import frappe

from ledgix_saas.api import (
    fbr_client,
    fbr_health,
    fbr_native,
    fbr_transport,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing V2 health/status gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    original_user = frappe.session.user
    original_get = fbr_transport.get_json
    original_post = fbr_transport.post_json

    network_attempts = []

    def _forbid_network(*args, **kwargs):
        network_attempts.append(True)
        frappe.throw(
            "REAL FBR NETWORK FORBIDDEN BY V2 STATUS GATE"
        )

    try:
        frappe.set_user("Administrator")

        fbr_transport.get_json = _forbid_network
        fbr_transport.post_json = _forbid_network

        client_status = fbr_client.get_client_status()
        health = fbr_health.check()
        legacy_validate = fbr_client.validate_invoice(
            {"invoiceType": "Sale Invoice"},
            mode="Sandbox",
        )
        legacy_post = fbr_client.post_invoice(
            {"invoiceType": "Sale Invoice"},
            mode="Production",
        )

    finally:
        fbr_transport.get_json = original_get
        fbr_transport.post_json = original_post
        frappe.set_user(original_user)

    checks = {
        "client_status_v2": (
            client_status.get("source")
            == "Ledgix FBR Integration Profile"
        ),
        "health_v2": (
            health.get("source")
            == "Ledgix FBR Integration Profile"
        ),
        "legacy_validate_retired": (
            legacy_validate.get("status") == "Retired"
            and legacy_validate.get("network_call") is False
        ),
        "legacy_post_retired": (
            legacy_post.get("status") == "Retired"
            and legacy_post.get("network_call") is False
        ),
        "connectivity_fail_closed": not any(
            client_status.get(key)
            for key in (
                "sandbox_validate_connected",
                "sandbox_post_connected",
                "production_validate_connected",
                "production_post_connected",
                "network_enabled",
            )
        ),
        "no_fbr_network_attempts": not network_attempts,
        "native_cutover_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None)
            is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "v2_health_client_status_after_legacy_retirement",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            key for key, passed in checks.items() if not passed
        ],
        "client_status": client_status,
        "legacy_validate": legacy_validate,
        "legacy_post": legacy_post,
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "V2 health/client status gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
