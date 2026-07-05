# Copyright (c) 2026, Ledgix and contributors
# License: MIT

import frappe
from frappe.model.document import Document


class LedgixBrandSettings(Document):
	def validate(self):
		if not self.brand_name:
			self.brand_name = "Ledgix"

	def on_update(self):
		for fieldname in ("symbol_logo", "full_logo", "favicon"):
			self._ensure_public_file(fieldname)
		frappe.clear_cache(doctype="Ledgix Brand Settings")

	def _ensure_public_file(self, fieldname):
		file_url = self.get(fieldname)
		if not file_url:
			return

		file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
		if not file_name:
			return

		file_doc = frappe.get_doc("File", file_name)
		changed = False

		if file_doc.is_private:
			file_doc.is_private = 0
			changed = True

		if changed:
			file_doc.save(ignore_permissions=True)

		public_url = file_doc.file_url
		if public_url and public_url != self.get(fieldname):
			self.db_set(fieldname, public_url, update_modified=False)
