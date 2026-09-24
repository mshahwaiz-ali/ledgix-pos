from __future__ import annotations

"""Read-only proof for Patch 5E1A old-settings runtime retirement."""

import frappe

from ledgix_saas.api import fbr_native, fbr_settings
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
PROFILE_NAME = "FBR-PROFILE-00094"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Patch 5E1A gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run():
    _assert_safe_site()
    frappe.set_user("Administrator")

    old_mode = (
        frappe.db.get_single_value("Ledgix FBR Settings", "mode")
        if frappe.db.exists("DocType", "Ledgix FBR Settings")
        else None
    )
    old_submit_trigger = (
        frappe.db.get_single_value("Ledgix FBR Settings", "submit_trigger")
        if frappe.db.exists("DocType", "Ledgix FBR Settings")
        else None
    )

    compatibility = fbr_settings.get_fbr_settings_internal()
    control = fbr_settings.get_fbr_control_state_internal()
    legacy_token = fbr_settings.get_active_fbr_token("Sandbox")

    save_retired = False
    save_message = ""
    try:
        fbr_settings.save_fbr_settings({"mode": "Production"})
    except Exception as exc:
        save_message = str(exc)
        save_retired = "retired" in save_message.lower()

    profile = frappe.db.get_value(
        PROFILE_DOCTYPE,
        PROFILE_NAME,
        [
            "name",
            "enabled",
            "mode",
            "submit_trigger",
            "production_post_armed",
            "reference_sync_status",
        ],
        as_dict=True,
    ) or {}

    checks = {
        "legacy_singleton_still_present_for_compatibility": bool(
            frappe.db.exists("DocType", "Ledgix FBR Settings")
        ),
        "compatibility_state_ignores_stale_singleton": (
            compatibility.get("retired") is True
            and compatibility.get("enabled") is False
            and compatibility.get("mode") == "Disabled"
            and compatibility.get("submit_trigger") == "Manual"
        ),
        "legacy_control_is_fail_closed": (
            control.get("retired") is True
            and control.get("enabled") is False
            and control.get("can_attempt_submission") is False
            and control.get("can_manual_submit") is False
        ),
        "legacy_token_is_never_read": legacy_token is None,
        "legacy_settings_write_rejected": save_retired,
        "v2_profile_exact_safe_state": (
            profile.get("name") == PROFILE_NAME
            and not bool(profile.get("enabled"))
            and profile.get("mode") == "Disabled"
            and profile.get("submit_trigger") == "Manual"
            and not bool(profile.get("production_post_armed"))
            and profile.get("reference_sync_status") == "Never Synced"
        ),
        "native_cutover_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "v2_old_settings_runtime_cleanup_patch5e1a",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "old_singleton_evidence": {
            "mode": old_mode,
            "submit_trigger": old_submit_trigger,
        },
        "compatibility_state": compatibility,
        "control_state": control,
        "save_retired_message": save_message,
        "profile": dict(profile),
        "checks": checks,
        "failed_checks": [key for key, passed in checks.items() if not passed],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Patch 5E1A old-settings runtime cleanup gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
