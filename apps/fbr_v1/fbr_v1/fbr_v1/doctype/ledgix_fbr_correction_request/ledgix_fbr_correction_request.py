"""Historical correction records are retained; unsupported workflow is retired."""
import frappe
from frappe.model.document import Document

class LedgixFBRCorrectionRequest(Document):
    def validate(self):
        frappe.throw("Correction Request workflow is retired. Use native ERPNext credit/return evidence; external correction contract is unresolved.")
    def on_trash(self):
        frappe.throw("Historical fiscal correction evidence cannot be deleted.")
