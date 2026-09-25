from __future__ import annotations

"""FBR adapter for ERPNext-native invoice compliance.

Canonical payload preview/readiness is V2 and consumes immutable ERPNext-native
snapshot evidence. Network validation/submission remains explicitly fail-closed
until the company-scoped V2 transport cutover is completed. This module never
creates a second sales, payment, stock or accounting ledger.
"""

import os

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from ledgix_saas.api import fbr_v2_transport
from ledgix_saas.setup import erpnext_phase9_extensions
from ledgix_saas.services import fbr_v2_payload_builder, fbr_v2_readiness
from ledgix_saas.services.fbr_submission_support import (
    create_submission_log,
    finalize_submission_log,
    parse_fbr_response,
    resolve_submission_status,
    submission_lock,
)

SUPPORTED_DOCTYPES = ("Sales Invoice", "POS Invoice")
OFFLINE_PENDING = "Offline Pending"
RECONCILIATION_REQUIRED = "Reconciliation Required"
OFFLINE_PENDING_MESSAGE = (
    "Invoice is in Known Offline / Offline Pending state. Use the controlled "
    "offline-upload workflow; generic submission is blocked."
)
RECONCILIATION_CONFIRMATION = "CONFIRMED NOT RECEIVED BY FBR"
RECONCILIATION_MESSAGE = (
    "Production FBR POST outcome may be ambiguous. Reconcile the invoice with "
    "FBR/PRAL before any retransmission."
)
TOLERANCE = 0.05

PRODUCTION_ATTEMPT_PENDING_MESSAGE = (
    "A Production FBR POST attempt was durably prepared. Until the attempt is "
    "finalized, retransmission is blocked and the invoice must be reconciled "
    "with FBR/PRAL if the worker outcome is unknown."
)
PRODUCTION_ATTEMPT_PENDING_CODE = "FBR_POST_ATTEMPT_PENDING"


def _begin_production_post_attempt(doc, payload) -> tuple[str, dict]:
    attempt_context = {
        "fbr_operation": "post",
        "fbr_mode": "Production",
        "company": doc.company,
        "network_call": False,
        "success": False,
        "attempt_state": "Prepared",
        "requires_reconciliation": True,
        "contains_secrets": False,
    }
    log_name = _create_log(
        doc,
        "Pending",
        payload=payload,
        response=attempt_context,
        error_code=PRODUCTION_ATTEMPT_PENDING_CODE,
        error_message=PRODUCTION_ATTEMPT_PENDING_MESSAGE,
    )
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        RECONCILIATION_REQUIRED,
        error_code=PRODUCTION_ATTEMPT_PENDING_CODE,
        error_message=PRODUCTION_ATTEMPT_PENDING_MESSAGE,
        log_name=log_name,
    )
    frappe.db.commit()
    return log_name, status


def _finalize_production_post_attempt(
    log_name: str,
    *,
    status: str,
    response,
    error_code: str = "",
    error_message: str = "",
    invoice_number: str = "",
) -> None:
    finalize_submission_log(
        log_name,
        status,
        response_json=response,
        error_code=error_code,
        error_message=error_message,
        fbr_invoice_number=invoice_number,
    )



# Deliberately false until the company-scoped V2 transport wiring has passed
# local runtime proof and authorized Sandbox certification. Keeping this false
# prevents any invoice Validate/POST from leaving Ledgix during the cutover.
V2_NETWORK_CUTOVER_ACTIVE = False
V2_NETWORK_CUTOVER_MESSAGE = (
    "General FBR V2 network validation/submission is not active. "
    "Sandbox traffic is allowed only through the explicitly confirmed local "
    "Sandbox certification exercise; Production remains blocked."
)
SANDBOX_NETWORK_EXERCISE_ENV = "LEDGIX_FBR_SANDBOX_NETWORK_EXERCISE"
SANDBOX_NETWORK_EXERCISE_CONFIRMATION = "SEND TO FBR SANDBOX"


