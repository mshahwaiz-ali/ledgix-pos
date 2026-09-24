from __future__ import annotations

"""Compatibility shell for retired Ledgix Sale / Sales Return FBR execution.

ERPNext Sales Invoice / POS Invoice plus FBR V2 are the only active execution
path. Neutral response parsing, audit logging and locking live in
services.fbr_submission_support and are re-exported here only for compatibility.
Historical legacy FBR status remains readable; mutation/submission is retired.
"""

import frappe

from ledgix_saas.services import fbr_submission_support as support


RECONCILIATION_REQUIRED = "Reconciliation Required"
RECONCILIATION_CONFIRMATION = "CONFIRMED NOT RECEIVED BY FBR"
RECONCILIATION_MESSAGE = (
    "Legacy Ledgix Sale / Sales Return FBR execution is retired. "
    "Use the authoritative ERPNext Sales Invoice or POS Invoice FBR workflow."
)
LEGACY_EXECUTION_RETIRED_MESSAGE = RECONCILIATION_MESSAGE

serialize_json = support.serialize_json
normalize_fbr_status = support.normalize_fbr_status
_safe_message = support._safe_message
_extract_fbr_qr_code = support._extract_fbr_qr_code
parse_fbr_response = support.parse_fbr_response
create_submission_log = support.create_submission_log
_resolve_submission_status = support.resolve_submission_status
_submission_lock = support.submission_lock


def _require_fbr_view_permission(action="view"):
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(
        {"System Manager", "Ledgix Admin", "Ledgix Manager"}
    ):
        frappe.throw(
            f"Only System Manager, Ledgix Admin, or Ledgix Manager can "
            f"{action} historical FBR data.",
            frappe.PermissionError,
        )


def _historical_status(doctype: str, name: str) -> dict:
    name = str(name or "").strip()
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(f"{doctype} {name or ''} was not found.")

    fields = [
        "fbr_status",
        "fbr_invoice_number",
        "fbr_qr_code",
        "fbr_generated_at",
        "fbr_submitted_at",
        "fbr_upload_due_at",
        "fbr_error_code",
        "fbr_error_message",
        "fbr_submission_log",
    ]
    meta = frappe.get_meta(doctype)
    available = [field for field in fields if meta.has_field(field)]
    values = dict(
        frappe.db.get_value(
            doctype,
            name,
            available,
            as_dict=True,
        )
        or {}
    )
    values["reference_doctype"] = doctype
    values["reference_name"] = name
    values["historical_only"] = True
    values["execution_retired"] = True
    return values


@frappe.whitelist()
def get_sale_fbr_status(sale_name):
    _require_fbr_view_permission("view")
    return _historical_status("Ledgix Sale", sale_name)


def _get_sale_fbr_status(sale_name):
    return _historical_status("Ledgix Sale", sale_name)


def _get_return_fbr_status(return_name):
    return _historical_status("Ledgix Sales Return", return_name)


def _retired_result(reference_name="", reference_doctype="") -> dict:
    return {
        "network_call": False,
        "status": "Retired",
        "log_name": "",
        "reference_doctype": str(reference_doctype or ""),
        "reference_name": str(reference_name or ""),
        "validation": {
            "valid": False,
            "errors": [LEGACY_EXECUTION_RETIRED_MESSAGE],
            "warnings": [],
        },
        "response": None,
        "fbr_invoice_number": "",
        "fbr_qr_code": "",
        "error_code": "LEGACY_FBR_RETIRED",
        "error_message": LEGACY_EXECUTION_RETIRED_MESSAGE,
        "execution_retired": True,
        "transport_authority": "ERPNext Native + FBR V2",
    }


def mark_sale_fbr_status(*args, **kwargs):
    frappe.throw(LEGACY_EXECUTION_RETIRED_MESSAGE)


def mark_return_fbr_status(*args, **kwargs):
    frappe.throw(LEGACY_EXECUTION_RETIRED_MESSAGE)


def _build_ready_payload(sale_name):
    return None, {
        "valid": False,
        "errors": [LEGACY_EXECUTION_RETIRED_MESSAGE],
        "warnings": [],
    }, LEGACY_EXECUTION_RETIRED_MESSAGE


def _build_ready_return_payload(return_name):
    return None, {
        "valid": False,
        "errors": [LEGACY_EXECUTION_RETIRED_MESSAGE],
        "warnings": [],
    }, LEGACY_EXECUTION_RETIRED_MESSAGE


@frappe.whitelist()
def dry_run_sale_fbr_payload(sale_name):
    return _retired_result(sale_name, "Ledgix Sale")


@frappe.whitelist()
def validate_sale_with_fbr(sale_name):
    return _retired_result(sale_name, "Ledgix Sale")


@frappe.whitelist()
def validate_sale_with_fbr_production(sale_name):
    return _retired_result(sale_name, "Ledgix Sale")


@frappe.whitelist()
def submit_sale_to_fbr(sale_name):
    return _retired_result(sale_name, "Ledgix Sale")


def _submit_sale_to_fbr_internal(sale_name, force=False):
    return _retired_result(sale_name, "Ledgix Sale")


def _after_commit_submit(sale_name):
    return _retired_result(sale_name, "Ledgix Sale")


def queue_sale_for_fbr(sale_name, reason=None):
    return _retired_result(sale_name, "Ledgix Sale")


@frappe.whitelist()
def release_sale_after_fbr_reconciliation(sale_name, confirmation):
    return _retired_result(sale_name, "Ledgix Sale")


def _submit_return_to_fbr_internal(return_name):
    return _retired_result(return_name, "Ledgix Sales Return")


def queue_return_for_fbr(return_name, reason=None):
    return _retired_result(return_name, "Ledgix Sales Return")


@frappe.whitelist()
def submit_return_to_fbr(return_name):
    return _retired_result(return_name, "Ledgix Sales Return")


@frappe.whitelist()
def release_return_after_fbr_reconciliation(return_name, confirmation):
    return _retired_result(return_name, "Ledgix Sales Return")


def process_fbr_retry_queue(limit=20):
    return {
        "processed": 0,
        "retired": True,
        "network_call": False,
        "message": LEGACY_EXECUTION_RETIRED_MESSAGE,
    }


def process_fbr_offline_upload_queue(limit=20):
    return {
        "processed": 0,
        "retired": True,
        "network_call": False,
        "message": LEGACY_EXECUTION_RETIRED_MESSAGE,
    }
