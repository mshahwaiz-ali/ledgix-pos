from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class LedgixFBRTaxComponentMapping(Document):
    def validate(self):
        if not self.company or not frappe.db.exists("Company", self.company):
            frappe.throw("Select a valid ERPNext Company.")

        account = frappe.db.get_value(
            "Account",
            self.account_head,
            ["company", "is_group", "disabled"],
            as_dict=True,
        )
        if not account:
            frappe.throw("Select a valid ERPNext tax Account.")
        if account.company != self.company:
            frappe.throw("FBR Tax Component Mapping cannot use an Account from another Company.")
        if cint(account.is_group) or cint(account.disabled):
            frappe.throw("FBR Tax Component Mapping requires an enabled ledger Account.")

        if cint(self.active):
            duplicate = frappe.db.exists(
                "Ledgix FBR Tax Component Mapping",
                {
                    "company": self.company,
                    "account_head": self.account_head,
                    "active": 1,
                    "name": ["!=", self.name or ""],
                },
            )
            if duplicate:
                frappe.throw(
                    f"An active FBR component mapping already exists for Account {self.account_head}."
                )