def _sandbox_network_exercise_allowed(mode: str | None) -> bool:
    # Narrow exception for the exact-confirmed local certification subprocess.
    return bool(
        V2_NETWORK_CUTOVER_ACTIVE is False
        and str(mode or "").strip() == "Sandbox"
        and str(os.environ.get(SANDBOX_NETWORK_EXERCISE_ENV) or "").strip()
        == SANDBOX_NETWORK_EXERCISE_CONFIRMATION
    )


def _require_role(action: str, *, submit: bool = False) -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    allowed = {"System Manager", "Ledgix Admin"}
    if not submit:
        allowed.add("Ledgix Manager")
    if not roles.intersection(allowed):
        frappe.throw(
            f"Only {', '.join(sorted(allowed))} can {action} native FBR data.",
            frappe.PermissionError,
        )


def _reference(reference_doctype: str, reference_name: str):
    doctype = str(reference_doctype or "").strip()
    name = str(reference_name or "").strip()
    if doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("FBR native source must be Sales Invoice or POS Invoice.")
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name or ''} was not found.")
    return frappe.get_doc(doctype, name)


def _is_consolidated_pos_sales_invoice(doc) -> bool:
    if doc.doctype != "Sales Invoice" or cint(doc.get("is_return")):
        return False
    if frappe.db.exists("POS Invoice", {"consolidated_invoice": doc.name, "docstatus": 1}):
        return True
    # During ERPNext closing the POS rows may be linked immediately after the
    # consolidated Sales Invoice submit. A POS-shaped SI without a Ledgix sale
    # channel is accounting consolidation, not a second FBR source.
    return bool(cint(doc.get("is_pos")) and not str(doc.get("custom_ledgix_sale_channel") or "").strip())


def is_native_fbr_source(doc) -> bool:
    return bool(
        doc
        and doc.doctype in SUPPORTED_DOCTYPES
        and cint(doc.docstatus) == 1
        and not _is_consolidated_pos_sales_invoice(doc)
    )



def _summary(doc) -> dict:
    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "docstatus": cint(doc.docstatus),
        "customer": doc.get("customer") or "",
        "posting_date": doc.get("posting_date"),
        "is_return": bool(cint(doc.get("is_return"))),
        "return_against": doc.get("return_against") or "",
        "net_total": abs(flt(doc.get("net_total"), 2)),
        "tax_amount": abs(flt(doc.get("total_taxes_and_charges"), 2)),
        "grand_total": abs(flt(doc.get("grand_total"), 2)),
        "fbr_status": doc.get("custom_ledgix_fbr_status") or "Not Submitted",
        "fbr_invoice_number": doc.get("custom_ledgix_fbr_invoice_number") or "",
    }


def validate_native_readiness_internal(
    reference_doctype: str,
    reference_name: str,
) -> dict:
    """Compatibility wrapper over the canonical V2 readiness service."""

    doc = _reference(reference_doctype, reference_name)
    readiness = fbr_v2_readiness.evaluate_invoice_readiness(
        reference_doctype,
        reference_name,
    )

    errors = list(readiness.get("errors") or [])
    warnings = list(readiness.get("warnings") or [])

    if cint(doc.docstatus) == 0:
        errors.insert(0, "Draft ERPNext invoice cannot be used for FBR payload.")
    elif cint(doc.docstatus) == 2:
        errors.insert(0, "Cancelled ERPNext invoice cannot be used for FBR payload.")

    if _is_consolidated_pos_sales_invoice(doc):
        errors.insert(
            0,
            "Consolidated POS Sales Invoice is accounting-only; "
            "source POS Invoices own FBR submission.",
        )

    if cint(doc.get("is_return")):
        errors.append(
            "FBR V2 return payload is not activated until Debit/Credit Note "
            "semantics are proven in Sandbox."
        )

    profile = dict(readiness.get("profile") or {})
    mode = profile.get("mode") or "Disabled"
    token_configured = bool(
        profile.get("sandbox_token_configured")
        if mode == "Sandbox"
        else (
            profile.get("production_token_configured")
            if mode == "Production"
            else False
        )
    )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "reference": _summary(doc),
        "settings": {
            "source": "Ledgix FBR Integration Profile",
            "enabled": bool(profile.get("enabled")),
            "mode": mode,
            "submit_trigger": profile.get("submit_trigger") or "Manual",
            "token_configured": token_configured,
            "production_post_armed": bool(profile.get("production_post_armed")),
        },
        "v2": {
            "payload_input_ready": bool(readiness.get("payload_input_ready")),
            "sandbox_transport_ready": bool(
                readiness.get("sandbox_transport_ready")
            ),
            "production_transport_ready": bool(
                readiness.get("production_transport_ready")
            ),
            "snapshot_source": (
                (readiness.get("native_snapshot_candidate") or {}).get(
                    "snapshot_source"
                )
                or ""
            ),
            "snapshot_hash_verified": bool(
                (readiness.get("native_snapshot_candidate") or {}).get(
                    "hash_verified"
                )
            ),
        },
    }


