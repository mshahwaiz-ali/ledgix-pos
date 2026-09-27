"""Restoration + 24h evidence. External offline upload remains unavailable."""
import json
from datetime import timedelta
import frappe
from frappe.utils import get_datetime, now_datetime
from fbr_v1.api.fiscalization import require_operator, source, history, history_blocker, mark
from fbr_v1.services.fbr_submission_support import sanitize, submission_lock, create_submission_log
from fbr_v1.services.fbr_v1_payload_builder import digest
from fbr_v1.services.fbr_v1_snapshot_persistence import read_persisted_v1_snapshot
from fbr_v1.services.pos_identity import get_profile

EVENT = "Ledgix FBR Fiscal Event Log"
FAILURES = {"Connectivity Failure", "Software Failure", "Power Failure"}


def restoration_due_at(restored_at):
    return get_datetime(restored_at) + timedelta(hours=24)


def append_event(device, event_type, evidence=None, *, occurred_at=None, doctype=None, name=None, external_reference=None, external_evidence=None):
    body = {"pos_device": device, "event_type": event_type, "occurred_at": str(occurred_at or now_datetime()),
            "reference_doctype": doctype, "reference_name": name,
            "external_reference": external_reference, "external_evidence": external_evidence,
            "evidence": sanitize(evidence or {}), "created_by": frappe.session.user}
    return frappe.get_doc({"doctype": EVENT, **{k: v for k, v in body.items() if k != "evidence"},
        "event_json": json.dumps(body, sort_keys=True, default=str), "event_hash": digest(body),
        "severity": "Warning" if event_type in FAILURES else "Info"}).insert(ignore_permissions=True)


def offline_invoice(doc):
    profile = get_profile(doc.company)
    if not profile or profile.get("offline_policy") != "Operator Confirmed" or not (
            profile.get("offline_authority_reference") and profile.get("offline_authority_evidence")):
        frappe.throw(
            "Known-offline issuance is disabled. "
            "The Federal V1 offline policy must be explicitly authorized before use."
        )

    with submission_lock(f"{doc.doctype}:{doc.name}"):
        doc.reload()
        if doc.get("custom_ledgix_fbr_status") == "Offline Pending":
            return {"status": "Offline Pending", "network_call": False}
        blocked = history_blocker(doc, history(doc))
        if blocked:
            frappe.throw("Fiscal history requires reconciliation before offline classification.")
        snapshot = read_persisted_v1_snapshot(doc.doctype, doc.name)
        device = snapshot["header"]["pos_device"]["name"]
        if frappe.db.get_value("Ledgix FBR POS Device", device, "operational_state") != "Offline":
            frappe.throw("Record a device failure before issuing offline evidence.")
        issued = now_datetime()
        append_event(device, "Offline Invoice Issued", {"snapshot_hash": snapshot["snapshot_hash"]},
                     occurred_at=issued, doctype=doc.doctype, name=doc.name)
        mark(doc, "Offline Pending", custom_ledgix_fbr_offline_issued_at=issued,
             custom_ledgix_fbr_offline_reason="Recorded device outage", custom_ledgix_fbr_upload_due_at=None)
        create_submission_log(doc.doctype, doc.name, "Credit Note" if doc.get("is_return") else "Sale Invoice",
            "Offline Pending", pos_device=device, transport_outcome="Offline Deferred", offline_issued_at=issued,
            source_snapshot_hash=snapshot["snapshot_hash"])
        return {"status": "Offline Pending", "due_at": None, "network_call": False}


@frappe.whitelist()
def mark_offline(reference_doctype, reference_name):
    require_operator()
    return offline_invoice(source(reference_doctype, reference_name, "submit"))


