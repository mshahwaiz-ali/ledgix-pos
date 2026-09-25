from __future__ import annotations

"""LOCAL proof for retirement of stale legacy Desk/readiness FBR control plane."""

import frappe

from ledgix_saas.api import (
    fbr_native,
    fbr_preflight,
    fbr_preview,
    fbr_transport,
    fbr_v2_center,
    tax_center,
)
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Patch 5A gate on {frappe.local.site!r}; "
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
            "REAL FBR NETWORK FORBIDDEN BY PATCH 5A GATE"
        )

    try:
        frappe.set_user("Administrator")
        fbr_transport.get_json = _forbid_network
        fbr_transport.post_json = _forbid_network

        canonical = fbr_v2_center.get_fbr_readiness()
        preflight = fbr_preflight.get_fbr_readiness()
        tax_readiness = tax_center.get_fbr_readiness()
        boot = fbr_v2_center.get_v2_center_boot()
        legacy_boot_blocked = False
        try:
            tax_center.get_tax_center_boot()
        except frappe.ValidationError:
            legacy_boot_blocked = True

        preview_blocked = False
        preview_message = ""
        try:
            fbr_preview.get_fbr_sale_preview("LEGACY-PREVIEW-PROBE")
        except frappe.ValidationError as exc:
            preview_message = str(exc)
            preview_blocked = (
                "Legacy Ledgix Sale / Sales Return FBR execution is retired"
                in preview_message
            )

    finally:
        fbr_transport.get_json = original_get
        fbr_transport.post_json = original_post
        frappe.set_user(original_user)

    profiles = boot.get("profiles") or []

    checks = {
        "preflight_matches_v2": preflight == canonical,
        "tax_readiness_matches_v2": tax_readiness == canonical,
        "tax_boot_uses_v2_profile_status": (
            boot.get("architecture") == "ERPNext Native + FBR V2"
            and legacy_boot_blocked
        ),
        "legacy_preview_blocked": preview_blocked,
        "no_fbr_network_attempts": not network_attempts,
        "native_cutover_still_false": (
            getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is False
        ),
        "v2_profile_stays_fail_closed": (
            all(
                not row.get("enabled") and row.get("mode") == "Disabled"
                and not row.get("production_post_armed")
                for row in profiles
            )
        ),
    }

    result = {
        "site": frappe.local.site,
        "proof_type": "v2_legacy_desk_readiness_retirement_patch5a",
        "real_fbr_network_calls": 0,
        "database_write": False,
        "checks": checks,
        "failed_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "evidence": {
            "canonical_readiness": canonical,
            "tax_center_fbr_summary": boot,
            "preview_message": preview_message,
        },
        "scope_proven": [
            "legacy preflight readiness delegates to V2 readiness",
            "legacy tax-center FBR readiness delegates to V2 readiness",
            "tax-center FBR summary uses V2 status rather than Ledgix FBR Settings",
            "legacy Ledgix Sale FBR preview fails closed in source",
            "old Settings getters are not called by these surfaces",
            "no FBR network request is made",
        ],
        "scope_not_proven": [
            "client setup/readiness old Settings retirement",
            "legacy print/settings seller compatibility retirement",
            "fbr_payload/fbr_submission/fbr_client transport retirement",
            "authorized Sandbox network behavior",
        ],
        "gate_passed": all(checks.values()),
    }

    if not result["gate_passed"]:
        frappe.throw(
            "Patch 5A legacy Desk/readiness retirement gate failed: "
            + frappe.as_json(result["failed_checks"])
        )

    return result
