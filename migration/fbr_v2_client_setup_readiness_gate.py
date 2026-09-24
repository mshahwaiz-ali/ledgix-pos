from __future__ import annotations

"""LOCAL read-only proof for client setup/readiness V2 FBR migration."""

import frappe

from ledgix_saas.api import (
    client_readiness,
    client_setup,
    fbr_native,
    fbr_transport,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.setup.erpnext_extensions import DEFAULT_BUSINESS_PROFILE


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Patch 5B gate on {frappe.local.site!r}; "
            f"expected {INTEGRATION_SITE!r}."
        )


def run() -> dict:
    _assert_safe_site()

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False.")

    original_user = frappe.session.user
    original_get_single = frappe.get_single
    original_get = fbr_transport.get_json
    original_post = fbr_transport.post_json

    legacy_settings_attempts = []
    network_attempts = []

    def _guarded_get_single(doctype, *args, **kwargs):
        if doctype == "Ledgix FBR Settings":
            legacy_settings_attempts.append(True)
            frappe.throw("OLD FBR SETTINGS FORBIDDEN BY PATCH 5B GATE")
        return original_get_single(doctype, *args, **kwargs)

    def _forbid_network(*args, **kwargs):
        network_attempts.append(True)
        frappe.throw("REAL FBR NETWORK FORBIDDEN BY PATCH 5B GATE")

    try:
        frappe.set_user("Administrator")
        frappe.get_single = _guarded_get_single
        fbr_transport.get_json = _forbid_network
        fbr_transport.post_json = _forbid_network

        profile = original_get_single("Ledgix Business Profile")
        company = str(profile.get("setup_company") or "").strip()
        business_profile = profile.get("business_profile") or DEFAULT_BUSINESS_PROFILE

        setup = client_setup.evaluate_client_setup(
            {
                "business_profile": business_profile,
                "company": company,
            }
        )
        readiness = client_readiness.evaluate_client_readiness(
            strict_evidence=0
        )

    finally:
        frappe.get_single = original_get_single
        fbr_transport.get_json = original_get
        fbr_transport.post_json = original_post
        frappe.set_user(original_user)

    setup_checks = {
        row.get("key"): row
        for row in setup.get("checks") or []
    }
    readiness_checks = {
        row.get("key"): row
        for row in readiness.get("checks") or []
    }

    setup_profile = setup_checks.get("fbr_integration_profile") or {}
    readiness_profile = readiness_checks.get("fbr_integration_profile") or {}
    interlock = readiness_checks.get("fbr_pre_activation_interlock") or {}
    identity = readiness_checks.get("fbr_seller_identity") or {}

    checks = {
        "setup_uses_v2_profile_check": (
            setup_profile.get("target") == "Ledgix FBR Integration Profile"
        ),
        "readiness_uses_v2_profile_check": (
            readiness_profile.get("target") == "Ledgix FBR Integration Profile"
        ),
        "production_remains_unarmed": bool(interlock.get("passed")),
        "seller_identity_target_is_erpnext": (
            identity.get("target") == "Company / Address"
            and (identity.get("details") or {}).get("authority") == "ERPNext"
        ),
        "legacy_settings_not_read": not legacy_settings_attempts,
        "no_fbr_network_attempts": not network_attempts,
        "native_cutover_still_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "v2_client_setup_readiness_migration_patch5b",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "evidence": {
            "setup_fbr_profile_check": setup_profile,
            "readiness_fbr_profile_check": readiness_profile,
            "pre_activation_interlock": interlock,
            "seller_identity_check": identity,
        },
        "scope_proven": [
            "client setup uses company-scoped V2 Integration Profile",
            "client readiness uses V2 profile Production interlock",
            "seller identity readiness uses ERPNext Company + Address",
            "old Ledgix FBR Settings singleton is not read",
            "no FBR network request is made",
        ],
        "scope_not_proven": [
            "legacy print/settings seller compatibility retirement",
            "fbr_payload/fbr_submission/fbr_client transport retirement",
            "authorized Sandbox configuration or network behavior",
        ],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Patch 5B client setup/readiness gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
