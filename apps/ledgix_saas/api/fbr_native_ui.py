from __future__ import annotations

import frappe
from frappe.utils import cint

from ledgix_saas.api import fbr_native


ACTIVE_MODES = {"Sandbox", "Production"}


def _v2_control_state(validation: dict) -> dict:
    settings = dict(validation.get("settings") or {})
    v2 = dict(validation.get("v2") or {})

    mode = settings.get("mode") or "Disabled"
    submit_trigger = settings.get("submit_trigger") or "Manual"
    enabled_checked = bool(settings.get("enabled"))
    enabled = bool(enabled_checked and mode in ACTIVE_MODES)
    token_configured = bool(settings.get("token_configured"))
    production_post_armed = bool(settings.get("production_post_armed"))
    cutover_active = bool(fbr_native.V2_NETWORK_CUTOVER_ACTIVE)

    sandbox_transport_ready = bool(v2.get("sandbox_transport_ready"))
    production_transport_ready = bool(v2.get("production_transport_ready"))

    production_post_connected = bool(
        enabled
        and mode == "Production"
        and token_configured
    )
    production_post_ready = bool(
        cutover_active
        and production_transport_ready
    )
    auto_submit_active = bool(
        production_post_ready
        and submit_trigger == "On Submit"
    )

    can_manual_validate = bool(
        cutover_active
        and (
            (mode == "Sandbox" and sandbox_transport_ready)
            or (
                mode == "Production"
                and enabled
                and token_configured
            )
        )
    )
    can_manual_submit = production_post_ready
    can_auto_submit = auto_submit_active
    can_attempt_submission = bool(
        cutover_active
        and (
            sandbox_transport_ready
            if mode == "Sandbox"
            else production_transport_ready
            if mode == "Production"
            else False
        )
    )

    is_paused = mode == "Paused"
    is_manual_only = bool(
        mode in ACTIVE_MODES
        and submit_trigger == "Manual"
    )

    if not cutover_active:
        reason = fbr_native.V2_NETWORK_CUTOVER_MESSAGE
    elif mode == "Disabled":
        reason = "FBR disabled"
    elif mode in ACTIVE_MODES and not enabled_checked:
        reason = "FBR Integration Profile is disabled"
    elif mode == "Paused":
        reason = "FBR paused"
    elif mode in ACTIVE_MODES and not token_configured:
        reason = "FBR token not configured"
    elif mode == "Sandbox" and not sandbox_transport_ready:
        reason = "Sandbox transport is not ready"
    elif mode == "Production" and not production_transport_ready:
        reason = (
            "Production transport is not ready; complete Sandbox certification "
            "and arm Production posting."
        )
    elif submit_trigger == "Manual":
        reason = "Manual submission required"
    else:
        reason = "Ready"

    return {
        "source": settings.get("source") or "Ledgix FBR Integration Profile",
        "enabled": enabled,
        "mode": mode,
        "submit_trigger": submit_trigger,
        "production_post_armed": production_post_armed,
        "can_attempt_submission": can_attempt_submission,
        "production_post_connected": production_post_connected,
        "production_post_ready": production_post_ready,
        "auto_submit_active": auto_submit_active,
        "retry_worker_active": False,
        "offline_worker_active": False,
        "can_manual_validate": can_manual_validate,
        "can_manual_submit": can_manual_submit,
        "can_auto_submit": can_auto_submit,
        "is_paused": is_paused,
        "is_manual_only": is_manual_only,
        "token_configured": token_configured,
        "sandbox_transport_ready": sandbox_transport_ready,
        "production_transport_ready": production_transport_ready,
        "network_cutover_active": cutover_active,
        "reason": reason,
    }


@frappe.whitelist()
def get_native_fbr_preview(reference_doctype, reference_name):
    fbr_native._require_role("preview")
    result = fbr_native.build_native_payload_internal(reference_doctype, reference_name)
    validation = result.get("validation") or {}
    reference = validation.get("reference") or {}
    control = _v2_control_state(validation)
    doc = fbr_native._reference(reference_doctype, reference_name)
    status = fbr_native._status_fields(doc)
    ready = bool(validation.get("valid"))
    return {
        "reference_doctype": doc.doctype,
        "reference_name": doc.name,
        "sale_name": doc.name,
        "control_state": control,
        "readiness": {
            "ready": ready,
            "errors": list(validation.get("errors") or []),
            "warnings": list(validation.get("warnings") or []),
        },
        "sale_summary": {
            "name": doc.name,
            "doctype": doc.doctype,
            "customer": doc.get("customer") or "",
            "posting_date": doc.get("posting_date"),
            "total_amount": abs(float(doc.get("net_total") or 0)),
            "tax_amount": abs(float(doc.get("total_taxes_and_charges") or 0)),
            "grand_total": abs(float(doc.get("grand_total") or 0)),
            "fbr_status": status.get("fbr_status") or "",
            "is_return": bool(cint(doc.get("is_return"))),
        },
        "payload": result.get("payload"),
        "can_submit_now": bool(
            ready
            and control.get("can_manual_submit")
            and not status.get("fbr_invoice_number")
            and status.get("fbr_status") != fbr_native.RECONCILIATION_REQUIRED
        ),
        "can_validate_now": bool(
            ready
            and control.get("can_manual_validate")
            and control.get("mode") == "Sandbox"
        ),
        "source_authority": "ERPNext",
        "reference": reference,
    }


@frappe.whitelist()
def validate_native_fbr_sandbox(reference_doctype, reference_name):
    fbr_native._require_role("validate")
    return fbr_native.validate_native_with_fbr_internal(reference_doctype, reference_name, "Sandbox")


@frappe.whitelist()
def validate_native_fbr_production(reference_doctype, reference_name):
    fbr_native._require_role("validate")
    return fbr_native.validate_native_with_fbr_internal(reference_doctype, reference_name, "Production")
