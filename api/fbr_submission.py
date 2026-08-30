import json

import frappe
from frappe.utils import cint, now_datetime

from ledgix_saas.api import fbr_client
from ledgix_saas.api.fbr_payload import _build_sale_invoice_payload_internal
from ledgix_saas.api.fbr_settings import get_fbr_control_state_internal, get_fbr_settings_internal


RECONCILIATION_REQUIRED = "Reconciliation Required"
RECONCILIATION_CONFIRMATION = "CONFIRMED NOT RECEIVED BY FBR"
RECONCILIATION_MESSAGE = (
    "Production FBR POST outcome may be ambiguous. Reconcile the invoice with FBR/PRAL before any retransmission."
)

ALLOWED_STATUSES = {
    "Not Required",
    "Pending",
    "Validated",
    "Submitted",
    "Failed",
    RECONCILIATION_REQUIRED,
    "Offline Pending",
    "Skipped",
    "Paused",
}
FINAL_ATTEMPT_STATUSES = {
    "Validated",
    "Submitted",
    "Failed",
    RECONCILIATION_REQUIRED,
    "Skipped",
    "Paused",
    "Not Required",
}


def serialize_json(data):
    if data in (None, ""):
        return None
    if isinstance(data, str):
        return data
    try:
        return frappe.as_json(data)
    except Exception:
        return json.dumps(data, default=str, ensure_ascii=False)


def normalize_fbr_status(status):
    normalized = status or "Pending"
    if normalized not in ALLOWED_STATUSES:
        frappe.throw(f"Invalid FBR status: {normalized}")
    return normalized


def _safe_message(value):
    text = str(value or "")
    if "Bearer " in text:
        text = text.split("Bearer ", 1)[0].rstrip()
    return text


def _extract_fbr_qr_code(response):
    if not isinstance(response, dict):
        return ""

    for key in ("QRCode", "qrCode", "qr_code", "QR_CODE", "qrString"):
        value = response.get(key)
        if value not in (None, ""):
            return str(value).strip()

    validation_response = response.get("validationResponse") or {}
    if isinstance(validation_response, dict):
        for key in ("QRCode", "qrCode", "qr_code", "QR_CODE", "qrString"):
            value = validation_response.get(key)
            if value not in (None, ""):
                return str(value).strip()

    return ""


def _is_network_failure(client_result):
    if not client_result or not client_result.get("network_call"):
        return False
    if client_result.get("status") == "Network Error":
        return True
    if client_result.get("http_status") in (None, "") and client_result.get("error"):
        return True
    return False


def _is_ambiguous_production_post(mode, client_result):
    return bool(
        mode == "Production"
        and client_result
        and client_result.get("network_call")
        and str(client_result.get("fbr_operation") or "").strip().lower() == "post"
        and _is_network_failure(client_result)
    )


def _resolve_submission_status(mode, parsed):
    if not parsed.get("valid"):
        return "Failed", ""

    invoice_number = str(parsed.get("invoice_number") or "").strip()
    qr_code = str(parsed.get("qr_code") or "").strip()

    if mode == "Production":
        if invoice_number:
            return "Submitted", invoice_number
        return "Failed", ""

    if invoice_number:
        return "Submitted", invoice_number
    if qr_code:
        return "Validated", ""
    return "Validated", ""


def parse_fbr_response(response, require_invoice_number=False):
    source = response.get("response") if isinstance(response, dict) and "response" in response else response
    if not isinstance(source, dict):
        return {
            "valid": False,
            "invoice_number": "",
            "qr_code": "",
            "dated": "",
            "status_code": "",
            "error_code": "",
            "error_message": "FBR response was not JSON.",
            "item_statuses": [],
        }

    validation_response = source.get("validationResponse") or {}
    if not isinstance(validation_response, dict):
        validation_response = {}

    invoice_statuses = validation_response.get("invoiceStatuses") or []
    if not isinstance(invoice_statuses, list):
        invoice_statuses = []

    item_statuses = []
    item_invalid = False
    for item in invoice_statuses:
        item = item if isinstance(item, dict) else {}
        item_status = str(item.get("status") or "").strip()
        item_code = str(item.get("statusCode") or "").strip()
        item_error_code = str(item.get("errorCode") or "").strip()
        item_error = _safe_message(item.get("error") or item.get("message"))
        if (item_status and item_status.lower() == "invalid") or (item_code and item_code != "00"):
            item_invalid = True
        item_statuses.append({
            "status": item_status,
            "status_code": item_code,
            "error_code": item_error_code,
            "error": item_error,
        })

    status = str(validation_response.get("status") or source.get("status") or "").strip()
    status_code = str(validation_response.get("statusCode") or source.get("statusCode") or "").strip()
    invoice_number = str(source.get("invoiceNumber") or validation_response.get("invoiceNumber") or "").strip()
    dated = source.get("dated") or validation_response.get("dated") or ""
    top_valid = status.lower() == "valid" and status_code == "00"
    valid = bool(top_valid and not item_invalid)
    if require_invoice_number and not invoice_number:
        valid = False

    first_item_error = next((row for row in item_statuses if row.get("error_code") or row.get("error")), {})
    error_code = (
        validation_response.get("errorCode")
        or source.get("errorCode")
        or first_item_error.get("error_code")
        or (status_code if status_code and status_code != "00" else "")
        or ""
    )
    error_message = _safe_message(
        validation_response.get("error")
        or validation_response.get("message")
        or source.get("error")
        or source.get("message")
        or first_item_error.get("error")
        or ("FBR invoice number was missing from production post response." if require_invoice_number and not invoice_number else "")
        or ("FBR validation failed." if not valid else "")
    )

    return {
        "valid": valid,
        "invoice_number": invoice_number,
        "qr_code": _extract_fbr_qr_code(source),
        "dated": dated,
        "status_code": status_code,
        "error_code": str(error_code or ""),
        "error_message": error_message,
        "item_statuses": item_statuses,
    }


