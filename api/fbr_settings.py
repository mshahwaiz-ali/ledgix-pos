import json

import frappe
from frappe.utils import cint, now_datetime
from frappe.utils.password import get_decrypted_password


SETTINGS_DOCTYPE = "Ledgix FBR Settings"
ACTIVE_MODES = {"Sandbox", "Production"}
ALLOWED_MODES = {"Disabled", "Sandbox", "Production", "Paused", "Manual Only"}
ALLOWED_SUBMIT_TRIGGERS = {"Manual", "On Submit", "Validate Only"}
SETTINGS_WRITE_FIELDS = {
    "enabled",
    "mode",
    "submit_trigger",
    "production_post_armed",
    "block_sale_if_fbr_fails",
    "sandbox_post_on_submit",
    "retry_enabled",
    "max_retry_count",
    "offline_upload_hours",
    "seller_ntn_cnic",
    "seller_business_name",
    "seller_province",
    "seller_address",
    "software_registration_number",
    "digital_invoicing_logo",
    "pause_reason",
}
PASSWORD_FIELDS = {"sandbox_token", "production_token"}

FBR_VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
FBR_ADMIN_ROLES = {"System Manager", "Ledgix Admin"}


def assert_fbr_view_permission():
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(FBR_VIEW_ROLES):
        frappe.throw("You do not have permission to access FBR information.", frappe.PermissionError)


def assert_fbr_admin_permission(action="manage"):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(FBR_ADMIN_ROLES):
        frappe.throw(f"Only System Manager or Ledgix Admin can {action} FBR.", frappe.PermissionError)


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
}


def _doctype_exists():
    try:
        return bool(frappe.db.exists("DocType", SETTINGS_DOCTYPE))
    except Exception:
        return False


def _get_settings_doc():
    if not _doctype_exists():
        return None

    try:
        return frappe.get_single(SETTINGS_DOCTYPE)
    except Exception:
        return None


def _has_password(fieldname):
    if not fieldname or not _doctype_exists():
        return False

    try:
        return bool(
            get_decrypted_password(
                SETTINGS_DOCTYPE,
                SETTINGS_DOCTYPE,
                fieldname,
                raise_exception=False,
            )
        )
    except Exception:
        return False


def _settings_dict():
    doc = _get_settings_doc()
    if not doc:
        return dict(DISABLED_DEFAULTS)

    return {
        "enabled": bool(cint(doc.get("enabled"))),
        "mode": doc.get("mode") or "Disabled",
        "submit_trigger": doc.get("submit_trigger") or "Manual",
        "production_post_armed": bool(cint(doc.get("production_post_armed"))),
        "block_sale_if_fbr_fails": bool(cint(doc.get("block_sale_if_fbr_fails"))),
        "sandbox_post_on_submit": bool(cint(doc.get("sandbox_post_on_submit"))),
        "retry_enabled": bool(cint(doc.get("retry_enabled"))),
        "max_retry_count": cint(doc.get("max_retry_count") or 0),
        "offline_upload_hours": cint(doc.get("offline_upload_hours") or 24),
        "seller_ntn_cnic": doc.get("seller_ntn_cnic") or "",
        "seller_business_name": doc.get("seller_business_name") or "",
        "seller_province": doc.get("seller_province") or "",
        "seller_address": doc.get("seller_address") or "",
        "software_registration_number": doc.get("software_registration_number") or "",
        "digital_invoicing_logo": doc.get("digital_invoicing_logo") or "",
        "paused_at": doc.get("paused_at"),
        "pause_reason": doc.get("pause_reason") or "",
        "paused_by": doc.get("paused_by") or "",
        "last_sync_status": doc.get("last_sync_status") or "",
        "sandbox_token_configured": _has_password("sandbox_token"),
        "production_token_configured": _has_password("production_token"),
    }


def get_fbr_settings_internal():
    return _settings_dict()


@frappe.whitelist()
def get_fbr_settings():
    assert_fbr_view_permission()
    return get_fbr_settings_internal()


def _assert_fbr_settings_write_permission():
    assert_fbr_admin_permission("update")


def _coerce_settings_values(values):
    if values is None:
        return {}

    if isinstance(values, str):
        try:
            values = json.loads(values)
        except Exception:
            frappe.throw("FBR settings values must be a valid JSON object.")

    if not isinstance(values, dict):
        frappe.throw("FBR settings values must be a dictionary.")

    return values


def _set_password_value(doc, fieldname, value):
    if value in (None, ""):
        return

    if hasattr(doc, "set_password"):
        doc.set_password(fieldname, value)
    else:
        doc.set(fieldname, value)


@frappe.whitelist()
def save_fbr_settings(values):
    _assert_fbr_settings_write_permission()

    doc = _get_settings_doc()
    if not doc:
        frappe.throw("Ledgix FBR Settings DocType is not available.")

    values = _coerce_settings_values(values)
    old_mode = doc.get("mode") or "Disabled"

    for fieldname in SETTINGS_WRITE_FIELDS:
        if fieldname not in values:
            continue

        value = values.get(fieldname)

        if fieldname == "mode":
            if value not in ALLOWED_MODES:
                frappe.throw("Invalid FBR mode.")
        elif fieldname == "submit_trigger":
            if value not in ALLOWED_SUBMIT_TRIGGERS:
                frappe.throw("Invalid FBR submit trigger.")
        elif fieldname == "max_retry_count":
            value = max(0, min(10, cint(value)))
        elif fieldname == "offline_upload_hours":
            value = max(1, min(72, cint(value or 24)))
        elif fieldname in {
            "enabled",
            "production_post_armed",
            "block_sale_if_fbr_fails",
            "retry_enabled",
            "sandbox_post_on_submit",
        }:
            value = 1 if cint(value) else 0

        doc.set(fieldname, value)

    for fieldname in PASSWORD_FIELDS:
        _set_password_value(doc, fieldname, values.get(fieldname))

    mode = doc.get("mode") or "Disabled"
    pause_reason_provided = "pause_reason" in values

    # Production posting must always be deliberately re-armed after leaving
    # Production. This prevents a stale setting from becoming live later.
    if mode != "Production":
        doc.production_post_armed = 0

    if mode == "Paused" and old_mode != "Paused":
        doc.paused_at = now_datetime()
        doc.paused_by = frappe.session.user
    elif old_mode == "Paused" and mode != "Paused":
        doc.paused_at = None
        doc.paused_by = ""
        if not pause_reason_provided:
            doc.pause_reason = ""

    doc.save()
    return get_fbr_settings()


