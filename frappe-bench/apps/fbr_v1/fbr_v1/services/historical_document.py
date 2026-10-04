"""Controller contract preserving retired metadata and rejecting writes."""
import frappe
from frappe.model.document import Document

class HistoricalDocument(Document):
    def validate(self):
        frappe.throw("Retired historical FBR evidence is read-only.")
    before_insert = validate
    before_save = validate
    before_submit = validate
    before_cancel = validate
    on_trash = validate