def create_submission_log(
    reference_doctype,
    reference_name,
    invoice_type,
    status,
    request_json=None,
    response_json=None,
    error_code=None,
    error_message=None,
    fbr_invoice_number=None,
    attempt_count=None,
    next_retry_time=None,
):
    if not reference_doctype:
        frappe.throw("reference_doctype is required for FBR submission log.")
    if not reference_name:
        frappe.throw("reference_name is required for FBR submission log.")

    status = normalize_fbr_status(status)
    log = frappe.new_doc("Ledgix FBR Submission Log")
    log.reference_doctype = reference_doctype
    log.reference_name = reference_name
    log.invoice_type = invoice_type or "Sale Invoice"
    log.fbr_status = status
    log.fbr_invoice_number = fbr_invoice_number or ""
    log.attempt_count = cint(attempt_count or 0)
    log.next_retry_time = next_retry_time
    log.request_json = serialize_json(request_json)
    log.response_json = serialize_json(response_json)
    log.error_code = error_code
    log.error_message = _safe_message(error_message)
    log.submitted_by = getattr(frappe.session, "user", None)

    if status in FINAL_ATTEMPT_STATUSES:
        log.submitted_at = now_datetime()

    log.insert(ignore_permissions=True)
    return log.name


def _require_fbr_submit_permission(action="submit"):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin"}):
        frappe.throw(f"Only System Manager or Ledgix Admin can {action} with FBR.", frappe.PermissionError)


def _require_fbr_validate_permission(action="validate"):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}):
        frappe.throw(
            f"Only System Manager, Ledgix Admin, or Ledgix Manager can {action} with FBR.",
            frappe.PermissionError,
        )


def _require_fbr_view_permission(action="view"):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}):
        frappe.throw(f"Only System Manager, Ledgix Admin, or Ledgix Manager can {action} FBR data.", frappe.PermissionError)


def _not_ready(sale_name, validation=None, errors=None, warnings=None):
    validation = validation or {}
    merged_errors = list(validation.get("errors") or [])
    merged_errors.extend(errors or [])
    merged_warnings = list(validation.get("warnings") or [])
    merged_warnings.extend(warnings or [])
    return {
        "network_call": False,
        "status": "Not Ready",
        "log_name": "",
        "sale_status": _get_sale_fbr_status(sale_name) if sale_name and frappe.db.exists("Ledgix Sale", sale_name) else {},
        "validation": {"valid": False, "errors": merged_errors, "warnings": merged_warnings},
        "response": None,
        "fbr_invoice_number": "",
        "error_code": "",
        "error_message": "; ".join(merged_errors),
    }


def _reconciliation_result(current_status, key):
    message = current_status.get("fbr_error_message") or RECONCILIATION_MESSAGE
    return {
        "network_call": False,
        "status": RECONCILIATION_REQUIRED,
        "log_name": current_status.get("fbr_submission_log") or "",
        key: current_status,
        "validation": {"valid": False, "errors": [message], "warnings": []},
        "response": None,
        "fbr_invoice_number": current_status.get("fbr_invoice_number") or "",
        "fbr_qr_code": current_status.get("fbr_qr_code") or "",
        "error_code": current_status.get("fbr_error_code") or "",
        "error_message": message,
    }


def _build_ready_payload(sale_name):
    payload_result = _build_sale_invoice_payload_internal(sale_name) or {}
    payload = payload_result.get("payload")
    validation = payload_result.get("validation") or {}
    if not validation.get("valid"):
        return payload, validation, "Payload readiness failed."
    if not payload:
        validation.setdefault("errors", []).append("FBR payload could not be built.")
        validation["valid"] = False
        return payload, validation, "FBR payload could not be built."
    return payload, validation, ""


