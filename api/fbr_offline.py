from __future__ import annotations

# Known-offline lifecycle for ERPNext-native FBR invoices.
#
# Known Offline is separate from an ambiguous Production POST. This module
# never schedules automatic retry traffic, guesses a legal upload deadline,
# or changes ERPNext accounting. The upload window is client/provider-specific.

import json

import frappe
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from ledgix_saas.api import fbr_native
from ledgix_saas.services import fbr_submission_support, fbr_v2_readiness


PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
OFFLINE_PENDING = fbr_native.OFFLINE_PENDING
DECLARE_OFFLINE_CONFIRMATION = "DECLARE KNOWN OFFLINE"
UPLOAD_OFFLINE_CONFIRMATION = "UPLOAD OFFLINE INVOICE"

VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
ACTION_ROLES = {"System Manager", "Ledgix Admin"}


def _text(value) -> str:
    return str(value or "").strip()


def _require_roles(allowed: set[str], action: str) -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection(allowed):
        frappe.throw(
            f"You do not have permission to {action}.",
            frappe.PermissionError,
        )


def _profile_runtime(company: str) -> dict:
    bundle = fbr_v2_readiness.get_company_profile_state(company)
    state = dict(bundle.get("profile") or {})
    certification = dict(bundle.get("sandbox_certification") or {})

    name = _text(state.get("name"))
    profile = (
        frappe.get_doc(PROFILE_DOCTYPE, name)
        if name and frappe.db.exists(PROFILE_DOCTYPE, name)
        else None
    )

    return {
        "state": state,
        "certification": certification,
        "profile": profile,
    }


def _offline_policy(company: str) -> dict:
    runtime = _profile_runtime(company)
    state = runtime["state"]
    certification = runtime["certification"]
    profile = runtime["profile"]

    blockers = []
    if not fbr_native.V2_NETWORK_CUTOVER_ACTIVE:
        blockers.append("Global FBR V2 Production network cutover is not active.")
    if not state.get("exists"):
        blockers.append("Company has no FBR Integration Profile.")
    if not state.get("enabled"):
        blockers.append("FBR Integration Profile is not enabled.")
    if _text(state.get("mode")) != "Production":
        blockers.append("Known Offline workflow is available only in Production mode.")
    if not state.get("production_token_configured"):
        blockers.append("Production token is not configured.")
    if not state.get("production_post_armed"):
        blockers.append("Production posting is not armed.")
    if not certification.get("complete"):
        blockers.append("Completed Sandbox certification evidence is required.")

    offline_policy = _text(profile.get("offline_policy")) if profile else "Disabled"
    upload_window_hours = cint(
        profile.get("offline_upload_window_hours")
        if profile
        else 0
    )
    if offline_policy != "Operator Confirmed":
        blockers.append("Known Offline Policy is not enabled.")
    if upload_window_hours <= 0:
        blockers.append(
            "Offline Upload Window (Hours) is not configured from the current "
            "client/provider rule."
        )

    return {
        "ready": not blockers,
        "blockers": blockers,
        "profile_name": profile.name if profile else "",
        "offline_policy": offline_policy,
        "upload_window_hours": upload_window_hours,
        "submit_trigger": _text(state.get("submit_trigger")) or "Manual",
        "production_post_armed": bool(state.get("production_post_armed")),
        "production_token_configured": bool(
            state.get("production_token_configured")
        ),
        "sandbox_certification_complete": bool(
            certification.get("complete")
        ),
        "contains_secrets": False,
    }


