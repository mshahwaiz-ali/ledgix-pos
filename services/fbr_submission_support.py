from __future__ import annotations

"""Neutral FBR submission helpers shared by ERPNext-native compliance paths.

This module deliberately owns no FBR settings, payload construction, transport,
retry policy, accounting, or business-ledger logic. It contains only response
parsing/status resolution, audit-log persistence, and submission locking.
"""

import json

import frappe
from frappe.utils import cint, now_datetime

ALLOWED_STATUSES = {
    "Not Required", "Pending", "Validated", "Submitted", "Failed",
    "Reconciliation Required", "Offline Pending", "Skipped", "Paused",
}
FINAL_ATTEMPT_STATUSES = {
    "Validated", "Submitted", "Failed", "Reconciliation Required",
    "Skipped", "Paused", "Not Required",
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


def resolve_submission_status(mode, parsed):
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
            "valid": False, "invoice_number": "", "qr_code": "", "dated": "",
            "status_code": "", "error_code": "",
            "error_message": "FBR response was not JSON.", "item_statuses": [],
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


class _SubmissionLock:
    def __init__(self, reference_key):
        self.reference_key = reference_key
        self.lock_key = f"ledgix_fbr_{reference_key}"[:60]
        self._cache_lock = None
        self._db_locked = False

    def __enter__(self):
        try:
            self._cache_lock = frappe.cache().lock(
                f"ledgix:fbr-submit:{self.reference_key}", timeout=120
            )
            self._cache_lock.__enter__()
            return self
        except Exception:
            result = frappe.db.sql("SELECT GET_LOCK(%s, 120)", (self.lock_key,))
            acquired = bool(result and result[0][0] == 1)
            if not acquired:
                frappe.throw(
                    "FBR submission is already in progress for this reference. "
                    "Please wait and try again."
                )
            self._db_locked = True
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cache_lock is not None:
            return self._cache_lock.__exit__(exc_type, exc_val, exc_tb)
        if self._db_locked:
            frappe.db.sql("SELECT RELEASE_LOCK(%s)", (self.lock_key,))
        return False


def submission_lock(reference_key):
    return _SubmissionLock(reference_key)
