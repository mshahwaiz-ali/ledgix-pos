from __future__ import annotations

from frappe.model.document import Document
from frappe.utils import cint

from ledgix_saas.setup.erpnext_extensions import apply_business_profile_defaults


class LedgixBusinessProfile(Document):
    def validate(self):
        if cint(self.use_profile_defaults):
            apply_business_profile_defaults(self)
