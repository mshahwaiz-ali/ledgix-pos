import frappe
from frappe.model.document import Document

class LedgixFBRSubmissionLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Fiscal attempt evidence is append-only.")
    def on_trash(self):
        frappe.throw("Fiscal attempt evidence cannot be deleted.")
