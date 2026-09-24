from __future__ import annotations

# LOCAL proof that activation/operator configuration authority is V2-owned.

import frappe

from ledgix_saas.api import (
    fbr_activation,
    fbr_native,
    fbr_transport,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.setup import fbr_sandbox_operator


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing V2 activation profile gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    original_user = frappe.session.user
    original_get = fbr_transport.get_json
    original_post = fbr_transport.post_json

    network_attempts = []

    def _forbid_network(*args, **kwargs):
        network_attempts.append(True)
        frappe.throw(
            "REAL FBR NETWORK FORBIDDEN BY V2 ACTIVATION GATE"
        )

    try:
        frappe.set_user("Administrator")
        fbr_transport.get_json = _forbid_network
        fbr_transport.post_json = _forbid_network

        activation = fbr_activation.evaluate_fbr_activation_readiness()
        operator = fbr_sandbox_operator._safe_settings_summary()

    finally:
        fbr_transport.get_json = original_get
        fbr_transport.post_json = original_post
        frappe.set_user(original_user)

    settings = activation.get("settings") or {}
    checks = {
        "activation_source_is_v2_profile": (
            settings.get("source")
            == "Ledgix FBR Integration Profile"
        ),
        "activation_company_is_setup_company": bool(
            settings.get("company")
        ),
        "seller_identity_is_erpnext": (
            settings.get("seller_identity_source")
            == "ERPNext Company + Company Address"
        ),
        "operator_source_is_v2_profile": (
            operator.get("source")
            == "Ledgix FBR Integration Profile"
        ),
        "operator_profile_matches_activation": (
            operator.get("profile_name")
            == settings.get("profile_name")
        ),
        "no_fbr_network_attempts": not network_attempts,
        "native_cutover_still_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        ),
        "profile_remains_fail_closed": (
            operator.get("enabled") is False
            and operator.get("mode") == "Disabled"
            and operator.get("production_post_armed") is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "v2_activation_profile_migration_patch4a",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "evidence": {
            "activation_settings": settings,
            "operator_settings": operator,
        },
        "scope_proven": [
            "activation readiness no longer reads legacy FBR Settings",
            "Sandbox operator summary is company-scoped V2 profile state",
            "seller identity authority is ERPNext Company + Company Address",
            "no FBR network request is made by activation/operator summary",
        ],
        "scope_not_proven": [
            "authorized Sandbox token configuration",
            "authorized V2 reference GET",
            "Sandbox validate/POST",
            "Production activation",
            "legacy FBR health migration",
        ],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "V2 activation profile Patch 4A gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
