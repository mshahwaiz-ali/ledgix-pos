from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class LedgixFBRItemMapping(Document):
    def validate(self):
        if not self.company or not frappe.db.exists("Company", self.company):
            frappe.throw("Select a valid ERPNext Company.")
        if not self.erpnext_item or not frappe.db.exists("Item", self.erpnext_item):
            frappe.throw("Select a valid ERPNext Item.")

        if cint(self.active):
            duplicate = frappe.db.exists(
                "Ledgix FBR Item Mapping",
                {
                    "company": self.company,
                    "erpnext_item": self.erpnext_item,
                    "active": 1,
                    "name": ["!=", self.name or ""],
                },
            )
            if duplicate:
                frappe.throw(
                    f"An active FBR Item Mapping already exists for {self.erpnext_item} in {self.company}."
                )

        if self.tax_basis == "Notified Retail Price" and flt(self.notified_retail_price) <= 0:
            frappe.throw("Notified Retail Price is required when Tax Basis is Notified Retail Price.")
