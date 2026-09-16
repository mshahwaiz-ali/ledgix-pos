# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from ledgix_saas.api.taxation import validate_item_tax_profile_hs_code


class LedgixItemTaxProfile(Document):
	def validate(self):
		# Phase 3 moves the target relationship to ERPNext Item while retaining the
		# old Ledgix Item link only as a migration compatibility reference. Existing
		# profiles therefore remain valid, and new ERPNext-native profiles do not
		# need a duplicate Ledgix Item master.
		if not self.erpnext_item and not self.item:
			frappe.throw("Select an ERPNext Item or a legacy Ledgix Item for this FBR profile.")
		validate_item_tax_profile_hs_code(self)
