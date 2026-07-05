import frappe
from frappe.utils import cint, flt

from ledgix_saas.api.fbr_settings import get_fbr_control_state
from ledgix_saas.api.fbr_payload import (
    _build_sale_invoice_payload_internal,
    _require_fbr_view_permission,
    _validate_sale_fbr_readiness_internal,
    get_sale_for_fbr,
)


# Manual FBR preview only; this module must never submit or mutate invoices.
def _dedupe_messages(messages):
    deduped = []
    seen = set()

    for message in messages or []:
        text = str(message)
        if text in seen:
            continue
        seen.add(text)
        deduped.append(text)

    return deduped


def _sale_summary(sale_doc=None):
    if not sale_doc:
        return {
            "customer": "",
            "posting_date": None,
            "total_amount": 0,
            "tax_amount": 0,
            "grand_total": 0,
            "fbr_status": "",
            "tax_detail_count": 0,
        }

    return {
        "customer": sale_doc.get("customer") or "",
        "posting_date": sale_doc.get("posting_date") or sale_doc.get("sale_date"),
        "total_amount": flt(sale_doc.get("total_amount"), 2),
        "tax_amount": flt(sale_doc.get("tax_amount"), 2),
        "grand_total": flt(sale_doc.get("grand_total"), 2),
        "fbr_status": sale_doc.get("fbr_status") or "",
        "tax_detail_count": len(sale_doc.get("tax_details") or []),
    }


def _normalize_readiness(validation=None, extra_errors=None, extra_warnings=None):
    validation = validation or {}
    errors = list(validation.get("errors") or [])
    warnings = list(validation.get("warnings") or [])

    errors.extend(extra_errors or [])
    warnings.extend(extra_warnings or [])

    return {
        "ready": bool(validation.get("valid")) and not errors,
        "errors": _dedupe_messages(errors),
        "warnings": _dedupe_messages(warnings),
    }


def _empty_preview(sale_name, control_state, sale_doc=None, errors=None, warnings=None):
    readiness = _normalize_readiness(
        {"valid": False, "errors": [], "warnings": []},
        extra_errors=errors,
        extra_warnings=warnings,
    )

    return {
        "sale_name": sale_name or "",
        "control_state": control_state,
        "readiness": readiness,
        "sale_summary": _sale_summary(sale_doc),
        "payload": None,
        "can_submit_now": False,
        "can_validate_now": False,
    }


def _can_validate_now(sale_doc, readiness, control_state):
    return bool(
        sale_doc
        and cint(sale_doc.docstatus) == 1
        and readiness.get("ready")
        and control_state.get("mode") == "Sandbox"
        and control_state.get("enabled")
        and control_state.get("token_configured")
    )


def _can_submit_now(sale_doc, readiness, control_state):
    return bool(
        sale_doc
        and cint(sale_doc.docstatus) == 1
        and readiness.get("ready")
        and control_state.get("can_manual_submit")
        and not sale_doc.get("fbr_invoice_number")
    )


@frappe.whitelist()
def get_fbr_sale_preview(sale_name):
    _require_fbr_view_permission("preview")
    control_state = get_fbr_control_state()

    if not sale_name:
        return _empty_preview(
            sale_name,
            control_state,
            errors=["sale_name is required."],
        )

    sale_doc = get_sale_for_fbr(sale_name)
    if not sale_doc:
        return _empty_preview(
            sale_name,
            control_state,
            errors=[f"Ledgix Sale {sale_name or ''} was not found."],
        )

    if cint(sale_doc.docstatus) != 1:
        return _empty_preview(
            sale_name,
            control_state,
            sale_doc=sale_doc,
            errors=["FBR preview requires submitted sale."],
        )

    validation = {}
    validation_errors = []
    payload_errors = []
    payload = None

    try:
        validation = _validate_sale_fbr_readiness_internal(sale_name) or {}
    except Exception as exc:
        validation_errors.append(str(exc))

    try:
        payload_result = _build_sale_invoice_payload_internal(sale_name) or {}
        payload = payload_result.get("payload")
        payload_validation = payload_result.get("validation") or {}

        validation = {
            "valid": bool(validation.get("valid")) and bool(payload_validation.get("valid")),
            "errors": _dedupe_messages(
                list(validation.get("errors") or []) + list(payload_validation.get("errors") or [])
            ),
            "warnings": _dedupe_messages(
                list(validation.get("warnings") or []) + list(payload_validation.get("warnings") or [])
            ),
        }
    except Exception as exc:
        payload_errors.append(str(exc))

    readiness = _normalize_readiness(
        validation,
        extra_errors=validation_errors + payload_errors,
    )

    return {
        "sale_name": sale_name,
        "control_state": control_state,
        "readiness": readiness,
        "sale_summary": _sale_summary(sale_doc),
        "payload": payload,
        "can_submit_now": _can_submit_now(sale_doc, readiness, control_state),
        "can_validate_now": _can_validate_now(sale_doc, readiness, control_state),
    }
