from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class LedgixFBRIntegrationProfile(Document):
    def validate(self):
        if not self.company or not frappe.db.exists("Company", self.company):
            frappe.throw("Select a valid ERPNext Company for the FBR Integration Profile.")

        if self.mode != "Production":
            self.production_post_armed = 0

        if self.mode == "Paused" and not str(self.pause_reason or "").strip():
            frappe.throw("Pause Reason is required when the FBR profile is Paused.")

        offline_policy = str(self.offline_policy or "Disabled").strip()
        if offline_policy not in {"Disabled", "Operator Confirmed"}:
            frappe.throw("Known Offline Policy must be Disabled or Operator Confirmed.")
        if offline_policy == "Operator Confirmed" and cint(
            self.offline_upload_window_hours
        ) <= 0:
            frappe.throw(
                "Offline Upload Window (Hours) must be configured from the current "
                "client/provider rule before Known Offline Policy can be enabled."
            )
