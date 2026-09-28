import frappe
from frappe.model.document import Document


class LedgixFBRPOSDevice(Document):
    def validate(self):
        if not self.company or not frappe.db.exists("Company", self.company):
            frappe.throw("An existing ERPNext Company is required.")
        pos_id = str(self.pos_id or "")
        if pos_id and (not pos_id.isascii() or not pos_id.isdigit() or not 0 < int(pos_id) <= 9223372036854775807):
            frappe.throw("POSID must be positive bigint digits.")
        if self.pos_profile and frappe.db.get_value("POS Profile", self.pos_profile, "company") != self.company:
            frappe.throw("POS Profile must belong to the device company.")
        if self.active:
            if not pos_id:
                frappe.throw("An active device requires a registered POSID.")
            if self.environment not in {"Sandbox", "Production"}:
                frappe.throw("An active device requires Sandbox or Production environment.")
            if self.transport_topology not in {"Cloud API", "Local IMS - Server Reachable"}:
                frappe.throw("An active device requires a supported transport topology.")
