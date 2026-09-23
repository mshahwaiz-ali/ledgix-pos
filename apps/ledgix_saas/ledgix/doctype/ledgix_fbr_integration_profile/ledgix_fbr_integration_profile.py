from __future__ import annotations

import frappe
from frappe.model.document import Document


class LedgixFBRIntegrationProfile(Document):
    def validate(self):
        if not self.company or not frappe.db.exists("Company", self.company):
            frappe.throw("Select a valid ERPNext Company for the FBR Integration Profile.")

        if self.mode != "Production":
            self.production_post_armed = 0

        if self.mode == "Paused" and not str(self.pause_reason or "").strip():
            frappe.throw("Pause Reason is required when the FBR profile is Paused.")
