import frappe
from frappe.model.document import Document

class LedgixFBRFiscalEventLog(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Fiscal events are append-only.")
    def on_trash(self):
        frappe.throw("Fiscal events cannot be deleted.")