def build_native_payload_internal(
    reference_doctype: str,
    reference_name: str,
) -> dict:
    """Build native preview exclusively through the canonical V2 builder."""

    validation = validate_native_readiness_internal(
        reference_doctype,
        reference_name,
    )
    doc = _reference(reference_doctype, reference_name)

    if not validation.get("valid"):
        return {
            "validation": validation,
            "payload": None,
            "source": {
                "doctype": doc.doctype,
                "name": doc.name,
                "is_return": bool(cint(doc.get("is_return"))),
                "authority": "ERPNext Native",
                "payload_builder": "FBR V2",
            },
            "reconciliation": {},
            "scenario_context": {
                "source": "none",
                "scenario_id": "",
            },
        }

    candidate = fbr_v2_payload_builder.build_payload_candidate(
        reference_doctype,
        reference_name,
    )
    return {
        "validation": validation,
        "payload": candidate.get("payload"),
        "source": candidate.get("source") or {},
        "reconciliation": candidate.get("reconciliation") or {},
        "scenario_context": candidate.get("scenario_context") or {},
    }

@frappe.whitelist()
def build_native_invoice_payload(reference_doctype, reference_name):
    _require_role("preview")
    return build_native_payload_internal(reference_doctype, reference_name)


def _status_fields(doc) -> dict:
    return {
        "fbr_status": doc.get("custom_ledgix_fbr_status") or "Not Submitted",
        "fbr_invoice_number": doc.get("custom_ledgix_fbr_invoice_number") or "",
        "fbr_qr_code": doc.get("custom_ledgix_fbr_qr_code") or "",
        "fbr_reference": doc.get("custom_ledgix_fbr_reference") or "",
        "fbr_submitted_at": doc.get("custom_ledgix_fbr_submitted_at"),
        "fbr_generated_at": doc.get("custom_ledgix_fbr_generated_at"),
        "fbr_upload_due_at": doc.get("custom_ledgix_fbr_upload_due_at"),
        "fbr_offline_issued_at": doc.get("custom_ledgix_fbr_offline_issued_at"),
        "fbr_offline_reason": doc.get("custom_ledgix_fbr_offline_reason") or "",
        "fbr_error_code": doc.get("custom_ledgix_fbr_error_code") or "",
        "fbr_error_message": doc.get("custom_ledgix_fbr_error_message") or "",
        "fbr_submission_log": doc.get("custom_ledgix_fbr_submission_log") or "",
        "fbr_reconciliation_required": bool(cint(doc.get("custom_ledgix_fbr_reconciliation_required"))),
    }


def _get_status(reference_doctype: str, reference_name: str) -> dict:
    return _status_fields(_reference(reference_doctype, reference_name))


@frappe.whitelist()
def get_native_fbr_status(reference_doctype, reference_name):
    _require_role("view")
    return _get_status(reference_doctype, reference_name)


