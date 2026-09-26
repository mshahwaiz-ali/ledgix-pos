# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime


class LedgixFBRSubmissionLog(Document):
	def after_insert(self):
		"""Persist FBR's own invoice generation timestamp for correction-window tracking."""
		if self.reference_doctype != "Ledgix Sale" or self.fbr_status != "Submitted" or not self.reference_name:
			return
		if not frappe.db.exists("Ledgix Sale", self.reference_name):
			return
		if frappe.db.get_value("Ledgix Sale", self.reference_name, "fbr_generated_at"):
			return

		try:
			payload = json.loads(self.response_json) if isinstance(self.response_json, str) else (self.response_json or {})
		except (TypeError, ValueError):
			return
		if not isinstance(payload, dict):
			return

		response = payload.get("response") if isinstance(payload.get("response"), dict) else payload
		dated = response.get("dated") if isinstance(response, dict) else None
		if not dated:
			return

		try:
			generated_at = get_datetime(dated)
		except Exception:
			return

		frappe.db.set_value(
			"Ledgix Sale",
			self.reference_name,
			"fbr_generated_at",
			generated_at,
			update_modified=False,
		)
