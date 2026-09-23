from __future__ import annotations

import frappe
from frappe.model.document import Document


class LedgixFBRReferenceData(Document):
    def validate(self):
        duplicate = frappe.db.exists(
            "Ledgix FBR Reference Data",
            {
                "reference_type": self.reference_type,
                "fbr_id": self.fbr_id,
                "protocol_version": self.protocol_version or "",
                "name": ["!=", self.name or ""],
            },
        )
        if duplicate:
            frappe.throw(
                f"FBR Reference Data already exists for {self.reference_type} / "
                f"{self.fbr_id} / {self.protocol_version or ''}."
            )