def mark_native_fbr_status(
    reference_doctype: str,
    reference_name: str,
    status: str,
    *,
    fbr_invoice_number=None,
    fbr_qr_code=None,
    fbr_generated_at=None,
    fbr_upload_due_at=None,
    offline_issued_at=None,
    offline_reason=None,
    clear_upload_due_at: bool = False,
    error_code=None,
    error_message=None,
    log_name=None,
    submit_trigger=None,
) -> dict:
    erpnext_phase9_extensions.sync_all()
    doc = _reference(reference_doctype, reference_name)
    values = {
        "custom_ledgix_fbr_status": status,
        "custom_ledgix_fbr_reconciliation_required": 1 if status == RECONCILIATION_REQUIRED else 0,
    }
    if fbr_invoice_number is not None:
        values["custom_ledgix_fbr_invoice_number"] = fbr_invoice_number
        values["custom_ledgix_fbr_reference"] = fbr_invoice_number
    if fbr_qr_code is not None:
        values["custom_ledgix_fbr_qr_code"] = fbr_qr_code
    if fbr_generated_at is not None:
        values["custom_ledgix_fbr_generated_at"] = fbr_generated_at
    if fbr_upload_due_at is not None:
        values["custom_ledgix_fbr_upload_due_at"] = fbr_upload_due_at
    if offline_issued_at is not None:
        values["custom_ledgix_fbr_offline_issued_at"] = offline_issued_at
    if offline_reason is not None:
        values["custom_ledgix_fbr_offline_reason"] = str(
            offline_reason or ""
        )[:1000]
    if error_code is not None:
        values["custom_ledgix_fbr_error_code"] = error_code
    if error_message is not None:
        values["custom_ledgix_fbr_error_message"] = str(error_message or "")[:1000]
    if log_name is not None:
        values["custom_ledgix_fbr_submission_log"] = log_name
    if submit_trigger is not None:
        values["custom_ledgix_fbr_submit_trigger"] = submit_trigger
    if status in {"Validated", "Submitted"}:
        values["custom_ledgix_fbr_submitted_at"] = now_datetime()
    if status in {"Submitted", RECONCILIATION_REQUIRED} or clear_upload_due_at:
        values["custom_ledgix_fbr_upload_due_at"] = None
    frappe.db.set_value(doc.doctype, doc.name, values, update_modified=False)
    return _get_status(doc.doctype, doc.name)


def _create_log(doc, status: str, *, payload=None, response=None, error_code=None, error_message=None, invoice_number=None):
    return create_submission_log(
        doc.doctype,
        doc.name,
        "Return" if cint(doc.get("is_return")) else "Sale Invoice",
        status,
        request_json=payload,
        response_json=response,
        error_code=error_code,
        error_message=error_message,
        fbr_invoice_number=invoice_number,
        attempt_count=1 if response else 0,
    )


def _not_ready(doc, validation: dict, message: str) -> dict:
    return {
        "network_call": False,
        "status": "Not Ready",
        "reference_status": _get_status(doc.doctype, doc.name),
        "validation": validation,
        "response": None,
        "fbr_invoice_number": "",
        "fbr_qr_code": "",
        "error_code": "",
        "error_message": message,
    }


def _ready_payload(doc):
    result = build_native_payload_internal(doc.doctype, doc.name)
    validation = result.get("validation") or {}
    payload = result.get("payload")
    if not validation.get("valid"):
        return payload, validation, "Payload readiness failed."
    if not payload:
        validation.setdefault("errors", []).append("FBR payload could not be built.")
        validation["valid"] = False
        return payload, validation, "FBR payload could not be built."
    return payload, validation, ""


def _configured_for_network(settings: dict) -> str:
    if not settings.get("enabled"):
        return "FBR Integration Profile must be enabled for submission."
    mode = settings.get("mode")
    if mode not in {"Sandbox", "Production"}:
        return "FBR mode must be Sandbox or Production for submission."
    if not settings.get("token_configured"):
        return f"{mode} token is not configured."
    if mode == "Production" and not settings.get("production_post_armed"):
        return "Production posting is not armed."
    return ""


def _lock(doc):
    return submission_lock(f"{doc.doctype}:{doc.name}")