@frappe.whitelist()
def record_device_event(pos_device, event_type):
    require_operator()
    device = frappe.get_doc("Ledgix FBR POS Device", pos_device)
    device.check_permission("write")
    if event_type not in FAILURES | {"Startup", "Shutdown", "Restoration"}:
        frappe.throw("Select a supported operational event.")
    with submission_lock("device:" + device.name):
        device.reload()
        at = now_datetime()
        evidence = {}
        if event_type == "Restoration":
            if device.operational_state != "Offline":
                frappe.throw("Restoration requires an outstanding recorded outage.")
            pending = []
            for dt in ("Sales Invoice", "POS Invoice"):
                for row in frappe.get_all(dt, filters={"custom_ledgix_fbr_pos_device": device.name,
                        "docstatus": 1, "custom_ledgix_fbr_status": "Offline Pending"},
                        fields=["name", "custom_ledgix_fbr_upload_due_at"], limit_page_length=0):
                    # A later outage/restoration never extends an existing deadline.
                    if row.get("custom_ledgix_fbr_upload_due_at"):
                        continue
                    frappe.db.set_value(dt, row.name, {"custom_ledgix_fbr_restored_at": at,
                        "custom_ledgix_fbr_upload_due_at": restoration_due_at(at)}, update_modified=False)
                    pending.append({"doctype": dt, "name": row.name})
            evidence = {"due_at": str(restoration_due_at(at)), "pending": pending}
            device.db_set("operational_state", "Operational")
        elif event_type in FAILURES:
            device.db_set("operational_state", "Offline")
        elif event_type == "Startup" and device.operational_state != "Offline":
            device.db_set("operational_state", "Operational")
        event = append_event(device.name, event_type, evidence, occurred_at=at)
        return {"event": event.name, "network_call": False, **evidence}


@frappe.whitelist()
def upload_offline(*args, **kwargs):
    require_operator()
    frappe.throw("Separate Federal V1 offline-upload endpoint/schema is unresolved; upload is unavailable.")


@frappe.whitelist(methods=["POST"])
def record_offline_upload_confirmation(reference_doctype, reference_name, external_reference,
                                       external_evidence, fbr_invoice_number):
    from fbr_v1.api.compliance_evidence import require_external_evidence
    require_operator()
    require_external_evidence(external_reference, external_evidence)
    number = str(fbr_invoice_number or "").strip()
    if not number:
        frappe.throw("The authoritative FBR invoice number is required.")
    doc = source(reference_doctype, reference_name, "submit")
    with submission_lock(f"{doc.doctype}:{doc.name}"):
        doc = frappe.get_doc(reference_doctype, reference_name, for_update=True)
        doc.check_permission("submit")
        if doc.docstatus != 1 or doc.get("custom_ledgix_fbr_status") != "Offline Pending":
            frappe.throw("Only a submitted Offline Pending invoice can be confirmed.")
        if history_blocker(doc, history(doc)):
            frappe.throw("Fiscal history requires reconciliation; offline confirmation is blocked.")
        restored = doc.get("custom_ledgix_fbr_restored_at")
        due = doc.get("custom_ledgix_fbr_upload_due_at")
        if not restored or not due:
            frappe.throw("Recorded restoration and its fixed upload deadline are required.")
        snapshot = read_persisted_v1_snapshot(doc.doctype, doc.name)
        device = frappe.get_doc("Ledgix FBR POS Device", snapshot["header"]["pos_device"]["name"])
        device.check_permission("write")
        if device.company != doc.company:
            frappe.throw("POS device company mismatch.")
        at = now_datetime()
        evidence = {"operator_confirmation": True, "external_reference": external_reference,
            "external_evidence": external_evidence, "fbr_invoice_number": number,
            "recorded_at": str(at), "restored_at": str(restored), "due_at": str(due),
            "confirmed_after_deadline": at > get_datetime(due), "operator": frappe.session.user,
            "network_call": False}
        log = create_submission_log(doc.doctype, doc.name, "Credit Note" if doc.get("is_return") else "Sale Invoice",
            "Submitted", fbr_invoice_number=number, transport_outcome="Externally Confirmed",
            source_snapshot_hash=snapshot["snapshot_hash"], pos_device=device.name,
            external_reference=external_reference, external_evidence=external_evidence,
            operator=frappe.session.user, offline_issued_at=doc.get("custom_ledgix_fbr_offline_issued_at"),
            offline_upload_due_at=due)
        event = append_event(device.name, "Offline Upload", {**evidence, "submission_log": log},
            occurred_at=at, doctype=doc.doctype, name=doc.name,
            external_reference=external_reference, external_evidence=external_evidence)
        mark(doc, "Submitted", custom_ledgix_fbr_invoice_number=number,
             custom_ledgix_fbr_submitted_at=at, custom_ledgix_fbr_submission_log=log,
             custom_ledgix_fbr_reconciliation_required=0)
        return {"status": "Submitted", "log": log, "event": event.name, **evidence}
