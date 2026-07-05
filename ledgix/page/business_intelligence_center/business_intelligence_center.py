# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def search_business_intelligence_entities(query=None, tracking_type="All", limit=20):
	"""Delegate to secured API implementation."""
	from ledgix_saas.api.business_intelligence import search_business_intelligence_entities as _search

	return _search(query=query, tracking_type=tracking_type, limit=limit)
