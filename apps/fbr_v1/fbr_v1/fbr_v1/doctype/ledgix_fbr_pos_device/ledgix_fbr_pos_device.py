import frappe
from frappe.model.document import Document

class LedgixFBRPOSDevice(Document):
    def validate(self):
        if self.pos_id and (not str(self.pos_id).isascii() or not str(self.pos_id).isdigit() or int(self.pos_id) <= 0):
            frappe.throw("POSID must be positive numeric text.")
        if self.pos_profile and frappe.db.get_value("POS Profile", self.pos_profile, "company") != self.company:
            frappe.throw("POS Profile must belong to the device company.")
        if self.active and not self.pos_id:
            frappe.throw("An active device requires a registered POSID.")
