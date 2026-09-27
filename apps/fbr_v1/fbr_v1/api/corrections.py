"""Controlled internal correction evidence; no Board API or accounting mutation."""
import frappe
from frappe.utils import now_datetime
from fbr_v1.api.compliance_evidence import require_external_evidence
from fbr_v1.api.fiscalization import require_operator, source
from fbr_v1.services.fbr_submission_support import submission_lock
from fbr_v1.fbr_v1.doctype.ledgix_fbr_correction_request.ledgix_fbr_correction_request import CONTROLLED_WRITE


@frappe.whitelist(methods=["POST"])
def request_correction(reference_doctype, reference_name, action_type, reason,
                       fbr_generated_at=None, generation_time_reference=None, generation_time_evidence=None):
    require_operator()
    invoice = source(reference_doctype, reference_name, "submit")
    if not (invoice.get("custom_ledgix_fbr_snapshot_protocol") == "Federal POS/IMS V1"
            and invoice.get("custom_ledgix_fbr_generated_at")):
        require_external_evidence(generation_time_reference, generation_time_evidence)
    with submission_lock(f"{reference_doctype}:{reference_name}"):
        doc = frappe.get_doc({"doctype": "Ledgix FBR Correction Request",
            "reference_doctype": reference_doctype, "reference_name": reference_name,
            "action_type": action_type, "reason": reason, "fbr_generated_at": fbr_generated_at,
            "requested_by": frappe.session.user, "requested_at": now_datetime(),
            "generation_time_reference": generation_time_reference, "generation_time_evidence": generation_time_evidence})
        doc.flags.fbr_v1_controlled_write = CONTROLLED_WRITE
        doc.insert(ignore_permissions=True)
        return {"name": doc.name, "status": doc.status, "deadline": doc.correction_deadline, "network_call": False}


@frappe.whitelist(methods=["POST"])
def record_correction_result(correction_request, status, board_reference, external_evidence,
                             commissioner_approval_reference=None):
    require_operator()
    if status not in {"Completed", "Rejected"}:
        frappe.throw("Select Completed or Rejected based on external evidence.")
    require_external_evidence(board_reference, external_evidence)
    with submission_lock("correction:" + correction_request):
        doc = frappe.get_doc("Ledgix FBR Correction Request", correction_request, for_update=True)
        doc.check_permission("read")
        source(doc.reference_doctype, doc.reference_name, "submit")
        doc.update({"status": status, "board_reference": board_reference, "external_evidence": external_evidence,
                    "commissioner_approval_reference": commissioner_approval_reference})
        doc.flags.fbr_v1_controlled_write = CONTROLLED_WRITE
        doc.save(ignore_permissions=True)
        return {"name": doc.name, "status": doc.status, "network_call": False, "source_invoice_changed": False}