@frappe.whitelist()
def get_sale_fbr_status(sale_name):
    _require_fbr_view_permission("view")
    return _get_sale_fbr_status(sale_name)


def _get_sale_fbr_status(sale_name):
    if not sale_name or not frappe.db.exists("Ledgix Sale", sale_name):
        frappe.throw(f"Ledgix Sale {sale_name or ''} was not found.")
    fields = [
        "fbr_status",
        "fbr_invoice_number",
        "fbr_qr_code",
        "fbr_submitted_at",
        "fbr_upload_due_at",
        "fbr_error_code",
        "fbr_error_message",
        "fbr_submission_log",
    ]
    return dict(frappe.db.get_value("Ledgix Sale", sale_name, fields, as_dict=True) or {})


def mark_sale_fbr_status(
    sale_name,
    status,
    fbr_invoice_number=None,
    fbr_qr_code=None,
    fbr_upload_due_at=None,
    error_code=None,
    error_message=None,
    log_name=None,
):
    if not sale_name or not frappe.db.exists("Ledgix Sale", sale_name):
        frappe.throw(f"Ledgix Sale {sale_name or ''} was not found.")

    values = {"fbr_status": normalize_fbr_status(status)}
    if fbr_invoice_number is not None:
        values["fbr_invoice_number"] = fbr_invoice_number
    if fbr_qr_code is not None:
        values["fbr_qr_code"] = fbr_qr_code
    if fbr_upload_due_at is not None:
        values["fbr_upload_due_at"] = fbr_upload_due_at
    if error_code is not None:
        values["fbr_error_code"] = error_code
    if error_message is not None:
        values["fbr_error_message"] = _safe_message(error_message)
    if log_name is not None:
        values["fbr_submission_log"] = log_name
    if status in {"Submitted", "Validated"}:
        values["fbr_submitted_at"] = now_datetime()
    if status in {"Submitted", RECONCILIATION_REQUIRED}:
        values["fbr_upload_due_at"] = None

    frappe.db.set_value("Ledgix Sale", sale_name, values, update_modified=False)
    return _get_sale_fbr_status(sale_name)


def _run_validate_sale(sale_name, mode):
    if not sale_name:
        frappe.throw("sale_name is required.")
    if not frappe.db.exists("Ledgix Sale", sale_name):
        frappe.throw(f"Ledgix Sale {sale_name or ''} was not found.")
    sale_doc = frappe.get_doc("Ledgix Sale", sale_name)
    if sale_doc.docstatus != 1:
        frappe.throw("FBR validation requires submitted sale.")

    payload, validation, readiness_error = _build_ready_payload(sale_name)
    if readiness_error:
        log_name = create_submission_log(
            "Ledgix Sale", sale_name, "Sale Invoice", "Failed", request_json=payload, error_message=readiness_error
        )
        sale_status = mark_sale_fbr_status(sale_name, "Failed", error_message=readiness_error, log_name=log_name)
        return {
            "network_call": False,
            "status": "Failed",
            "log_name": log_name,
            "sale_status": sale_status,
            "validation": validation,
            "response": None,
            "fbr_invoice_number": "",
            "error_code": "",
            "error_message": readiness_error,
        }

    client_result = fbr_client.validate_invoice(payload, mode=mode)
    if not client_result.get("network_call"):
        return _not_ready(sale_name, validation=validation, errors=[client_result.get("error") or "FBR validation was not sent."])

    parsed = parse_fbr_response(client_result)
    if not client_result.get("success"):
        parsed["valid"] = False
        parsed["error_code"] = parsed.get("error_code") or str(client_result.get("http_status") or "")
        parsed["error_message"] = parsed.get("error_message") or client_result.get("error") or "FBR validation failed."

    status = "Validated" if parsed.get("valid") else "Failed"
    log_name = create_submission_log(
        "Ledgix Sale",
        sale_name,
        "Sale Invoice",
        status,
        request_json=payload,
        response_json=client_result,
        error_code="" if parsed.get("valid") else parsed.get("error_code"),
        error_message="" if parsed.get("valid") else parsed.get("error_message"),
    )
    sale_status = mark_sale_fbr_status(
        sale_name,
        status,
        error_code="" if parsed.get("valid") else parsed.get("error_code"),
        error_message="" if parsed.get("valid") else parsed.get("error_message"),
        log_name=log_name,
    )
    return {
        "network_call": True,
        "status": status,
        "log_name": log_name,
        "sale_status": sale_status,
        "validation": validation,
        "response": client_result,
        "fbr_invoice_number": "",
        "error_code": "" if parsed.get("valid") else parsed.get("error_code"),
        "error_message": "" if parsed.get("valid") else parsed.get("error_message"),
    }