def _already_submitted(
    status: dict,
    *,
    allow_offline_upload: bool = False,
) -> dict | None:
    if status.get("fbr_status") == RECONCILIATION_REQUIRED:
        return {
            "network_call": False,
            "status": RECONCILIATION_REQUIRED,
            "reference_status": status,
            "validation": {"valid": False, "errors": [RECONCILIATION_MESSAGE], "warnings": []},
            "response": None,
            "fbr_invoice_number": status.get("fbr_invoice_number") or "",
            "fbr_qr_code": status.get("fbr_qr_code") or "",
            "error_message": status.get("fbr_error_message") or RECONCILIATION_MESSAGE,
        }
    if (
        status.get("fbr_status") == OFFLINE_PENDING
        and not allow_offline_upload
    ):
        return {
            "network_call": False,
            "status": OFFLINE_PENDING,
            "reference_status": status,
            "validation": {
                "valid": False,
                "errors": [OFFLINE_PENDING_MESSAGE],
                "warnings": [],
            },
            "response": None,
            "fbr_invoice_number": "",
            "fbr_qr_code": status.get("fbr_qr_code") or "",
            "error_code": "",
            "error_message": OFFLINE_PENDING_MESSAGE,
        }
    if status.get("fbr_invoice_number"):
        return {
            "network_call": False,
            "status": "Already Submitted",
            "reference_status": status,
            "validation": {"valid": True, "errors": [], "warnings": []},
            "response": None,
            "fbr_invoice_number": status.get("fbr_invoice_number"),
            "fbr_qr_code": status.get("fbr_qr_code") or "",
            "error_code": "",
            "error_message": "",
        }
    return None


def validate_native_with_fbr_internal(reference_doctype: str, reference_name: str, mode: str | None = None) -> dict:
    doc = _reference(reference_doctype, reference_name)
    if not is_native_fbr_source(doc):
        frappe.throw("FBR validation requires a submitted ERPNext source invoice, not a consolidated POS accounting invoice.")

    if not V2_NETWORK_CUTOVER_ACTIVE and not _sandbox_network_exercise_allowed(mode):
        validation = validate_native_readiness_internal(doc.doctype, doc.name)
        return _not_ready(
            doc,
            validation,
            V2_NETWORK_CUTOVER_MESSAGE,
        )

    payload, validation, readiness_error = _ready_payload(doc)
    if readiness_error:
        log_name = _create_log(doc, "Failed", payload=payload, error_message=readiness_error)
        status = mark_native_fbr_status(doc.doctype, doc.name, "Failed", error_message=readiness_error, log_name=log_name)
        return {
            "network_call": False,
            "status": "Failed",
            "reference_status": status,
            "validation": validation,
            "response": None,
            "error_message": readiness_error,
        }
    settings = validation.get("settings") or {}
    actual_mode = mode or settings.get("mode")
    if actual_mode not in {"Sandbox", "Production"}:
        return _not_ready(
            doc,
            validation,
            "FBR V2 validation requires Sandbox or Production mode.",
        )
    client_result = fbr_v2_transport.validate_invoice(
        company=doc.company,
        payload=payload,
        mode=actual_mode,
    )
    if not client_result.get("network_call"):
        return _not_ready(doc, validation, client_result.get("error") or "FBR validation was not sent.")
    parsed = parse_fbr_response(client_result)
    if not client_result.get("success"):
        parsed["valid"] = False
    status_name = "Validated" if parsed.get("valid") else "Failed"
    error_code = "" if parsed.get("valid") else parsed.get("error_code") or ""
    error_message = "" if parsed.get("valid") else parsed.get("error_message") or client_result.get("error") or "FBR validation failed."
    log_name = _create_log(
        doc,
        status_name,
        payload=payload,
        response=client_result,
        error_code=error_code,
        error_message=error_message,
    )
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        status_name,
        fbr_qr_code=parsed.get("qr_code") or "",
        error_code=error_code,
        error_message=error_message,
        log_name=log_name,
    )
    return {
        "network_call": True,
        "status": status_name,
        "reference_status": status,
        "validation": validation,
        "response": client_result,
        "fbr_invoice_number": "",
        "fbr_qr_code": parsed.get("qr_code") or "",
        "error_code": error_code,
        "error_message": error_message,
    }


