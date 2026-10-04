import frappe
from frappe.model.document import Document
from frappe.utils import cint


class LedgixFBRIntegrationProfile(Document):
    def validate(self):
        old = self.get_doc_before_save()
        if cint(self.get("production_post_armed")) and not cint(old.get("production_post_armed") if old else 0):
            if "System Manager" not in frappe.get_roles():
                frappe.throw("Only System Manager may arm Production posting.", frappe.PermissionError)
        from fbr_v1.services.production_approval import validate_approval
        validate_approval(self, old)

        # Legacy credentials and authority are never promoted to Federal V1.
        if self.protocol_version != "Federal POS/IMS V1":
            self.enabled = self.transport_enabled = self.production_post_armed = 0
            self.mode = "Disabled"
        self.protocol_version = "Federal POS/IMS V1"
        if self.mode == "Disabled":
            self.transport_enabled = self.production_post_armed = 0
        if self.mode != "Production":
            self.production_post_armed = 0
        if self.mode == "Production":
            if not self.get("pos_service_fee_account"):
                frappe.throw("Production Federal V1 requires the FBR POS Service Fee payable account.")
            if self.submit_trigger != "On Submit":
                frappe.throw(
                    "Production Federal V1 profiles must use the On Submit trigger."
                )
            if cint(self.block_print_without_fiscal_result) != 1:
                frappe.throw(
                    "Production Federal V1 profiles must block printing until a fiscal result exists."
                )
        if self.mode == "Paused" and not self.pause_reason:
            frappe.throw("Pause Reason is required.")
        if self.default_pos_device and frappe.db.get_value("Ledgix FBR POS Device", self.default_pos_device, "company") != self.company:
            frappe.throw("Default POS device must belong to the profile company.")
        if self.provider_type == "Licensed Integrator" and not self.licensed_integrator_name:
            frappe.throw("Licensed Integrator Name is required.")
        if self.offline_policy == "Operator Confirmed" and not (
                self.get("offline_authority_reference") and self.get("offline_authority_evidence")):
            frappe.throw("Operator Confirmed offline policy requires authority reference and evidence.")
