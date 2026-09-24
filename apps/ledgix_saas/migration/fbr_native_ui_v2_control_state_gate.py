from __future__ import annotations

"""Read-only LOCAL proof that native UI control state is V2-owned and fail-closed."""

import frappe

from ledgix_saas.api import fbr_native, fbr_native_ui
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing native UI V2 control-state gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    sandbox_validation = {
        "settings": {
            "source": "Ledgix FBR Integration Profile",
            "enabled": True,
            "mode": "Sandbox",
            "submit_trigger": "Manual",
            "token_configured": True,
            "production_post_armed": False,
        },
        "v2": {
            "sandbox_transport_ready": True,
            "production_transport_ready": False,
        },
    }
    production_validation = {
        "settings": {
            "source": "Ledgix FBR Integration Profile",
            "enabled": True,
            "mode": "Production",
            "submit_trigger": "Manual",
            "token_configured": True,
            "production_post_armed": True,
        },
        "v2": {
            "sandbox_transport_ready": False,
            "production_transport_ready": True,
        },
    }
    disabled_validation = {
        "settings": {
            "source": "Ledgix FBR Integration Profile",
            "enabled": False,
            "mode": "Disabled",
            "submit_trigger": "Manual",
            "token_configured": False,
            "production_post_armed": False,
        },
        "v2": {
            "sandbox_transport_ready": False,
            "production_transport_ready": False,
        },
    }

    sandbox = fbr_native_ui._v2_control_state(sandbox_validation)
    production = fbr_native_ui._v2_control_state(production_validation)
    disabled = fbr_native_ui._v2_control_state(disabled_validation)

    checks = {
        "sandbox_source_is_v2_profile": (
            sandbox.get("source") == "Ledgix FBR Integration Profile"
        ),
        "production_source_is_v2_profile": (
            production.get("source") == "Ledgix FBR Integration Profile"
        ),
        "sandbox_readiness_preserved": bool(
            sandbox.get("sandbox_transport_ready")
        ),
        "production_readiness_preserved": bool(
            production.get("production_transport_ready")
        ),
        "sandbox_actions_blocked_by_cutover": (
            sandbox.get("network_cutover_active") is False
            and sandbox.get("can_manual_validate") is False
            and sandbox.get("can_manual_submit") is False
        ),
        "production_actions_blocked_by_cutover": (
            production.get("network_cutover_active") is False
            and production.get("can_manual_validate") is False
            and production.get("can_manual_submit") is False
            and production.get("production_post_ready") is False
        ),
        "disabled_profile_stays_disabled": (
            disabled.get("enabled") is False
            and disabled.get("can_attempt_submission") is False
        ),
        "cutover_reason_exposed": (
            sandbox.get("reason") == fbr_native.V2_NETWORK_CUTOVER_MESSAGE
            and production.get("reason") == fbr_native.V2_NETWORK_CUTOVER_MESSAGE
        ),
        "native_cutover_still_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "native_ui_v2_control_state_cutover",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "evidence": {
            "sandbox": sandbox,
            "production": production,
            "disabled": disabled,
        },
        "scope_proven": [
            "native UI control state is derived from V2 Integration Profile readiness",
            "Sandbox and Production transport readiness remain distinct",
            "all native UI network actions remain blocked while cutover is False",
            "old global FBR Settings are not required by native UI control-state logic",
        ],
        "scope_not_proven": [
            "authorized Sandbox network behavior",
            "Production activation",
            "legacy Tax Center settings retirement",
        ],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Native UI V2 control-state gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