@frappe.whitelist()
def validate_native_with_fbr(reference_doctype, reference_name):
    _require_role("validate")
    return validate_native_with_fbr_internal(reference_doctype, reference_name)


def submit_native_to_fbr_internal(
    reference_doctype: str,
    reference_name: str,
    *,
    allow_offline_upload: bool = False,
) -> dict:
    doc = _reference(reference_doctype, reference_name)
    if not is_native_fbr_source(doc):
        frappe.throw("FBR submission requires a submitted ERPNext source invoice, not a consolidated POS accounting invoice.")
    current = _get_status(doc.doctype, doc.name)
    if allow_offline_upload and current.get("fbr_status") != OFFLINE_PENDING:
        frappe.throw(
            "Controlled offline upload requires an Offline Pending invoice."
        )
    already = _already_submitted(
        current,
        allow_offline_upload=allow_offline_upload,
    )
    if already:
        return already

    validation = validate_native_readiness_internal(doc.doctype, doc.name)
    settings = validation.get("settings") or {}
    mode = settings.get("mode") or "Disabled"

    if not V2_NETWORK_CUTOVER_ACTIVE and not _sandbox_network_exercise_allowed(mode):
        return _not_ready(
            doc,
            validation,
            V2_NETWORK_CUTOVER_MESSAGE,
        )

    config_error = _configured_for_network(settings)
    if config_error:
        return _not_ready(
            doc,
            validation,
            config_error,
        )

    with _lock(doc):
        current = _get_status(doc.doctype, doc.name)
        already = _already_submitted(
            current,
            allow_offline_upload=allow_offline_upload,
        )
        if already:
            return already
        payload, validation, readiness_error = _ready_payload(doc)
        if readiness_error and allow_offline_upload:
            return _not_ready(
                doc,
                validation,
                "Offline upload remains pending: " + readiness_error,
            )
        if readiness_error:
            log_name = _create_log(doc, "Failed", payload=payload, error_message=readiness_error)
            status = mark_native_fbr_status(doc.doctype, doc.name, "Failed", error_message=readiness_error, log_name=log_name)
            return {
                "network_call": False,
                "status": "Failed",
                "reference_status": status,
                "validation": validation,
                "response": None,
                "error_message": readiness_error,
            }

        production_attempt_log = ""
        if mode == "Production":
            production_attempt_log, _ = _begin_production_post_attempt(doc, payload)

        client_result = fbr_v2_transport.post_invoice(
            company=doc.company,
            payload=payload,
            mode=mode,
        )
        if not client_result.get("network_call"):
            if production_attempt_log:
                error_message = client_result.get("error") or "FBR post was not sent."
                _finalize_production_post_attempt(
                    production_attempt_log,
                    status="Failed",
                    response=client_result,
                    error_code=str(client_result.get("http_status") or ""),
                    error_message=error_message,
                )
                status = mark_native_fbr_status(
                    doc.doctype,
                    doc.name,
                    "Failed",
                    error_code=str(client_result.get("http_status") or ""),
                    error_message=error_message,
                    log_name=production_attempt_log,
                )
                return {
                    "network_call": False,
                    "status": "Failed",
                    "log_name": production_attempt_log,
                    "reference_status": status,
                    "validation": validation,
                    "response": client_result,
                    "fbr_invoice_number": "",
                    "fbr_qr_code": "",
                    "error_code": str(client_result.get("http_status") or ""),
                    "error_message": error_message,
                }
            return _not_ready(doc, validation, client_result.get("error") or "FBR post was not sent.")
        parsed = parse_fbr_response(client_result, require_invoice_number=(mode == "Production"))
        if not client_result.get("success"):
            parsed["valid"] = False
            parsed["error_code"] = parsed.get("error_code") or str(client_result.get("http_status") or "")
            parsed["error_message"] = parsed.get("error_message") or client_result.get("error") or "FBR post failed."
        status_name, invoice_number = resolve_submission_status(mode, parsed)
        qr_code = parsed.get("qr_code") or ""
        if client_result.get("requires_reconciliation"):
            status_name = RECONCILIATION_REQUIRED
            invoice_number = ""
            parsed["error_message"] = client_result.get("error") or RECONCILIATION_MESSAGE

        success_status = status_name in {"Submitted", "Validated"}
        error_code = "" if success_status else parsed.get("error_code") or ""
        error_message = "" if success_status else parsed.get("error_message") or ""
        if production_attempt_log:
            _finalize_production_post_attempt(
                production_attempt_log,
                status=status_name,
                response=client_result,
                error_code=error_code,
                error_message=error_message,
                invoice_number=invoice_number,
            )
            log_name = production_attempt_log
        else:
            log_name = _create_log(
                doc,
                status_name,
                payload=payload,
                response=client_result,
                error_code=error_code,
                error_message=error_message,
                invoice_number=invoice_number,
            )
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            status_name,
            fbr_invoice_number=invoice_number if invoice_number else None,
            fbr_qr_code=qr_code if qr_code else None,
            fbr_generated_at=(
                parsed.get("dated")
                if status_name == "Submitted" and invoice_number
                else None
            ),
            error_code=error_code,
            error_message=error_message,
            log_name=log_name,
            clear_upload_due_at=bool(
                allow_offline_upload and client_result.get("network_call")
            ),
        )
        return {
            "network_call": True,
            "status": status_name,
            "log_name": log_name,
            "reference_status": status,
            "validation": validation,
            "response": client_result,
            "fbr_invoice_number": invoice_number,
            "fbr_qr_code": qr_code,
            "fbr_generated_at": (
                parsed.get("dated")
                if status_name == "Submitted" and invoice_number
                else ""
            ),
            "error_code": error_code,
            "error_message": error_message,
        }


