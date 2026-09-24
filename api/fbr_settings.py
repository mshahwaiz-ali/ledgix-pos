from __future__ import annotations

"""Fail-closed compatibility shell for the retired pre-V2 FBR Settings API.

The company-scoped Ledgix FBR Integration Profile is the only live FBR
configuration authority. This module is retained temporarily so historical
gates/imports fail safely while the old singleton DocType still exists.
"""

import frappe


SETTINGS_DOCTYPE = "Ledgix FBR Settings"
LEGACY_SETTINGS_RETIRED_MESSAGE = (
    "Ledgix FBR Settings is retired. "
    "Use the company-scoped Ledgix FBR Integration Profile in Tax & FBR Center."
)

FBR_VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
FBR_ADMIN_ROLES = {"System Manager", "Ledgix Admin"}

DISABLED_DEFAULTS = {
    "enabled": False,
    "mode": "Disabled",
    "submit_trigger": "Manual",
    "production_post_armed": False,
    "block_sale_if_fbr_fails": False,
    "sandbox_post_on_submit": False,
    "retry_enabled": False,
    "max_retry_count": 0,
    "offline_upload_hours": 24,
    "seller_ntn_cnic": "",
    "seller_business_name": "",
    "seller_province": "",
    "seller_address": "",
    "software_registration_number": "",
    "digital_invoicing_logo": "",
    "paused_at": None,
    "pause_reason": "",
    "paused_by": "",
    "last_sync_status": "",
    "sandbox_token_configured": False,
    "production_token_configured": False,
    "retired": True,
    "retired_message": LEGACY_SETTINGS_RETIRED_MESSAGE,
}


def assert_fbr_view_permission():
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(FBR_VIEW_ROLES):
        frappe.throw(
            "You do not have permission to access FBR information.",
            frappe.PermissionError,
        )


def assert_fbr_admin_permission(action="manage"):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(FBR_ADMIN_ROLES):
        frappe.throw(
            f"Only System Manager or Ledgix Admin can {action} FBR.",
            frappe.PermissionError,
        )


def get_fbr_settings_internal():
    """Return inert compatibility state without reading the retired singleton."""

    return dict(DISABLED_DEFAULTS)


@frappe.whitelist()
def get_fbr_settings():
    assert_fbr_view_permission()
    return get_fbr_settings_internal()


@frappe.whitelist()
def save_fbr_settings(values=None):
    """Reject all writes to the retired singleton API."""

    assert_fbr_admin_permission("update")
    frappe.throw(LEGACY_SETTINGS_RETIRED_MESSAGE)


def get_fbr_mode():
    return "Disabled"


def get_submit_trigger():
    return "Manual"


def is_fbr_enabled():
    return False


def is_fbr_paused():
    return False


def is_manual_only():
    return True


def should_submit_on_sale_submit():
    return False


def get_active_fbr_token(mode=None):
    """Never expose/read a legacy token; V2 owns credentials."""

    return None


@frappe.whitelist()
def get_fbr_control_state():
    assert_fbr_view_permission()
    return get_fbr_control_state_internal()


def get_fbr_control_state_internal():
    return {
        "enabled": False,
        "mode": "Disabled",
        "submit_trigger": "Manual",
        "production_post_armed": False,
        "can_attempt_submission": False,
        "production_post_connected": False,
        "production_post_ready": False,
        "auto_submit_active": False,
        "retry_worker_active": False,
        "offline_worker_active": False,
        "can_manual_validate": False,
        "can_manual_submit": False,
        "can_auto_submit": False,
        "is_paused": False,
        "is_manual_only": True,
        "token_configured": False,
        "reason": "Legacy FBR Settings retired",
        "retired": True,
        "retired_message": LEGACY_SETTINGS_RETIRED_MESSAGE,
    }
