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


def sanitize(value, secrets=()):
    import re
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if any(x in str(k).lower() for x in
                ("token", "authorization", "password", "secret")) else sanitize(v, secrets))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return re.sub(r"(?i)bearer\s+[^\s\"',}]+", "Bearer [REDACTED]", value)
    return value


def _safe_message(value):
    return sanitize(str(value or ""))


def parse_fbr_response(response, require_invoice_number=True):
    from fbr_v1.protocol.response import parse_fiscal_response
    result = parse_fiscal_response(response)
    return {"valid": result.success, "invoice_number": result.invoice_number,
            "status_code": result.code, "error_message": _safe_message(result.response)}


def resolve_submission_status(mode, parsed):
    if parsed.get("valid") and parsed.get("invoice_number"):
        return "Submitted", parsed["invoice_number"]
    return "Failed", ""


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
    offline_issued_at=None,
    offline_upload_due_at=None,
    offline_reason=None,
    **evidence,
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
    if log.meta.has_field("offline_issued_at"):
        log.offline_issued_at = offline_issued_at
    if log.meta.has_field("offline_upload_due_at"):
        log.offline_upload_due_at = offline_upload_due_at
    if log.meta.has_field("offline_reason"):
        log.offline_reason = _safe_message(offline_reason)
    log.update(evidence)
    log.protocol = "Federal POS/IMS V1"
    log.request_json = serialize_json(sanitize(request_json))
    log.response_json = serialize_json(sanitize(response_json))
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
        # DB advisory lock is authoritative even when Redis is unavailable to only
        # one worker. Every worker takes it, avoiding split Redis/DB lock domains.
        import hashlib
        self.lock_key = "fbr_v1_" + hashlib.sha256(self.reference_key.encode()).hexdigest()[:50]
        result = frappe.db.sql("SELECT GET_LOCK(%s, 30)", (self.lock_key,))
        if not result or result[0][0] != 1:
            frappe.throw("FBR submission is already in progress.")
        self._db_locked = True
        try:
            self._cache_lock = frappe.cache().lock(
                "ledgix:fbr-v1:" + self.lock_key, timeout=120, blocking_timeout=1)
            self._cache_lock.__enter__()
        except Exception:
            self._cache_lock = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._cache_lock is not None:
                self._cache_lock.__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self._db_locked:
                frappe.db.sql("SELECT RELEASE_LOCK(%s)", (self.lock_key,))
        return False


def submission_lock(reference_key):
    return _SubmissionLock(reference_key)