@frappe.whitelist()
def submit_native_to_fbr(reference_doctype, reference_name):
    _require_role("submit", submit=True)
    return submit_native_to_fbr_internal(reference_doctype, reference_name)


def _after_commit_submit(doctype: str, name: str) -> None:
    def _run():
        try:
            submit_native_to_fbr_internal(doctype, name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Ledgix native FBR after-commit submit failed for {doctype} {name}")

    frappe.db.after_commit.add(_run)


def queue_native_for_fbr(reference_doctype: str, reference_name: str, reason: str | None = None) -> dict:
    doc = _reference(reference_doctype, reference_name)
    if not is_native_fbr_source(doc):
        return {
            "queued": False,
            "status": "Not Required",
            "reason": "Consolidated/draft/cancelled ERPNext document is not an FBR source.",
            "reference_status": _status_fields(doc),
        }
    current = _get_status(doc.doctype, doc.name)
    already = _already_submitted(current)
    if already:
        already["queued"] = False
        return already

    if not V2_NETWORK_CUTOVER_ACTIVE:
        validation = validate_native_readiness_internal(doc.doctype, doc.name)
        return {
            "queued": False,
            "status": "Not Ready",
            "reason": V2_NETWORK_CUTOVER_MESSAGE,
            "validation": validation,
            "reference_status": current,
        }

    validation = validate_native_readiness_internal(doc.doctype, doc.name)
    settings = validation.get("settings") or {}
    mode = settings.get("mode") or "Disabled"
    submit_trigger = settings.get("submit_trigger") or "Manual"
    if mode == "Disabled" or (not settings.get("enabled") and mode != "Paused"):
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            "Not Required",
            submit_trigger=submit_trigger,
        )
        return {
            "queued": False,
            "status": "Not Required",
            "reason": "FBR disabled",
            "reference_status": status,
        }

    payload, validation, readiness_error = _ready_payload(doc)
    if mode == "Paused":
        log_name = _create_log(
            doc,
            "Paused",
            payload=payload,
            error_message=reason or "FBR paused",
        )
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            "Paused",
            error_message=reason or "FBR paused",
            log_name=log_name,
            submit_trigger=submit_trigger,
        )
        return {
            "queued": False,
            "status": "Paused",
            "log_name": log_name,
            "validation": validation,
            "reference_status": status,
        }
    if readiness_error:
        log_name = _create_log(doc, "Failed", payload=payload, error_message=readiness_error)
        status = mark_native_fbr_status(
            doc.doctype,
            doc.name,
            "Failed",
            error_message=readiness_error,
            log_name=log_name,
            submit_trigger=submit_trigger,
        )
        return {"queued": False, "status": "Failed", "reason": readiness_error, "log_name": log_name, "validation": validation, "reference_status": status}

    log_name = _create_log(doc, "Pending", payload=payload, error_message=reason)
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        "Pending",
        error_message=reason or "",
        log_name=log_name,
        submit_trigger=submit_trigger,
    )
    if submit_trigger == "Manual":
        return {
            "queued": True,
            "status": "Pending",
            "reason": "Manual FBR submission required",
            "log_name": log_name,
            "validation": validation,
            "reference_status": status,
        }
    if submit_trigger == "Validate Only":
        result = validate_native_with_fbr_internal(
            doc.doctype,
            doc.name,
            mode,
        )
        result.update({"queued": True, "reason": "Validate Only flow completed"})
        return result
    if submit_trigger == "On Submit" and mode == "Production":
        _after_commit_submit(doc.doctype, doc.name)
        return {
            "queued": True,
            "status": "Pending",
            "reason": "Production FBR post queued after commit",
            "log_name": log_name,
            "validation": validation,
            "reference_status": status,
        }
    if submit_trigger == "On Submit" and mode == "Sandbox":
        result = validate_native_with_fbr_internal(
            doc.doctype,
            doc.name,
            "Sandbox",
        )
        result.update({"queued": True, "reason": "Sandbox validation completed"})
        return result
    return {"queued": True, "status": "Pending", "reason": "FBR submission queued", "log_name": log_name, "validation": validation, "reference_status": status}


