from __future__ import annotations

import math
from datetime import date

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime

CONFIG_WRITE_ROLES = {"System Manager", "Ledgix Admin", "Accounts Manager"}
MATERIAL_FIELDS = ("company", "erpnext_item", "hs_code", "tax_basis",
                   "notified_retail_price", "effective_from", "effective_to")


def periods_overlap(left, right):
    def bounds(row):
        return (getdate(row.get("effective_from")) if row.get("effective_from") else date.min,
                getdate(row.get("effective_to")) if row.get("effective_to") else date.max)
    start, end = bounds(left)
    other_start, other_end = bounds(right)
    return start <= other_end and other_start <= end


def _material_value(doc, field):
    value = doc.get(field)
    if field in ("effective_from", "effective_to"):
        return getdate(value) if value else None
    if field == "notified_retail_price":
        return flt(value)
    return str(value or "").strip()


def apply_review(doc):
    previous = doc.get_doc_before_save()
    if previous is None:
        doc.needs_review = 1
        doc.last_reviewed_at = doc.reviewed_by = None
    elif not cint(previous.get("needs_review")) and any(
            _material_value(doc, field) != _material_value(previous, field) for field in MATERIAL_FIELDS):
        doc.needs_review = 1
        doc.last_reviewed_at = doc.reviewed_by = None
    elif cint(previous.get("needs_review")) and not cint(doc.get("needs_review")):
        if not CONFIG_WRITE_ROLES.intersection(frappe.get_roles(frappe.session.user)):
            frappe.throw("FBR configuration write authority is required to review mappings.", frappe.PermissionError)
        doc.last_reviewed_at = now_datetime()
        doc.reviewed_by = frappe.session.user
    elif cint(doc.get("needs_review")):
        doc.last_reviewed_at = doc.reviewed_by = None
    else:
        # Approval metadata is server-owned, including on non-material saves.
        doc.last_reviewed_at = previous.get("last_reviewed_at")
        doc.reviewed_by = previous.get("reviewed_by")


class LedgixFBRItemMapping(Document):
    def validate(self):
        if not self.company or not frappe.db.exists("Company", self.company):
            frappe.throw("Select a valid ERPNext Company.")
        if not self.erpnext_item or not frappe.db.exists("Item", self.erpnext_item):
            frappe.throw("Select a valid ERPNext Item.")
        if self.get("effective_from") and self.get("effective_to") and getdate(self.effective_from) > getdate(self.effective_to):
            frappe.throw("Effective From must be on or before Effective To.")
        if cint(self.active):
            if cint(frappe.db.get_value("Item", self.erpnext_item, "has_variants")):
                frappe.throw("Active FBR mappings require a transaction-capable Item; variant templates cannot be mapped.")
            others = frappe.get_all("Ledgix FBR Item Mapping",
                filters={"company": self.company, "erpnext_item": self.erpnext_item,
                         "active": 1, "name": ["!=", self.name or ""]},
                fields=["name", "effective_from", "effective_to"], limit_page_length=0)
            if any(periods_overlap(self, row) for row in others):
                frappe.throw(f"Active FBR Item Mapping periods overlap for {self.erpnext_item} in {self.company}.")

        apply_review(self)
        if cint(self.active) and not cint(self.needs_review):
            self.hs_code = str(self.hs_code or "").strip()
            if not self.hs_code or len(self.hs_code) > 8:
                frappe.throw("Reviewed Federal V1 mappings require an HS / PCT code of at most 8 characters.")
            if self.tax_basis not in ("Transaction Value", "Notified Retail Price"):
                frappe.throw("Select a supported Federal V1 Tax Basis.")
        if self.tax_basis == "Notified Retail Price" and (not math.isfinite(flt(self.notified_retail_price)) or flt(self.notified_retail_price) <= 0):
            frappe.throw("Notified Retail Price is required when Tax Basis is Notified Retail Price.")
