# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from ledgix_saas.api.taxation import validate_item_tax_profile_hs_code


class LedgixItemTaxProfile(Document):
	def validate(self):
		validate_item_tax_profile_hs_code(self)