@frappe.whitelist()
def dry_run_sale_fbr_payload(sale_name):
    _require_fbr_view_permission("preview")
    result = _build_sale_invoice_payload_internal(sale_name)
    return {"dry_run": True, "network_call": False, "validation": result.get("validation"), "payload": result.get("payload")}


@frappe.whitelist()
def validate_sale_with_fbr(sale_name):
    _require_fbr_validate_permission("validate")
    settings = get_fbr_settings_internal()
    mode = settings.get("mode")
    if mode not in {"Sandbox", "Production"}:
        mode = "Sandbox"
    return _run_validate_sale(sale_name, mode)


@frappe.whitelist()
def validate_sale_with_fbr_production(sale_name):
    _require_fbr_validate_permission("validate")
    return _run_validate_sale(sale_name, "Production")


class _SubmissionLock:
    def __init__(self, sale_name):
        self.sale_name = sale_name
        self.lock_key = f"ledgix_fbr_{sale_name}"[:60]
        self._cache_lock = None
        self._db_locked = False

    def __enter__(self):
        try:
            self._cache_lock = frappe.cache().lock(f"ledgix:fbr-submit:{self.sale_name}", timeout=120)
            self._cache_lock.__enter__()
            return self
        except Exception:
            result = frappe.db.sql("SELECT GET_LOCK(%s, 120)", (self.lock_key,))
            acquired = bool(result and result[0][0] == 1)
            if not acquired:
                frappe.throw("FBR submission is already in progress for this sale. Please wait and try again.")
            self._db_locked = True
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cache_lock is not None:
            return self._cache_lock.__exit__(exc_type, exc_val, exc_tb)
        if self._db_locked:
            frappe.db.sql("SELECT RELEASE_LOCK(%s)", (self.lock_key,))
        return False


def _submission_lock(sale_name):
    return _SubmissionLock(sale_name)


@frappe.whitelist()
def submit_sale_to_fbr(sale_name):
    _require_fbr_submit_permission("submit")
    return _submit_sale_to_fbr_internal(sale_name, force=False)


