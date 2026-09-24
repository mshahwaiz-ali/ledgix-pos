from __future__ import annotations

"""Read-only, non-secret status authority for FBR V2 observability."""

import frappe

from ledgix_saas.api import fbr_native, fbr_transport
from ledgix_saas.services import fbr_v2_readiness


VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
ACTIVE_MODES = {"Sandbox", "Production"}


def assert_fbr_v2_view_permission() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(VIEW_ROLES):
        frappe.throw(
            "You do not have permission to access FBR status.",
            frappe.PermissionError,
        )


def _setup_company() -> str:
    try:
        return str(
            frappe.db.get_single_value(
                "Ledgix Business Profile",
                "setup_company",
            )
            or ""
        ).strip()
    except Exception:
        return ""


def get_fbr_v2_status_internal() -> dict:
    company = _setup_company()
    bundle = fbr_v2_readiness.get_company_profile_state(company)
    profile = dict(bundle.get("profile") or {})
    certification = dict(bundle.get("sandbox_certification") or {})

    mode = profile.get("mode") or "Disabled"
    enabled = bool(
        profile.get("exists")
        and profile.get("enabled")
        and mode in ACTIVE_MODES
    )
    requests_ready = bool(fbr_transport.requests_available())
    cutover_active = bool(fbr_native.V2_NETWORK_CUTOVER_ACTIVE)

    sandbox_token_configured = bool(profile.get("sandbox_token_configured"))
    production_token_configured = bool(profile.get("production_token_configured"))
    production_post_armed = bool(profile.get("production_post_armed"))
    certification_complete = bool(certification.get("complete"))

    sandbox_transport_configured = bool(
        requests_ready
        and enabled
        and mode == "Sandbox"
        and sandbox_token_configured
    )
    production_validate_configured = bool(
        requests_ready
        and enabled
        and mode == "Production"
        and production_token_configured
    )
    production_post_configured = bool(
        production_validate_configured
        and production_post_armed
        and certification_complete
    )

    token_configured = bool(
        sandbox_token_configured
        if mode == "Sandbox"
        else production_token_configured
        if mode == "Production"
        else False
    )

    return {
        "source": "Ledgix FBR Integration Profile",
        "architecture": "ERPNext Native + FBR V2",
        "company": company,
        "profile_name": profile.get("name") or "",
        "profile_exists": bool(profile.get("exists")),
        "mode": mode,
        "enabled": enabled,
        "submit_trigger": profile.get("submit_trigger") or "Manual",
        "requests_available": requests_ready,
        "sandbox_token_configured": sandbox_token_configured,
        "production_token_configured": production_token_configured,
        "token_configured": token_configured,
        "production_post_armed": production_post_armed,
        "sandbox_certification_name": certification.get("name") or "",
        "sandbox_certification_status": certification.get("status") or "",
        "sandbox_certification_evidence_complete": bool(
            certification.get("evidence_complete")
        ),
        "sandbox_certification_complete": certification_complete,
        "sandbox_transport_configured": sandbox_transport_configured,
        "production_validate_configured": production_validate_configured,
        "production_post_configured": production_post_configured,
        "sandbox_validate_connected": bool(
            cutover_active and sandbox_transport_configured
        ),
        "sandbox_post_connected": bool(
            cutover_active and sandbox_transport_configured
        ),
        "production_validate_connected": bool(
            cutover_active and production_validate_configured
        ),
        "production_post_connected": bool(
            cutover_active and production_post_configured
        ),
        "network_cutover_active": cutover_active,
        "network_enabled": bool(
            cutover_active
            and (
                sandbox_transport_configured
                or production_validate_configured
            )
        ),
        "contains_secrets": False,
        "network_call": False,
    }
