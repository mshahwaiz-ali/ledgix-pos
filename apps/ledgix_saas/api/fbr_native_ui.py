from __future__ import annotations

import frappe
from frappe.utils import cint

from ledgix_saas.api import fbr_native
from ledgix_saas.api.fbr_settings import get_fbr_control_state_internal


@frappe.whitelist()
def get_native_fbr_preview(reference_doctype, reference_name):
    fbr_native._require_role("preview")
    result = fbr_native.build_native_payload_internal(reference_doctype, reference_name)
    validation = result.get("validation") or {}
    reference = validation.get("reference") or {}
    control = get_fbr_control_state_internal()
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
            and control.get("enabled")
            and control.get("token_configured")
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
