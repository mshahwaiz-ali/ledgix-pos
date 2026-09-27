"""Operator-recorded external evidence; these APIs never contact FBR."""
import frappe
from frappe.utils import get_datetime, now_datetime
from fbr_v1.api.fiscalization import require_operator, source
from fbr_v1.api.fbr_offline import append_event

EVENTS = {"Outage Report Filed", "Alert Report Filed", "Offline Upload Confirmed",
          "Correction Filed", "Commissioner Approval Recorded"}


def require_external_evidence(reference, evidence):
    if not str(reference or "").strip() or not str(evidence or "").strip():
        frappe.throw("Authoritative external reference and evidence are required.")
    # Attach values must identify a readable File; no fetching arbitrary URLs.
    file_name = frappe.db.get_value("File", {"file_url": evidence}, "name")
    if not file_name:
        frappe.throw("Select an uploaded evidence attachment.")
    frappe.get_doc("File", file_name).check_permission("read")


@frappe.whitelist(methods=["POST"])
def record_external_compliance_evidence(pos_device, event_type, external_reference, external_evidence,
                                        reference_doctype=None, reference_name=None, occurred_at=None):
    require_operator()
    if event_type not in EVENTS:
        frappe.throw("Unsupported external compliance event.")
    require_external_evidence(external_reference, external_evidence)
    device = frappe.get_doc("Ledgix FBR POS Device", pos_device)
    device.check_permission("write")
    if bool(reference_doctype) != bool(reference_name):
        frappe.throw("Both invoice type and invoice name are required.")
    if reference_doctype:
        doc = source(reference_doctype, reference_name, "submit")
        if doc.docstatus != 1 or doc.company != device.company or doc.get("custom_ledgix_fbr_pos_device") != device.name:
            frappe.throw("Select a submitted invoice belonging to this POS device and company.")
    at = get_datetime(occurred_at) if occurred_at else now_datetime()
    if at > now_datetime():
        frappe.throw("External event time cannot be in the future.")
    event = append_event(device.name, event_type, {"operator_recorded": True, "recorded_at": str(now_datetime()),
        "invoice_state_changed": False}, occurred_at=at, doctype=reference_doctype, name=reference_name,
        external_reference=external_reference, external_evidence=external_evidence)
    return {"event": event.name, "network_call": False, "invoice_state_changed": False}
