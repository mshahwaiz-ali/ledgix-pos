import frappe
from frappe.model.document import Document

class LedgixFBRFiscalClosing(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Internal fiscal closings are immutable evidence.")
        if self.status != "Closed Internally":
            frappe.throw("External closing contract is unresolved.")
    def on_trash(self):
        frappe.throw("Fiscal closing evidence cannot be deleted.")
