"""Historical app identity only; never a current integration."""
import frappe
from frappe.model.document import Document

def reject(*args, **kwargs):
    frappe.throw("Retired: Digital Invoicing V1.2 is unsupported and cannot be installed or executed.")

class HistoricalDocument(Document):
    def validate(self):
        reject()
    before_insert = validate
    before_save = validate
    before_submit = validate
    before_cancel = validate
    on_trash = validate
