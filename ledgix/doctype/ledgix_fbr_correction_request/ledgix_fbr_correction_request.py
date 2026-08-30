# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime


OPEN_STATUSES = {"Board Action Pending", "Commissioner Approval Pending"}
FINAL_STATUSES = {"Completed", "Rejected"}


class LedgixFBRCorrectionRequest(Document):
	def before_insert(self):
		self.requested_by = frappe.session.user
		self.requested_at = now_datetime()

	def validate(self):
		sale = self._get_sale()
		self._freeze_sale_reference(sale)
		self._apply_correction_window()
		self._validate_duplicate_open_request()
		self._validate_completion_requirements()

	def _get_sale(self):
		if not self.sale:
			frappe.throw("Sale is required.")
		if not frappe.db.exists("Ledgix Sale", self.sale):
			frappe.throw(f"Ledgix Sale {self.sale} was not found.")

		sale = frappe.get_doc("Ledgix Sale", self.sale)
		if sale.docstatus != 1:
			frappe.throw("FBR correction tracking requires a submitted sale.")
		if not sale.fbr_invoice_number:
			frappe.throw("The sale does not have an official FBR invoice number.")
		if sale.fbr_status != "Submitted":
			frappe.throw("The sale must be in FBR Submitted status before a correction request can be tracked.")
		return sale

	def _freeze_sale_reference(self, sale):
		if not self.fbr_invoice_number:
			self.fbr_invoice_number = sale.fbr_invoice_number
		elif self.fbr_invoice_number != sale.fbr_invoice_number:
			frappe.throw("FBR Invoice Number cannot be changed after the correction request is created.")

		if not self.fbr_generated_at:
			self.fbr_generated_at = sale.fbr_generated_at or sale.fbr_submitted_at
		if not self.fbr_generated_at:
			frappe.throw(
				"FBR generation time is unavailable. The 72-hour correction window cannot be calculated safely."
			)

		self.fbr_generated_at = get_datetime(self.fbr_generated_at)
		self.correction_deadline = add_to_date(self.fbr_generated_at, hours=72, as_datetime=True)

	def _apply_correction_window(self):
		if self.status in FINAL_STATUSES:
			if self.status == "Completed" and not self.completed_at:
				self.completed_at = now_datetime()
			return

		if now_datetime() <= get_datetime(self.correction_deadline):
			self.correction_path = "Within 72 Hours"
			self.status = "Board Action Pending"
		else:
			self.correction_path = "Commissioner Approval Required"
			self.status = "Commissioner Approval Pending"
		self.completed_at = None

	def _validate_duplicate_open_request(self):
		existing = frappe.get_all(
			"Ledgix FBR Correction Request",
			filters={
				"sale": self.sale,
				"status": ["in", list(OPEN_STATUSES)],
				"name": ["!=", self.name or ""],
			},
			pluck="name",
			limit=1,
		)
		if existing:
			frappe.throw(
				f"Open FBR correction request {existing[0]} already exists for sale {self.sale}. "
				"Complete or reject it before creating another request."
			)

	def _validate_completion_requirements(self):
		if self.status != "Completed":
			return
		if not str(self.board_reference or "").strip():
			frappe.throw("Board Reference is required before marking an FBR correction request Completed.")
		if self.correction_path == "Commissioner Approval Required" and not str(
			self.commissioner_approval_reference or ""
		).strip():
			frappe.throw(
				"Commissioner Approval Reference is required for corrections completed after the 72-hour window."
			)
