import frappe
from frappe.model.document import Document
from fbr_v1.services.authority_evidence import stamp_verification


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
        if self.environment == "Production" and not (self.onboarding_reference and self.onboarding_evidence):
            frappe.throw("Production device requires onboarding reference and evidence.")
        for prefix in ("qr", "signature"):
            stamp_verification(self, prefix + "_verification_status", prefix + "_verification_reference",
                               prefix + "_verification_evidence", prefix + "_verified_at",
                               prefix + "_verified_by", {"Verified"}, context_fields=(
                                   "company", "pos_profile", "pos_id", "environment", "transport_topology",
                                   "software_registration_number", "ims_package_name", "ims_package_version",
                                   "ims_installation_reference", "ims_installation_evidence"))
