from __future__ import annotations

"""Read-only proof for Patch 5E2B2 old-settings proof dependency retirement."""

from pathlib import Path

import frappe

from ledgix_saas.api import fbr_native
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
PROFILE_NAME = "FBR-PROFILE-00094"
APP_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_SOURCE = APP_ROOT / "api" / "fbr_settings.py"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Patch 5E2B2 gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run():
    _assert_safe_site()
    frappe.set_user("Administrator")

    old_exists = bool(frappe.db.exists("DocType", "Ledgix FBR Settings"))
    old_mode = (
        frappe.db.get_single_value("Ledgix FBR Settings", "mode")
        if old_exists
        else None
    )
    old_submit_trigger = (
        frappe.db.get_single_value("Ledgix FBR Settings", "submit_trigger")
        if old_exists
        else None
    )

    settings_source = SETTINGS_SOURCE.read_text(encoding="utf-8")
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
        "legacy_singleton_still_present_for_cleanup": old_exists,
        "compatibility_shell_source_is_inert": (
            "LEGACY_SETTINGS_RETIRED_MESSAGE" in settings_source
            and "return dict(DISABLED_DEFAULTS)" in settings_source
            and "frappe.throw(LEGACY_SETTINGS_RETIRED_MESSAGE)" in settings_source
            and "return None" in settings_source
            and "get_decrypted_password" not in settings_source
            and "frappe.get_single(" not in settings_source
            and "frappe.db." not in settings_source
            and ".save(" not in settings_source
        ),
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
        "proof_type": "v2_old_settings_proof_dependency_retirement_patch5e2b2",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "old_singleton_evidence": {
            "exists": old_exists,
            "mode": old_mode,
            "submit_trigger": old_submit_trigger,
        },
        "profile": dict(profile),
        "checks": checks,
        "failed_checks": [key for key, passed in checks.items() if not passed],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Patch 5E2B2 old-settings proof dependency retirement gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
