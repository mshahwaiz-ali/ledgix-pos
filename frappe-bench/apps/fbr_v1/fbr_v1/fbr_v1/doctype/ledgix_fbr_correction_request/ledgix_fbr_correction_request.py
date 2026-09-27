"""Internal Board/PRAL tracking only; source invoices are never mutated here."""
from datetime import timedelta
import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime
from fbr_v1.api.fiscalization import source, history

CONTROLLED_WRITE = object()
FROZEN = ("reference_doctype", "reference_name", "fbr_invoice_number", "fbr_generated_at",
          "generation_time_reference", "generation_time_evidence", "action_type", "reason",
          "requested_by", "requested_at", "correction_deadline")


class LedgixFBRCorrectionRequest(Document):
    def before_insert(self):
        self._require_controlled_write()

    def before_save(self):
        self._require_controlled_write()

    def _require_controlled_write(self):
        if self.flags.get("fbr_v1_controlled_write") is not CONTROLLED_WRITE:
            frappe.throw("Use the controlled correction request/completion actions.")

    def validate(self):
        # Authorization and user stamping belong to the API; validation is session-independent.
        old = self.get_doc_before_save()
        if old:
            if old.status in {"Completed", "Rejected"}:
                frappe.throw("Completed/rejected correction evidence is immutable.")
            if any(self.get(k) != old.get(k) for k in FROZEN):
                frappe.throw("Original correction request evidence is immutable.")
        if self.reference_doctype not in {"Sales Invoice", "POS Invoice"} or not self.reference_name:
            frappe.throw("Select Sales Invoice or POS Invoice and an existing source name.")
        doc = frappe.get_doc(self.reference_doctype, self.reference_name)
        if doc.docstatus != 1:
            frappe.throw("Correction requires a submitted source invoice.")
        device = doc.get("custom_ledgix_fbr_pos_device")
        if not device or frappe.db.get_value("Ledgix FBR POS Device", device, "company") != doc.company:
            frappe.throw("Correction tracking requires a source POS device belonging to the invoice company.")
        numbers = {str(r.get("fbr_invoice_number")) for r in history(doc) if r.get("fbr_invoice_number")}
        if doc.get("custom_ledgix_fbr_invoice_number"):
            numbers.add(str(doc.get("custom_ledgix_fbr_invoice_number")))
        if len(numbers) != 1:
            frappe.throw("A single authoritative FBR invoice number is required; reconcile conflicting history first.")
        number = numbers.pop()
        if old and self.fbr_invoice_number != number:
            frappe.throw("Source fiscal identity changed; reconcile before correction completion.")
        self.fbr_invoice_number = number
        if self.action_type not in {"Cancel", "Delete", "Edit"} or not str(self.reason or "").strip():
            frappe.throw("Select Cancel/Delete/Edit and provide a bona-fide reason.")
        if not old:
            official = (doc.get("custom_ledgix_fbr_generated_at")
                        if doc.get("custom_ledgix_fbr_snapshot_protocol") == "Federal POS/IMS V1" else None)
            if official:
                self.fbr_generated_at = official
            else:
                _validate_external_evidence(self.generation_time_reference, self.generation_time_evidence)
            if not self.fbr_generated_at:
                frappe.throw("Authoritative FBR generation timestamp is required; local submission time is not a substitute.")
            if not self.requested_at or not self.requested_by:
                frappe.throw("Correction requester and request timestamp are required.")
        generated = get_datetime(self.fbr_generated_at)
        if generated > now_datetime():
            frappe.throw("FBR generation timestamp cannot be in the future.")
        self.correction_deadline = generated + timedelta(hours=72)
        late = now_datetime() > self.correction_deadline
        self.correction_path = "Commissioner Approval Required" if late else "Within 72 Hours"
        if self.status in {"Completed", "Rejected"}:
            _validate_external_evidence(self.board_reference, self.external_evidence)
            if self.status == "Completed" and late and not str(self.commissioner_approval_reference or "").strip():
                frappe.throw("Completion after the deadline requires commissioner approval and external evidence.")
            self.completed_at = now_datetime()
        else:
            self.status = "Commissioner Approval Pending" if late else "Board Action Pending"
            self.completed_at = None

    def on_update(self):
        from fbr_v1.api.fbr_offline import append_event
        doc = source(self.reference_doctype, self.reference_name)
        body = {k: self.get(k) for k in FROZEN + ("status", "correction_path", "board_reference",
                "external_evidence", "commissioner_approval_reference", "completed_at")}
        body.update(correction_request=self.name, internal_tracking_only=True)
        event_type = "Correction Filed" if self.status in {"Completed", "Rejected"} else "Adjustment"
        append_event(doc.get("custom_ledgix_fbr_pos_device"), event_type, body,
            doctype=self.reference_doctype, name=self.reference_name,
            external_reference=self.board_reference, external_evidence=self.external_evidence)
        if self.commissioner_approval_reference:
            append_event(doc.get("custom_ledgix_fbr_pos_device"), "Commissioner Approval Recorded", body,
                doctype=self.reference_doctype, name=self.reference_name,
                external_reference=self.commissioner_approval_reference, external_evidence=self.external_evidence)

    def on_trash(self):
        frappe.throw("Fiscal correction evidence cannot be deleted.")


def _validate_external_evidence(reference, evidence):
    # Existence is a document invariant. File read permission is checked by the API.
    if not str(reference or "").strip() or not str(evidence or "").strip():
        frappe.throw("Authoritative external reference and evidence are required.")
    if not frappe.db.exists("File", {"file_url": evidence}):
        frappe.throw("Select an uploaded evidence attachment.")
