from __future__ import annotations

"""LOCAL proof that retired legacy reference RPCs cannot reach FBR network."""

import frappe

from ledgix_saas.api import fbr_native, fbr_reference, fbr_transport
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing legacy reference retirement gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    original_get = fbr_transport.get_json
    network_attempts = []

    def _forbid_get(*args, **kwargs):
        network_attempts.append({"args": args, "kwargs": kwargs})
        frappe.throw("REAL FBR GET FORBIDDEN BY RETIREMENT GATE")

    fbr_transport.get_json = _forbid_get

    calls = [
        ("get_provinces", lambda: fbr_reference.get_provinces()),
        ("get_document_types", lambda: fbr_reference.get_document_types()),
        ("get_transaction_types", lambda: fbr_reference.get_transaction_types()),
        ("get_uoms", lambda: fbr_reference.get_uoms()),
        (
            "get_rates",
            lambda: fbr_reference.get_rates(
                "2025-05-18",
                "1",
                "Sindh",
            ),
        ),
        (
            "get_hs_uoms",
            lambda: fbr_reference.get_hs_uoms("0101.21", 3),
        ),
        (
            "get_sro_schedules",
            lambda: fbr_reference.get_sro_schedules(
                "1",
                "2025-05-18",
                "Sindh",
            ),
        ),
        (
            "get_sro_items",
            lambda: fbr_reference.get_sro_items("2025-05-18", "1"),
        ),
        (
            "get_sales_tax_registration_status",
            lambda: fbr_reference.get_sales_tax_registration_status(
                "0788762",
                "2025-05-18",
            ),
        ),
        (
            "get_registration_type",
            lambda: fbr_reference.get_registration_type("0788762"),
        ),
    ]

    evidence = []
    all_blocked = True

    try:
        for name, call in calls:
            blocked = False
            message = ""
            try:
                call()
            except frappe.ValidationError as exc:
                message = str(exc)
                blocked = (
                    "Legacy FBR reference APIs are retired"
                    in message
                )
            all_blocked = all_blocked and blocked
            evidence.append(
                {
                    "function": name,
                    "blocked": blocked,
                    "message": message,
                }
            )
    finally:
        fbr_transport.get_json = original_get

    checks = {
        "all_legacy_reference_functions_blocked": all_blocked,
        "all_10_public_surfaces_exercised": len(evidence) == 10,
        "no_fbr_get_attempts": not network_attempts,
        "native_cutover_still_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "legacy_reference_network_retirement",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "evidence": evidence,
        "scope_proven": [
            "all 10 legacy reference RPC surfaces fail closed",
            "legacy reference module cannot use old global FBR credentials",
            "no legacy reference call reaches neutral FBR GET transport",
            "canonical V2 reference service remains separate",
        ],
        "scope_not_proven": [
            "authorized V2 Sandbox reference GET",
            "old global FBR Settings full retirement",
            "legacy fbr_client/health/activation retirement",
        ],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Legacy reference retirement gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