def on_native_invoice_submit(doc, method=None) -> None:
    if not doc or doc.doctype not in SUPPORTED_DOCTYPES or cint(doc.docstatus) != 1:
        return
    if _is_consolidated_pos_sales_invoice(doc):
        return
    queue_native_for_fbr(doc.doctype, doc.name, reason="ERPNext native invoice submitted")


def block_cancel_after_fbr_submission(doc, method=None) -> None:
    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        return
    status = _status_fields(doc)
    if (
        status.get("fbr_invoice_number")
        or status.get("fbr_status") in {RECONCILIATION_REQUIRED, OFFLINE_PENDING}
    ):
        frappe.throw(
            _(
                "This ERPNext invoice has FBR submission/offline issuance history. "
                "Use the controlled offline, native return/note, or FBR correction "
                "workflow instead of cancellation."
            )
        )


@frappe.whitelist()
def release_native_after_fbr_reconciliation(reference_doctype, reference_name, confirmation):
    _require_role("release a reconciled invoice", submit=True)
    if str(confirmation or "").strip() != RECONCILIATION_CONFIRMATION:
        frappe.throw(f"Confirmation must be exactly: {RECONCILIATION_CONFIRMATION}")
    doc = _reference(reference_doctype, reference_name)
    current = _get_status(doc.doctype, doc.name)
    if current.get("fbr_status") != RECONCILIATION_REQUIRED:
        frappe.throw("ERPNext invoice is not awaiting FBR reconciliation.")
    message = "External FBR/PRAL reconciliation confirmed this invoice was not received. Manual retry is now permitted."
    log_name = _create_log(doc, "Pending", error_message=message)
    status = mark_native_fbr_status(
        doc.doctype,
        doc.name,
        "Pending",
        error_code="",
        error_message=message,
        log_name=log_name,
    )
    return {"released": True, "network_call": False, "status": "Pending", "reference_status": status, "log_name": log_name}
