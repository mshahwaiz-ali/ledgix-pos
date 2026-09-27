from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import cint

from ledgix_saas.setup.erpnext_extensions import apply_business_profile_defaults


class LedgixBusinessProfile(Document):
    def validate(self):
        if cint(self.use_profile_defaults):
            apply_business_profile_defaults(self)

    def on_update(self):
        # Product-profile changes affect UX navigation only; DocType permissions
        # remain authoritative. Refresh the profile-aware Cashier landing now so
        # the next Desk load cannot route a non-POS profile into Ledgix POS.
        from ledgix_saas.setup.erpnext_phase11_product_shell import sync_role_home_pages

        sync_role_home_pages()
        frappe.clear_cache()