def _response_json(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _prior_production_post_attempts(
    reference_doctype: str,
    reference_name: str,
) -> list[str]:
    rows = frappe.get_all(
        "Ledgix FBR Submission Log",
        filters={
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
        },
        fields=["name", "fbr_status", "response_json"],
        order_by="creation asc",
        limit_page_length=0,
    )
    attempts = []
    for row in rows:
        response = _response_json(row.get("response_json"))
        if (
            _text(response.get("fbr_mode")) == "Production"
            and _text(response.get("fbr_operation")).lower() == "post"
            and bool(response.get("network_call"))
        ):
            attempts.append(row.get("name") or "")
        elif row.get("fbr_status") in {
            "Submitted",
            fbr_native.RECONCILIATION_REQUIRED,
        }:
            attempts.append(row.get("name") or "")
    return [name for name in attempts if name]


def _source(reference_doctype: str, reference_name: str):
    doc = fbr_native._reference(reference_doctype, reference_name)
    if not fbr_native.is_native_fbr_source(doc):
        frappe.throw(
            "Known Offline workflow requires a submitted ERPNext-native FBR "
            "source invoice."
        )
    if cint(doc.get("is_return")):
        frappe.throw(
            "Known Offline return/note issuance remains blocked until the "
            "Debit/Credit Note contract is proven in Sandbox."
        )
    return doc


def declare_known_offline_internal(
    reference_doctype: str,
    reference_name: str,
    reason: str,
) -> dict:
    doc = _source(reference_doctype, reference_name)
    reason = _text(reason)
    if not reason:
        frappe.throw("Known Offline reason is required.")

    current = fbr_native._get_status(doc.doctype, doc.name)
    if current.get("fbr_status") == OFFLINE_PENDING:
        return {
            "declared": False,
            "idempotent": True,
            "status": OFFLINE_PENDING,
            "reference_status": current,
            "network_call": False,
            "contains_secrets": False,
        }
    if current.get("fbr_invoice_number"):
        frappe.throw("Invoice already has an official FBR invoice number.")
    if current.get("fbr_status") == fbr_native.RECONCILIATION_REQUIRED:
        frappe.throw(
            "Ambiguous Production POST is a reconciliation case, not Known Offline."
        )

    prior_posts = _prior_production_post_attempts(doc.doctype, doc.name)
    if prior_posts:
        frappe.throw(
            "Known Offline cannot be declared after a Production POST attempt. "
            "Use reconciliation instead."
        )

    policy = _offline_policy(doc.company)
    if not policy["ready"]:
        frappe.throw(
            "Known Offline policy is not ready: "
            + "; ".join(policy["blockers"])
        )

    payload, validation, readiness_error = fbr_native._ready_payload(doc)
    if readiness_error:
        frappe.throw(
            "Invoice is not payload-ready for Known Offline issuance: "
            + readiness_error
        )

    issued_at = now_datetime()
    due_at = add_to_date(
        issued_at,
        hours=policy["upload_window_hours"],
        as_datetime=True,
    )
    evidence = {
        "offline_event": "known_offline_issued",
        "network_call": False,
        "fbr_mode": "Production",
        "fbr_operation": "offline_issue",
        "reason": reason,
        "upload_window_hours": policy["upload_window_hours"],
        "production_post_attempted": False,
        "contains_secrets": False,
    }

    log_name = fbr_submission_support.create_submission_log(
        doc.doctype,
        doc.name,
        "Sale Invoice",
        OFFLINE_PENDING,
        request_json=payload,
        response_json=evidence,
        error_message=reason,
        attempt_count=0,
        offline_issued_at=issued_at,
        offline_upload_due_at=due_at,
        offline_reason=reason,
    )
    status = fbr_native.mark_native_fbr_status(
        doc.doctype,
        doc.name,
        OFFLINE_PENDING,
        fbr_upload_due_at=due_at,
        offline_issued_at=issued_at,
        offline_reason=reason,
        error_code="",
        error_message=reason,
        log_name=log_name,
        submit_trigger=policy["submit_trigger"],
    )

    return {
        "declared": True,
        "idempotent": False,
        "status": OFFLINE_PENDING,
        "log_name": log_name,
        "issued_at": issued_at,
        "upload_due_at": due_at,
        "reference_status": status,
        "policy": policy,
        "validation": validation,
        "network_call": False,
        "production_post_attempted": False,
        "contains_secrets": False,
    }


@frappe.whitelist()
def declare_known_offline(
    reference_doctype,
    reference_name,
    reason,
    confirmation,
):
    _require_roles(ACTION_ROLES, "declare Known Offline issuance")
    if _text(confirmation) != DECLARE_OFFLINE_CONFIRMATION:
        frappe.throw(
            "Confirmation must be exactly: "
            + DECLARE_OFFLINE_CONFIRMATION
        )
    return declare_known_offline_internal(
        reference_doctype,
        reference_name,
        reason,
    )


def list_offline_queue_internal(company: str | None = None) -> dict:
    now = now_datetime()
    rows = []
    for doctype in fbr_native.SUPPORTED_DOCTYPES:
        filters = {
            "docstatus": 1,
            "custom_ledgix_fbr_status": OFFLINE_PENDING,
        }
        if _text(company):
            filters["company"] = _text(company)

        for row in frappe.get_all(
            doctype,
            filters=filters,
            fields=[
                "name",
                "company",
                "posting_date",
                "customer",
                "grand_total",
                "custom_ledgix_fbr_offline_issued_at",
                "custom_ledgix_fbr_upload_due_at",
                "custom_ledgix_fbr_offline_reason",
                "custom_ledgix_fbr_submission_log",
            ],
            order_by="custom_ledgix_fbr_upload_due_at asc, posting_date asc",
            limit_page_length=0,
        ):
            due_at = row.get("custom_ledgix_fbr_upload_due_at")
            overdue = bool(
                due_at and get_datetime(due_at) < get_datetime(now)
            )
            rows.append(
                {
                    "doctype": doctype,
                    "name": row.get("name") or "",
                    "company": row.get("company") or "",
                    "posting_date": str(row.get("posting_date") or ""),
                    "customer": row.get("customer") or "",
                    "grand_total": row.get("grand_total") or 0,
                    "offline_issued_at": str(
                        row.get("custom_ledgix_fbr_offline_issued_at") or ""
                    ),
                    "upload_due_at": str(due_at or ""),
                    "offline_reason": row.get(
                        "custom_ledgix_fbr_offline_reason"
                    )
                    or "",
                    "submission_log": row.get(
                        "custom_ledgix_fbr_submission_log"
                    )
                    or "",
                    "overdue": overdue,
                }
            )

    return {
        "company": _text(company),
        "status": OFFLINE_PENDING,
        "count": len(rows),
        "overdue_count": sum(1 for row in rows if row["overdue"]),
        "rows": rows,
        "network_call": False,
        "database_write": False,
        "contains_secrets": False,
    }


@frappe.whitelist()
def get_offline_queue(company=None):
    _require_roles(VIEW_ROLES, "view the FBR Offline Pending queue")
    return list_offline_queue_internal(company)


def upload_offline_native_internal(
    reference_doctype: str,
    reference_name: str,
) -> dict:
    doc = _source(reference_doctype, reference_name)
    current = fbr_native._get_status(doc.doctype, doc.name)
    if current.get("fbr_status") != OFFLINE_PENDING:
        frappe.throw("Controlled offline upload requires Offline Pending status.")
    if current.get("fbr_invoice_number"):
        frappe.throw("Offline Pending invoice already has an FBR invoice number.")
    if current.get("fbr_reconciliation_required"):
        frappe.throw(
            "Reconciliation Required cannot use the Known Offline upload path."
        )

    prior_posts = _prior_production_post_attempts(doc.doctype, doc.name)
    if prior_posts:
        frappe.throw(
            "A Production POST attempt already exists. Controlled offline upload "
            "is blocked; reconcile externally instead."
        )

    policy = _offline_policy(doc.company)
    if not policy["ready"]:
        frappe.throw(
            "Controlled offline upload is not ready: "
            + "; ".join(policy["blockers"])
        )

    result = fbr_native.submit_native_to_fbr_internal(
        doc.doctype,
        doc.name,
        allow_offline_upload=True,
    )
    after = fbr_native._get_status(doc.doctype, doc.name)

    if not result.get("network_call"):
        if after.get("fbr_status") != OFFLINE_PENDING:
            frappe.throw(
                "Offline upload was not sent but Offline Pending state was not preserved."
            )
        return {
            **result,
            "offline_upload": True,
            "offline_pending_preserved": True,
            "contains_secrets": False,
        }

    if result.get("status") not in {
        "Submitted",
        "Failed",
        fbr_native.RECONCILIATION_REQUIRED,
    }:
        frappe.throw(
            "Controlled offline upload returned an unsupported terminal state."
        )

    return {
        **result,
        "offline_upload": True,
        "offline_pending_preserved": False,
        "offline_issued_at": current.get("fbr_offline_issued_at"),
        "offline_upload_due_at": current.get("fbr_upload_due_at"),
        "contains_secrets": False,
    }


@frappe.whitelist()
def upload_offline_invoice(
    reference_doctype,
    reference_name,
    confirmation,
):
    _require_roles(ACTION_ROLES, "upload an Offline Pending invoice")
    if _text(confirmation) != UPLOAD_OFFLINE_CONFIRMATION:
        frappe.throw(
            "Confirmation must be exactly: "
            + UPLOAD_OFFLINE_CONFIRMATION
        )
    return upload_offline_native_internal(
        reference_doctype,
        reference_name,
    )
