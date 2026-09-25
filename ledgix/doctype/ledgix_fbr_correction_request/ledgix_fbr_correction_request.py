# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime


OPEN_STATUSES = {"Board Action Pending", "Commissioner Approval Pending"}
FINAL_STATUSES = {"Completed", "Rejected"}
NATIVE_DOCTYPES = {"Sales Invoice", "POS Invoice"}


class LedgixFBRCorrectionRequest(Document):
	def before_insert(self):
		self.requested_by = frappe.session.user
		self.requested_at = now_datetime()

	def validate(self):
		reference = self._get_reference()
		self._freeze_reference(reference)
		self._apply_correction_window()
		self._validate_duplicate_open_request()
		self._validate_completion_requirements()

	def _get_reference(self):
		if self.reference_doctype or self.reference_name:
			if self.reference_doctype not in NATIVE_DOCTYPES:
				frappe.throw("Reference DocType must be Sales Invoice or POS Invoice.")
			if not self.reference_name:
				frappe.throw("Native Invoice reference is required.")
			if not frappe.db.exists(self.reference_doctype, self.reference_name):
				frappe.throw(f"{self.reference_doctype} {self.reference_name} was not found.")
			doc = frappe.get_doc(self.reference_doctype, self.reference_name)
			if doc.docstatus != 1:
				frappe.throw("FBR correction tracking requires a submitted ERPNext invoice.")
			if not doc.get("custom_ledgix_fbr_invoice_number"):
				frappe.throw("The ERPNext invoice does not have an official FBR invoice number.")
			if doc.get("custom_ledgix_fbr_status") != "Submitted":
				frappe.throw("The ERPNext invoice must be in FBR Submitted status before correction tracking.")
			return doc

		if not self.sale:
			frappe.throw("ERPNext native invoice reference is required. Legacy Sale is accepted only for historical records.")
		if not frappe.db.exists("Ledgix Sale", self.sale):
			frappe.throw(f"Ledgix Sale {self.sale} was not found.")
		doc = frappe.get_doc("Ledgix Sale", self.sale)
		if doc.docstatus != 1:
			frappe.throw("FBR correction tracking requires a submitted sale.")
		if not doc.fbr_invoice_number:
			frappe.throw("The sale does not have an official FBR invoice number.")
		if doc.fbr_status != "Submitted":
			frappe.throw("The sale must be in FBR Submitted status before correction tracking.")
		return doc

	def _reference_values(self, doc):
		if doc.doctype in NATIVE_DOCTYPES:
			return {
				"invoice_number": doc.get("custom_ledgix_fbr_invoice_number"),
				"generated_at": doc.get("custom_ledgix_fbr_generated_at"),
			}
		return {
			"invoice_number": doc.get("fbr_invoice_number"),
			"generated_at": doc.get("fbr_generated_at") or doc.get("fbr_submitted_at"),
		}

	def _freeze_reference(self, doc):
		values = self._reference_values(doc)
		invoice_number = values.get("invoice_number") or ""
		if not self.fbr_invoice_number:
			self.fbr_invoice_number = invoice_number
		elif self.fbr_invoice_number != invoice_number:
			frappe.throw("FBR Invoice Number cannot be changed after the correction request is created.")

		if not self.fbr_generated_at:
			self.fbr_generated_at = values.get("generated_at")
		if not self.fbr_generated_at:
			frappe.throw(
				"Official FBR generation time is unavailable. The 72-hour correction "
				"window cannot be calculated safely for a new correction request."
			)
		self.fbr_generated_at = get_datetime(self.fbr_generated_at)
		self.correction_deadline = add_to_date(self.fbr_generated_at, hours=72, as_datetime=True)

	def _apply_correction_window(self):
		deadline = get_datetime(self.correction_deadline)
		decision_time = get_datetime(self.completed_at) if self.status == "Completed" and self.completed_at else now_datetime()
		within_window = decision_time <= deadline
		self.correction_path = "Within 72 Hours" if within_window else "Commissioner Approval Required"
		if self.status == "Completed":
			if not self.completed_at:
				self.completed_at = decision_time
			return
		if self.status == "Rejected":
			return
		self.status = "Board Action Pending" if within_window else "Commissioner Approval Pending"
		self.completed_at = None

	def _validate_duplicate_open_request(self):
		filters = {
			"status": ["in", list(OPEN_STATUSES)],
			"name": ["!=", self.name or ""],
		}
		if self.reference_doctype and self.reference_name:
			filters.update({"reference_doctype": self.reference_doctype, "reference_name": self.reference_name})
		else:
			filters["sale"] = self.sale
		existing = frappe.get_all(
			"Ledgix FBR Correction Request",
			filters=filters,
			pluck="name",
			limit=1,
		)
		if existing:
			frappe.throw(
				f"Open FBR correction request {existing[0]} already exists for this invoice. "
				"Complete or reject it before creating another request."
			)

	def _validate_completion_requirements(self):
		if self.status != "Completed":
			return
		if not str(self.external_evidence or "").strip():
			frappe.throw(
				"External Completion Evidence is required before marking an FBR "
				"correction request Completed."
			)
		if not str(self.board_reference or "").strip():
			frappe.throw("Board Reference is required before marking an FBR correction request Completed.")
		if self.correction_path == "Commissioner Approval Required" and not str(
			self.commissioner_approval_reference or ""
		).strip():
			frappe.throw(
				"Commissioner Approval Reference is required for corrections completed after the 72-hour window."
			)