def _submit_sale_to_fbr_internal(sale_name, force=False):
    if not sale_name:
        frappe.throw("sale_name is required.")
    if not frappe.db.exists("Ledgix Sale", sale_name):
        frappe.throw(f"Ledgix Sale {sale_name or ''} was not found.")

    sale_doc = frappe.get_doc("Ledgix Sale", sale_name)
    if sale_doc.docstatus != 1:
        frappe.throw("FBR submission requires submitted sale.")

    current_status = _get_sale_fbr_status(sale_name)
    if current_status.get("fbr_status") == RECONCILIATION_REQUIRED:
        return _reconciliation_result(current_status, "sale_status")
    if current_status.get("fbr_invoice_number"):
        return {
            "network_call": False,
            "status": "Already Submitted",
            "log_name": current_status.get("fbr_submission_log") or "",
            "sale_status": current_status,
            "validation": {"valid": True, "errors": [], "warnings": []},
            "response": None,
            "fbr_invoice_number": current_status.get("fbr_invoice_number"),
            "error_code": "",
            "error_message": "",
        }

    settings = get_fbr_settings_internal()
    if not settings.get("enabled"):
        return _not_ready(sale_name, errors=["FBR Settings must be enabled for submission."])
    mode = settings.get("mode")
    if mode not in {"Sandbox", "Production"}:
        return _not_ready(sale_name, errors=["FBR mode must be Sandbox or Production for submission."])
    if mode == "Production" and not settings.get("production_token_configured"):
        return _not_ready(sale_name, errors=["Production token is not configured."])
    if mode == "Production" and not settings.get("production_post_armed"):
        return _not_ready(sale_name, errors=["Production posting is not armed."])
    if mode == "Sandbox" and not settings.get("sandbox_token_configured"):
        return _not_ready(sale_name, errors=["Sandbox token is not configured."])

    with _submission_lock(sale_name):
        current_status = _get_sale_fbr_status(sale_name)
        if current_status.get("fbr_status") == RECONCILIATION_REQUIRED:
            return _reconciliation_result(current_status, "sale_status")
        if current_status.get("fbr_invoice_number"):
            return {
                "network_call": False,
                "status": "Already Submitted",
                "log_name": current_status.get("fbr_submission_log") or "",
                "sale_status": current_status,
                "validation": {"valid": True, "errors": [], "warnings": []},
                "response": None,
                "fbr_invoice_number": current_status.get("fbr_invoice_number"),
                "error_code": "",
                "error_message": "",
            }

        payload, validation, readiness_error = _build_ready_payload(sale_name)
        if readiness_error:
            log_name = create_submission_log(
                "Ledgix Sale", sale_name, "Sale Invoice", "Failed", request_json=payload, error_message=readiness_error
            )
            sale_status = mark_sale_fbr_status(sale_name, "Failed", error_message=readiness_error, log_name=log_name)
            return {
                "network_call": False,
                "status": "Failed",
                "log_name": log_name,
                "sale_status": sale_status,
                "validation": validation,
                "response": None,
                "fbr_invoice_number": "",
                "error_code": "",
                "error_message": readiness_error,
            }

        client_result = fbr_client.post_invoice(payload, mode=mode)
        if not client_result.get("network_call"):
            return _not_ready(sale_name, validation=validation, errors=[client_result.get("error") or "FBR post was not sent."])

        parsed = parse_fbr_response(client_result, require_invoice_number=(mode == "Production"))
        if not client_result.get("success"):
            parsed["valid"] = False
            parsed["error_code"] = parsed.get("error_code") or str(client_result.get("http_status") or "")
            parsed["error_message"] = parsed.get("error_message") or client_result.get("error") or "FBR post failed."

        status, invoice_number = _resolve_submission_status(mode, parsed)
        qr_code = parsed.get("qr_code") or ""
        attempt_count = 1

        if _is_ambiguous_production_post(mode, client_result):
            status = RECONCILIATION_REQUIRED
            invoice_number = ""
            parsed["error_message"] = _safe_message(client_result.get("error") or RECONCILIATION_MESSAGE)

        log_name = create_submission_log(
            "Ledgix Sale",
            sale_name,
            "Sale Invoice",
            status,
            request_json=payload,
            response_json=client_result,
            error_code="" if status in {"Submitted", "Validated"} else parsed.get("error_code"),
            error_message="" if status in {"Submitted", "Validated"} else parsed.get("error_message"),
            fbr_invoice_number=invoice_number,
            attempt_count=attempt_count,
            next_retry_time=None,
        )
        sale_status = mark_sale_fbr_status(
            sale_name,
            status,
            fbr_invoice_number=invoice_number if invoice_number else None,
            fbr_qr_code=qr_code if qr_code else None,
            error_code="" if status in {"Submitted", "Validated"} else parsed.get("error_code"),
            error_message="" if status in {"Submitted", "Validated"} else parsed.get("error_message"),
            log_name=log_name,
        )

        return {
            "network_call": True,
            "status": status,
            "log_name": log_name,
            "sale_status": sale_status,
            "validation": validation,
            "response": client_result,
            "fbr_invoice_number": invoice_number,
            "fbr_qr_code": qr_code,
            "error_code": "" if status in {"Submitted", "Validated"} else parsed.get("error_code"),
            "error_message": "" if status in {"Submitted", "Validated"} else parsed.get("error_message"),
        }


