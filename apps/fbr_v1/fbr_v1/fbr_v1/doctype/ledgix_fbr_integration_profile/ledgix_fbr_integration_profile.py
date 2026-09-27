import frappe
from frappe.model.document import Document

class LedgixFBRIntegrationProfile(Document):
    def validate(self):
        # A legacy profile is never silently activated as V1.
        if self.protocol_version != "Federal POS/IMS V1":
            self.enabled = self.transport_enabled = self.production_post_armed = 0
            self.mode = "Disabled"
        self.protocol_version = "Federal POS/IMS V1"
        if self.mode != "Production":
            self.production_post_armed = 0
        if self.mode == "Paused" and not self.pause_reason:
            frappe.throw("Pause Reason is required.")
        if self.default_pos_device and frappe.db.get_value("Ledgix FBR POS Device", self.default_pos_device, "company") != self.company:
            frappe.throw("Default POS device must belong to the profile company.")
