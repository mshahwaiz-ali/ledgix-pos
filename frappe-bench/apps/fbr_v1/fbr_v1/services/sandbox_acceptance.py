"""Read-only Federal V1 Sandbox transport acceptance, not Production authority.

The legacy DI scenario Certification DocType is not evidence for this projection.
Completion means at least one supported native invoice has a verified V1
Sandbox snapshot, request, and successful fiscal response for this Company's
current V1 profile/device scope. It does not certify untested scenarios or
replace client/provider approval, and it never enables a runtime gate.
"""
import json

import frappe
from frappe.utils import cint

from fbr_v1.protocol.response import parse_fiscal_response
from fbr_v1.services.fbr_v1_payload_builder import build_invoice, digest
from fbr_v1.services.fbr_v1_snapshot_persistence import read_persisted_v1_snapshot
from fbr_v1.services.pos_identity import PROTOCOL

LOG_FIELDS = ["name", "protocol", "pos_device", "reference_doctype", "reference_name",
              "fbr_status", "fbr_invoice_number", "attempt_id", "source_snapshot_hash",
              "request_json", "request_hash", "response_json", "response_hash",
              "transport_outcome", "transport_started_at", "transport_finished_at",
              "reconciliation_required"]


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _verify_log(row, company, devices):
    if (row.get("protocol") != PROTOCOL or row.get("fbr_status") != "Submitted"
            or row.get("transport_outcome") != "Accepted" or cint(row.get("reconciliation_required"))
            or not row.get("attempt_id") or not row.get("transport_started_at")
            or not row.get("transport_finished_at")):
        return False
    if row.get("reference_doctype") not in {"Sales Invoice", "POS Invoice"} or not row.get("reference_name"):
        return False
    device = devices.get(row.get("pos_device"))
    if not device:
        return False
    # Respect invoice permissions as well as the permission-filtered log query.
    frappe.get_doc(row["reference_doctype"], row["reference_name"]).check_permission("read")
    snapshot = read_persisted_v1_snapshot(row["reference_doctype"], row["reference_name"])
    header = snapshot["header"]
    captured_device = header.get("pos_device") or {}
    if (header.get("protocol") != PROTOCOL or header.get("company") != company
            or captured_device.get("company") != company or captured_device.get("environment") != "Sandbox"
            or captured_device.get("name") != device.name
            or str(captured_device.get("pos_id")) != str(device.get("pos_id"))
            or snapshot["snapshot_hash"] != row.get("source_snapshot_hash")):
        return False
    request, response = _json(row.get("request_json")), _json(row.get("response_json"))
    if not isinstance(request, dict) or not isinstance(response, dict):
        return False
    if (not row.get("request_hash") or digest(request) != row["request_hash"]
            or digest(build_invoice(snapshot).to_payload()) != row["request_hash"]
            or not row.get("response_hash") or digest(response) != row["response_hash"]):
        return False
    fiscal = parse_fiscal_response(response)
    return bool(fiscal.success and fiscal.invoice_number == str(row.get("fbr_invoice_number") or "").strip())


def get_sandbox_acceptance(company, profile, devices):
    result = {"complete": False, "status": "Missing Evidence", "protocol": PROTOCOL,
              "company": company, "profile": profile.name if profile else None,
              "scope": "Verified Federal V1 Sandbox fiscal transport acceptance",
              "evidence": [], "verified_evidence_count": 0, "unverified_evidence_count": 0,
              "blockers": [], "production_authorized": False,
              "database_write": False, "fbr_network_call": False, "network_call": False}
    if not profile or profile.get("company") != company or profile.get("protocol_version") != PROTOCOL:
        result["blockers"].append("A current Company Federal V1 Integration Profile is required.")
        return result
    eligible = {d.name: d for d in devices if d.get("company") == company
                and cint(d.get("active")) and d.get("environment") == "Sandbox"}
    if not eligible:
        result["blockers"].append("An active Company Sandbox POS Device is required for acceptance evidence.")
        return result
    try:
        rows = frappe.get_list("Ledgix FBR Submission Log",
            filters={"protocol": PROTOCOL, "pos_device": ["in", sorted(eligible)],
                     "fbr_status": "Submitted", "transport_outcome": "Accepted"},
            fields=LOG_FIELDS, order_by="creation desc", limit_page_length=0)
    except frappe.PermissionError:
        result["status"] = "Evidence Unavailable"
        result["blockers"].append("Read permission for current V1 Sandbox acceptance evidence is required.")
        return result
    rejected = 0
    for row in rows:
        try:
            valid = _verify_log(row, company, eligible)
        except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError,
                ValueError, TypeError, KeyError, ArithmeticError):
            valid = False
        if valid:
            result["evidence"].append({key: row.get(key) for key in (
                "name", "pos_device", "reference_doctype", "reference_name", "source_snapshot_hash")})
        else:
            rejected += 1
    result["verified_evidence_count"] = len(result["evidence"])
    result["unverified_evidence_count"] = rejected
    result["complete"] = bool(result["evidence"])
    result["status"] = "Accepted" if result["complete"] else "Missing Verified Evidence"
    if not result["complete"]:
        result["blockers"].append("No verified current-V1 Sandbox acceptance evidence exists in this Company/profile/device scope.")
    return result
