from __future__ import annotations

import frappe
from frappe.model.document import Document


class LedgixFBRSandboxCertification(Document):
    def validate(self):
        if not self.integration_profile or not frappe.db.exists(
            "Ledgix FBR Integration Profile", self.integration_profile
        ):
            frappe.throw("Select a valid FBR Integration Profile.")

        profile_company = frappe.db.get_value(
            "Ledgix FBR Integration Profile", self.integration_profile, "company"
        )
        if self.company and self.company != profile_company:
            frappe.throw("Sandbox Certification Company must match its FBR Integration Profile.")
        self.company = profile_company

        if self.status == "Complete":
            required = [row for row in self.scenarios or [] if row.required]
            if not required:
                frappe.throw(
                    "At least one required Sandbox scenario is needed before certification can be Complete."
                )
            incomplete = [
                row.scenario_id
                for row in required
                if row.validate_status != "Validated" or row.post_status != "Submitted"
            ]
            if incomplete:
                frappe.throw(
                    "Required Sandbox scenarios are not complete: " + ", ".join(incomplete)
                )