def get_fbr_mode():
    return get_fbr_settings_internal().get("mode") or "Disabled"


def get_submit_trigger():
    return get_fbr_settings_internal().get("submit_trigger") or "Manual"


def is_fbr_enabled():
    settings = get_fbr_settings_internal()
    return bool(settings.get("enabled")) and settings.get("mode") in ACTIVE_MODES


def is_fbr_paused():
    return get_fbr_mode() == "Paused"


def is_manual_only():
    settings = get_fbr_settings_internal()
    mode = settings.get("mode") or "Disabled"
    submit_trigger = settings.get("submit_trigger") or "Manual"

    return mode == "Manual Only" or (
        mode in ACTIVE_MODES and submit_trigger == "Manual"
    )


def should_submit_on_sale_submit():
    settings = get_fbr_settings_internal()
    mode = settings.get("mode")
    if mode == "Production" and not settings.get("production_post_armed"):
        return False
    return (
        bool(settings.get("enabled"))
        and mode in ACTIVE_MODES
        and settings.get("submit_trigger") == "On Submit"
    )


def get_active_fbr_token(mode=None):
    settings = get_fbr_settings_internal()
    mode = mode or settings.get("mode")

    if mode == "Sandbox":
        fieldname = "sandbox_token"
    elif mode == "Production":
        fieldname = "production_token"
    else:
        return None

    if not bool(settings.get("enabled")):
        return None

    try:
        return get_decrypted_password(
            SETTINGS_DOCTYPE,
            SETTINGS_DOCTYPE,
            fieldname,
            raise_exception=False,
        )
    except Exception:
        return None


@frappe.whitelist()
def get_fbr_control_state():
    assert_fbr_view_permission()
    return get_fbr_control_state_internal()


def get_fbr_control_state_internal():
    settings = get_fbr_settings_internal()
    mode = settings.get("mode") or "Disabled"
    submit_trigger = settings.get("submit_trigger") or "Manual"
    enabled_checked = bool(settings.get("enabled"))
    enabled = enabled_checked and mode in ACTIVE_MODES
    production_post_armed = bool(settings.get("production_post_armed"))

    token_configured = False
    if mode == "Sandbox":
        token_configured = bool(settings.get("sandbox_token_configured"))
    elif mode == "Production":
        token_configured = bool(settings.get("production_token_configured"))

    is_paused = mode == "Paused"
    manual_only = mode == "Manual Only" or (mode in ACTIVE_MODES and submit_trigger == "Manual")
    production_post_connected = bool(enabled and mode == "Production" and settings.get("production_token_configured"))
    production_post_ready = bool(production_post_connected and production_post_armed)
    auto_submit_active = bool(production_post_ready and submit_trigger == "On Submit")
    # Recovery/retransmission workers are deliberately disabled until Ledgix has
    # a reconciliation-safe way to establish that FBR did not receive an
    # ambiguous Production POST. Normal explicitly armed On Submit posting is
    # unaffected.
    retry_worker_active = False
    offline_worker_active = False
    can_manual_validate = bool(enabled and token_configured and mode in ACTIVE_MODES)
    can_manual_submit = bool(production_post_ready)
    can_auto_submit = auto_submit_active
    can_attempt_submission = bool(
        enabled
        and token_configured
        and submit_trigger in {"On Submit", "Validate Only"}
        and (mode != "Production" or production_post_armed or submit_trigger == "Validate Only")
    )

    if mode == "Disabled":
        reason = "FBR disabled"
    elif mode in ACTIVE_MODES and not enabled_checked:
        reason = "FBR disabled"
    elif mode == "Paused":
        reason = "FBR paused"
    elif mode == "Manual Only":
        reason = "Manual submission required"
    elif mode in ACTIVE_MODES and submit_trigger == "Manual":
        reason = "Manual submission required"
    elif mode in ACTIVE_MODES and not token_configured:
        reason = "FBR token not configured"
    elif mode == "Production" and submit_trigger == "On Submit" and not production_post_armed:
        reason = "Production posting is not armed"
    else:
        reason = "Ready"

    return {
        "enabled": enabled,
        "mode": mode,
        "submit_trigger": submit_trigger,
        "production_post_armed": production_post_armed,
        "can_attempt_submission": can_attempt_submission,
        "production_post_connected": production_post_connected,
        "production_post_ready": production_post_ready,
        "auto_submit_active": auto_submit_active,
        "retry_worker_active": retry_worker_active,
        "offline_worker_active": offline_worker_active,
        "can_manual_validate": can_manual_validate,
        "can_manual_submit": can_manual_submit,
        "can_auto_submit": can_auto_submit,
        "is_paused": is_paused,
        "is_manual_only": manual_only,
        "token_configured": token_configured,
        "reason": reason,
    }
