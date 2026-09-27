"""Read-only fiscal reconstruction with explicit verification and redaction."""
import json
import frappe
from fbr_v1.api.fiscalization import source, require_operator
from fbr_v1.services.fbr_submission_support import sanitize
from fbr_v1.services.fbr_v1_snapshot_persistence import read_persisted_v1_snapshot
from fbr_v1.services.fbr_v1_payload_builder import build_invoice, digest
from fbr_v1.services.pos_identity import get_profile


def _json(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {"unparseable_json_omitted": True}


def _records(doctype, filters, fields):
    # Permission-filtered queries also respect company/user restrictions.
    return frappe.get_list(doctype, filters=filters, fields=fields, order_by="creation asc", limit_page_length=0)


@frappe.whitelist()
def get_fiscal_audit_bundle(reference_doctype, reference_name):
    require_operator()
    doc = source(reference_doctype, reference_name)
    filters = {"reference_doctype": doc.doctype, "reference_name": doc.name}
    snapshot = {"header": _json(doc.get("custom_ledgix_fbr_snapshot_json")),
                "snapshot_hash": doc.get("custom_ledgix_fbr_snapshot_hash"),
                "lines": {r.name: _json(r.get("custom_ledgix_fbr_snapshot_json")) for r in doc.get("items") or []}}
    verification = {"valid": False}
    payload = None
    try:
        snapshot = read_persisted_v1_snapshot(doc.doctype, doc.name)
        verification = {"valid": True, "header_hash": snapshot["snapshot_hash"], "line_manifest_verified": True}
    except (ValueError, KeyError, TypeError, ArithmeticError, frappe.ValidationError):
        verification["error"] = "Snapshot missing, invalid or inconsistent with its native source; retained raw evidence is unverified."
    serialization = {"valid": False}
    if verification["valid"]:
        try:
            payload = build_invoice(snapshot).to_payload()
            serialization = {"valid": True, "request_hash": digest(payload)}
        except (ValueError, KeyError, TypeError, ArithmeticError, frappe.ValidationError):
            serialization["error"] = "Snapshot cannot be serialized under the supported Federal V1 contract."
    logs = _records("Ledgix FBR Submission Log", filters, ["name", "creation", "protocol", "pos_device",
        "attempt_id", "idempotency_key", "fbr_status", "fbr_invoice_number", "request_json", "response_json",
        "source_snapshot_hash", "request_hash", "response_hash", "transport_outcome", "transport_started_at",
        "transport_finished_at", "submitted_at", "submitted_by", "operator", "reconciliation_required",
        "external_reference", "external_evidence", "offline_issued_at", "offline_upload_due_at"])
    for row in logs:
        for key in ("request_json", "response_json"):
            row[key] = _json(row.get(key))
    events = _records("Ledgix FBR Fiscal Event Log", filters, ["name", "creation", "pos_device", "event_type",
        "occurred_at", "external_reference", "external_evidence", "event_json", "event_hash", "created_by"])
    corrections = _records("Ledgix FBR Correction Request", filters, ["name", "creation", "action_type", "reason",
        "status", "fbr_invoice_number", "fbr_generated_at", "correction_deadline", "correction_path",
        "requested_at", "requested_by", "board_reference", "external_evidence", "commissioner_approval_reference",
        "completed_at", "generation_time_reference", "generation_time_evidence"])
    header = snapshot.get("header") if isinstance(snapshot.get("header"), dict) else {}
    device = header.get("pos_device") or {}
    if device.get("name"):
        device_events = _records("Ledgix FBR Fiscal Event Log", {"pos_device": device["name"], "reference_name": ["is", "not set"]},
            ["name", "creation", "pos_device", "event_type", "occurred_at", "external_reference", "external_evidence", "event_json", "event_hash", "created_by"])
        events.extend(device_events)
    for row in events:
        row["event_json"] = _json(row["event_json"])
        row["hash_verified"] = digest(row["event_json"]) == row["event_hash"]
    original = None
    if doc.get("is_return") and doc.get("return_against"):
        original_doc = source(doc.doctype, doc.return_against)
        original = {"doctype": original_doc.doctype, "name": original_doc.name,
                    "fbr_invoice_number": original_doc.get("custom_ledgix_fbr_invoice_number"),
                    "snapshot_hash": original_doc.get("custom_ledgix_fbr_snapshot_hash"), "ref_usin": header.get("ref_usin")}
    closings = []
    if device.get("name"):
        for row in _records("Ledgix FBR Fiscal Closing", {"pos_device": device["name"]},
                ["name", "period_type", "period_start", "period_end", "status", "external_status",
                 "source_manifest", "source_manifest_hash", "snapshot_hash", "generated_at", "generated_by"]):
            manifest = _json(row.pop("source_manifest"))
            if isinstance(manifest, list) and any(r.get("doctype") == doc.doctype and r.get("name") == doc.name for r in manifest):
                row["manifest_hash_verified"] = digest(manifest) == row["source_manifest_hash"]
                closings.append(row)
    # Known legacy credentials are used ONLY to redact old evidence, never as transport fallback.
    secrets = []
    profile = get_profile(doc.company)
    if profile:
        for field in ("v1_sandbox_token", "v1_production_token", "sandbox_token", "production_token"):
            try:
                secrets.append(profile.get_password(field, raise_exception=False))
            except Exception:
                pass
    bundle = {"source": {k: doc.get(k) for k in ("doctype", "name", "company", "docstatus", "creation",
        "modified", "posting_date", "posting_time", "is_return", "return_against")},
        "snapshot": snapshot, "snapshot_verification": verification,
        "serialized_request": payload, "serialization": serialization,
        "device_identity_snapshot": device, "submission_logs": logs, "fiscal_events": events,
        "corrections": corrections, "closings": closings,
        "fiscal_state": {k: doc.get(k) for k in ("custom_ledgix_fbr_status", "custom_ledgix_fbr_invoice_number",
            "custom_ledgix_fbr_generated_at", "custom_ledgix_fbr_submitted_at", "custom_ledgix_fbr_reconciliation_required",
            "custom_ledgix_fbr_offline_issued_at", "custom_ledgix_fbr_restored_at", "custom_ledgix_fbr_upload_due_at")},
        "original_invoice": original,
        "database_write": False, "network_call": False,
        "redacted": True, "hashes_refer_to_stored_evidence_before_export_redaction": True}
    return sanitize(bundle, secrets)
