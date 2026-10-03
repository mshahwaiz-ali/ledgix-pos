from __future__ import annotations

import math

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

        if cint(self.active) and not cint(self.needs_review):
            self.hs_code = str(self.hs_code or "").strip()
            if not self.hs_code or len(self.hs_code) > 8:
                frappe.throw("Reviewed Federal V1 mappings require an HS / PCT code of at most 8 characters.")
            if self.tax_basis not in ("Transaction Value", "Notified Retail Price"):
                frappe.throw("Select a supported Federal V1 Tax Basis.")

        if self.tax_basis == "Notified Retail Price" and (not math.isfinite(flt(self.notified_retail_price)) or flt(self.notified_retail_price) <= 0):
            frappe.throw("Notified Retail Price is required when Tax Basis is Notified Retail Price.")