def _after_commit_submit(sale_name):
    def _run():
        try:
            _submit_sale_to_fbr_internal(sale_name, force=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Ledgix FBR after-commit submit failed for {sale_name}")

    frappe.db.after_commit.add(_run)


def queue_sale_for_fbr(sale_name, reason=None):
    current_status = _get_sale_fbr_status(sale_name)
    if current_status.get("fbr_status") == RECONCILIATION_REQUIRED:
        return {
            "queued": False,
            "status": RECONCILIATION_REQUIRED,
            "reason": RECONCILIATION_MESSAGE,
            "sale_status": current_status,
        }
    if current_status.get("fbr_invoice_number"):
        return {"queued": False, "status": "Submitted", "reason": "Sale already has an FBR invoice number", "sale_status": current_status}

    control_state = get_fbr_control_state_internal()
    settings = get_fbr_settings_internal()
    mode = control_state.get("mode")
    submit_trigger = control_state.get("submit_trigger")

    if mode == "Disabled" or (not settings.get("enabled") and mode not in {"Paused", "Manual Only"}):
        status = mark_sale_fbr_status(sale_name, "Not Required")
        return {"queued": False, "status": "Not Required", "reason": "FBR disabled", "sale_status": status}

    payload, validation, readiness_error = _build_ready_payload(sale_name)
    if mode == "Paused":
        log_name = create_submission_log(
            "Ledgix Sale", sale_name, "Sale Invoice", "Paused", request_json=payload,
            error_message=reason or control_state.get("reason") or "FBR paused",
        )
        status = mark_sale_fbr_status(sale_name, "Paused", error_message=reason, log_name=log_name)
        return {"queued": False, "status": "Paused", "reason": "FBR paused", "log_name": log_name, "validation": validation, "sale_status": status}

    if readiness_error:
        log_name = create_submission_log(
            "Ledgix Sale", sale_name, "Sale Invoice", "Failed", request_json=payload, error_message=readiness_error
        )
        status = mark_sale_fbr_status(sale_name, "Failed", error_message=readiness_error, log_name=log_name)
        return {"queued": False, "status": "Failed", "reason": readiness_error, "log_name": log_name, "validation": validation, "sale_status": status}

    log_name = create_submission_log(
        "Ledgix Sale", sale_name, "Sale Invoice", "Pending", request_json=payload, error_message=reason
    )
    status = mark_sale_fbr_status(sale_name, "Pending", error_message=reason, log_name=log_name)

    if mode == "Manual Only" or submit_trigger == "Manual":
        return {"queued": True, "status": "Pending", "reason": "Manual FBR submission required", "log_name": log_name, "validation": validation, "sale_status": status}
    if submit_trigger == "Validate Only":
        result = _run_validate_sale(sale_name, mode if mode in {"Sandbox", "Production"} else "Sandbox")
        result.update({"queued": True, "reason": "Validate Only flow completed"})
        return result
    if submit_trigger == "On Submit":
        if mode == "Production":
            _after_commit_submit(sale_name)
            return {"queued": True, "status": "Pending", "reason": "Production FBR post queued after commit", "log_name": log_name, "validation": validation, "sale_status": status}
        if mode == "Sandbox":
            if settings.get("sandbox_post_on_submit"):
                _after_commit_submit(sale_name)
                return {"queued": True, "status": "Pending", "reason": "Sandbox FBR post queued after commit", "log_name": log_name, "validation": validation, "sale_status": status}
            result = _run_validate_sale(sale_name, "Sandbox")
            result.update({"queued": True, "reason": "Sandbox validation completed (enable Sandbox Post On Submit to post)"})
            return result

    return {"queued": True, "status": "Pending", "reason": "FBR submission queued", "log_name": log_name, "validation": validation, "sale_status": status}


@frappe.whitelist()
def release_sale_after_fbr_reconciliation(sale_name, confirmation):
    _require_fbr_submit_permission("release a reconciled sale")
    if str(confirmation or "").strip() != RECONCILIATION_CONFIRMATION:
        frappe.throw(f"Confirmation must be exactly: {RECONCILIATION_CONFIRMATION}")
    current = _get_sale_fbr_status(sale_name)
    if current.get("fbr_status") != RECONCILIATION_REQUIRED:
        frappe.throw("Sale is not awaiting FBR reconciliation.")

    message = "External FBR/PRAL reconciliation confirmed this invoice was not received. Manual retry is now permitted."
    log_name = create_submission_log("Ledgix Sale", sale_name, "Sale Invoice", "Pending", error_message=message)
    sale_status = mark_sale_fbr_status(sale_name, "Pending", error_code="", error_message=message, log_name=log_name)
    return {"released": True, "network_call": False, "status": "Pending", "sale_status": sale_status, "log_name": log_name}


def _get_return_fbr_status(return_name):
    if not return_name or not frappe.db.exists("Ledgix Sales Return", return_name):
        frappe.throw(f"Ledgix Sales Return {return_name or ''} was not found.")
    fields = [
        "fbr_status",
        "fbr_invoice_number",
        "fbr_qr_code",
        "fbr_submitted_at",
        "fbr_error_code",
        "fbr_error_message",
        "fbr_submission_log",
    ]
    return dict(frappe.db.get_value("Ledgix Sales Return", return_name, fields, as_dict=True) or {})


def mark_return_fbr_status(
    return_name,
    status,
    fbr_invoice_number=None,
    fbr_qr_code=None,
    error_code=None,
    error_message=None,
    log_name=None,
):
    if not return_name or not frappe.db.exists("Ledgix Sales Return", return_name):
        frappe.throw(f"Ledgix Sales Return {return_name or ''} was not found.")

    values = {"fbr_status": normalize_fbr_status(status)}
    if fbr_invoice_number is not None:
        values["fbr_invoice_number"] = fbr_invoice_number
    if fbr_qr_code is not None:
        values["fbr_qr_code"] = fbr_qr_code
    if error_code is not None:
        values["fbr_error_code"] = error_code
    if error_message is not None:
        values["fbr_error_message"] = _safe_message(error_message)
    if log_name is not None:
        values["fbr_submission_log"] = log_name
    if status == "Submitted":
        values["fbr_submitted_at"] = now_datetime()

    frappe.db.set_value("Ledgix Sales Return", return_name, values, update_modified=False)
    return _get_return_fbr_status(return_name)


def _build_ready_return_payload(return_name):
    from ledgix_saas.api.fbr_payload import _build_return_invoice_payload_internal

    payload_result = _build_return_invoice_payload_internal(return_name) or {}
    payload = payload_result.get("payload")
    validation = payload_result.get("validation") or {}
    if not validation.get("valid"):
        return payload, validation, "Return payload readiness failed."
    if not payload:
        validation.setdefault("errors", []).append("FBR return payload could not be built.")
        validation["valid"] = False
        return payload, validation, "FBR return payload could not be built."
    return payload, validation, ""


def _submit_return_to_fbr_internal(return_name):
    from ledgix_saas.api.fbr_payload import get_return_for_fbr

    if not return_name or not frappe.db.exists("Ledgix Sales Return", return_name):
        frappe.throw(f"Ledgix Sales Return {return_name or ''} was not found.")
    return_doc = get_return_for_fbr(return_name)
    if return_doc.docstatus != 1:
        frappe.throw("FBR submission requires submitted sales return.")

    current_status = _get_return_fbr_status(return_name)
    if current_status.get("fbr_status") == RECONCILIATION_REQUIRED:
        return _reconciliation_result(current_status, "return_status")
    if current_status.get("fbr_invoice_number"):
        return {
            "network_call": False,
            "status": "Already Submitted",
            "log_name": current_status.get("fbr_submission_log") or "",
            "return_status": current_status,
            "validation": {"valid": True, "errors": [], "warnings": []},
            "response": None,
            "fbr_invoice_number": current_status.get("fbr_invoice_number"),
            "fbr_qr_code": current_status.get("fbr_qr_code") or "",
            "error_code": "",
            "error_message": "",
        }

    settings = get_fbr_settings_internal()
    mode = settings.get("mode")
    if not settings.get("enabled") or mode not in {"Sandbox", "Production"}:
        return {
            "network_call": False,
            "status": "Not Ready",
            "return_status": current_status,
            "validation": {"valid": False, "errors": ["FBR is not enabled for return submission."], "warnings": []},
            "error_message": "FBR is not enabled for return submission.",
        }
    if mode == "Production" and not settings.get("production_token_configured"):
        return {"network_call": False, "status": "Not Ready", "return_status": current_status, "validation": {"valid": False, "errors": ["Production token is not configured."], "warnings": []}, "error_message": "Production token is not configured."}
    if mode == "Production" and not settings.get("production_post_armed"):
        return {"network_call": False, "status": "Not Ready", "return_status": current_status, "validation": {"valid": False, "errors": ["Production posting is not armed."], "warnings": []}, "error_message": "Production posting is not armed."}
    if mode == "Sandbox" and not settings.get("sandbox_token_configured"):
        return {"network_call": False, "status": "Not Ready", "return_status": current_status, "validation": {"valid": False, "errors": ["Sandbox token is not configured."], "warnings": []}, "error_message": "Sandbox token is not configured."}

    payload, validation, readiness_error = _build_ready_return_payload(return_name)
    if readiness_error:
        log_name = create_submission_log(
            "Ledgix Sales Return", return_name, "Credit Note", "Failed", request_json=payload, error_message=readiness_error
        )
        return_status = mark_return_fbr_status(return_name, "Failed", error_message=readiness_error, log_name=log_name)
        return {"network_call": False, "status": "Failed", "log_name": log_name, "return_status": return_status, "validation": validation, "error_message": readiness_error}

    client_result = fbr_client.post_invoice(payload, mode=mode)
    if not client_result.get("network_call"):
        return {"network_call": False, "status": "Not Ready", "return_status": current_status, "validation": validation, "response": client_result, "error_message": client_result.get("error") or "FBR return post was not sent."}

    parsed = parse_fbr_response(client_result, require_invoice_number=(mode == "Production"))
    if not client_result.get("success"):
        parsed["valid"] = False
        parsed["error_code"] = parsed.get("error_code") or str(client_result.get("http_status") or "")
        parsed["error_message"] = parsed.get("error_message") or client_result.get("error") or "FBR return post failed."

    status, invoice_number = _resolve_submission_status(mode, parsed)
    qr_code = parsed.get("qr_code") or ""
    if _is_ambiguous_production_post(mode, client_result):
        status = RECONCILIATION_REQUIRED
        invoice_number = ""
        parsed["error_message"] = _safe_message(client_result.get("error") or RECONCILIATION_MESSAGE)

    log_name = create_submission_log(
        "Ledgix Sales Return",
        return_name,
        "Credit Note",
        status,
        request_json=payload,
        response_json=client_result,
        error_code="" if status in {"Submitted", "Validated"} else parsed.get("error_code"),
        error_message="" if status in {"Submitted", "Validated"} else parsed.get("error_message"),
        fbr_invoice_number=invoice_number,
        attempt_count=1,
    )
    return_status = mark_return_fbr_status(
        return_name,
        status,
        fbr_invoice_number=invoice_number if invoice_number else None,
        fbr_qr_code=qr_code if qr_code else None,
        error_code="" if status in {"Submitted", "Validated"} else parsed.get("error_code"),
        error_message="" if status in {"Submitted", "Validated"} else parsed.get("error_message"),
        log_name=log_name,
    )
    return {
        "network_call": True,
        "status": status,
        "log_name": log_name,
        "return_status": return_status,
        "validation": validation,
        "response": client_result,
        "fbr_invoice_number": invoice_number,
        "fbr_qr_code": qr_code,
        "error_code": "" if status in {"Submitted", "Validated"} else parsed.get("error_code"),
        "error_message": "" if status in {"Submitted", "Validated"} else parsed.get("error_message"),
    }


def queue_return_for_fbr(return_name, reason=None):
    current_status = _get_return_fbr_status(return_name)
    if current_status.get("fbr_status") == RECONCILIATION_REQUIRED:
        return {"queued": False, "status": RECONCILIATION_REQUIRED, "reason": RECONCILIATION_MESSAGE, "return_status": current_status}
    if current_status.get("fbr_invoice_number"):
        return {"queued": False, "status": "Submitted", "reason": "Return already has an FBR credit note number", "return_status": current_status}

    settings = get_fbr_settings_internal()
    mode = settings.get("mode")
    submit_trigger = settings.get("submit_trigger")
    if mode == "Disabled" or (not settings.get("enabled") and mode not in {"Paused", "Manual Only"}):
        status = mark_return_fbr_status(return_name, "Not Required")
        return {"queued": False, "status": "Not Required", "reason": "FBR disabled", "return_status": status}

    payload, validation, readiness_error = _build_ready_return_payload(return_name)
    if readiness_error:
        log_name = create_submission_log(
            "Ledgix Sales Return", return_name, "Credit Note", "Failed", request_json=payload, error_message=readiness_error
        )
        status = mark_return_fbr_status(return_name, "Failed", error_message=readiness_error, log_name=log_name)
        return {"queued": False, "status": "Failed", "reason": readiness_error, "return_status": status, "validation": validation}

    log_name = create_submission_log(
        "Ledgix Sales Return", return_name, "Credit Note", "Pending", request_json=payload, error_message=reason
    )
    status = mark_return_fbr_status(return_name, "Pending", error_message=reason, log_name=log_name)
    if mode == "Manual Only" or submit_trigger == "Manual":
        return {"queued": True, "status": "Pending", "reason": "Manual FBR return submission required", "return_status": status}
    if submit_trigger == "On Submit" and mode in {"Sandbox", "Production"}:
        def _run():
            try:
                _submit_return_to_fbr_internal(return_name)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Ledgix FBR return after-commit submit failed for {return_name}")

        frappe.db.after_commit.add(_run)
        return {"queued": True, "status": "Pending", "reason": "FBR return post queued after commit", "return_status": status}
    return {"queued": True, "status": "Pending", "reason": "FBR return submission queued", "return_status": status}


@frappe.whitelist()
def submit_return_to_fbr(return_name):
    _require_fbr_submit_permission("submit")
    return _submit_return_to_fbr_internal(return_name)


@frappe.whitelist()
def release_return_after_fbr_reconciliation(return_name, confirmation):
    _require_fbr_submit_permission("release a reconciled return")
    if str(confirmation or "").strip() != RECONCILIATION_CONFIRMATION:
        frappe.throw(f"Confirmation must be exactly: {RECONCILIATION_CONFIRMATION}")
    current = _get_return_fbr_status(return_name)
    if current.get("fbr_status") != RECONCILIATION_REQUIRED:
        frappe.throw("Sales return is not awaiting FBR reconciliation.")

    message = "External FBR/PRAL reconciliation confirmed this note was not received. Manual retry is now permitted."
    log_name = create_submission_log("Ledgix Sales Return", return_name, "Credit Note", "Pending", error_message=message)
    return_status = mark_return_fbr_status(return_name, "Pending", error_code="", error_message=message, log_name=log_name)
    return {"released": True, "network_call": False, "status": "Pending", "return_status": return_status, "log_name": log_name}


def process_fbr_retry_queue(limit=20):
    """Fail closed: Production retransmission requires external reconciliation first."""
    return {
        "processed": 0,
        "skipped": True,
        "reason": "Automatic FBR retry is disabled. Reconcile with FBR/PRAL before any retransmission.",
    }


def process_fbr_offline_upload_queue(limit=20):
    """Fail closed until a true offline/restoration workflow is implemented."""
    return {
        "processed": 0,
        "skipped": True,
        "reason": "Automatic offline upload is disabled until connectivity restoration can be confirmed safely.",
    }
