import frappe
from frappe.model.document import Document
from fbr_v1.services.authority_evidence import AUTHORITY_STATES, stamp_verification


class LedgixFBRIntegrationProfile(Document):
    def validate(self):
        # Legacy credentials and authority are never promoted to Federal V1.
        if self.protocol_version != "Federal POS/IMS V1":
            self.enabled = self.transport_enabled = self.production_post_armed = 0
            self.mode = "Disabled"
        self.protocol_version = "Federal POS/IMS V1"
        if self.mode == "Disabled":
            self.transport_enabled = self.production_post_armed = 0
        if self.mode != "Production":
            self.production_post_armed = 0
        if self.mode == "Paused" and not self.pause_reason:
            frappe.throw("Pause Reason is required.")
        if self.default_pos_device and frappe.db.get_value("Ledgix FBR POS Device", self.default_pos_device, "company") != self.company:
            frappe.throw("Default POS device must belong to the profile company.")
        if self.provider_type == "Licensed Integrator" and not self.licensed_integrator_name:
            frappe.throw("Licensed Integrator Name is required.")
        if self.offline_policy == "Operator Confirmed" and not (
                self.get("offline_authority_reference") and self.get("offline_authority_evidence")):
            frappe.throw("Operator Confirmed offline policy requires authority reference and evidence.")
        stamp_verification(self, "authority_status", "authority_reference", "authority_evidence",
                           "authority_verified_at", "authority_verified_by", AUTHORITY_STATES,
                           context_fields=("company", "provider_type", "licensed_integrator_name"))
