# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LedgixStockSerial(Document):
    def validate(self):
        if not self.serial_no:
            frappe.throw("Serial Number is required.")

        if not self.item:
            frappe.throw("Item is required.")

        valid_statuses = ("Available", "Sold", "Returned", "Cancelled")
        if self.status not in valid_statuses:
            frappe.throw(f"Invalid stock serial status: {self.status}")

        duplicate = frappe.db.exists(
            "Ledgix Stock Serial",
            {
                "serial_no": self.serial_no,
                "name": ["!=", self.name],
            },
        )
        if duplicate:
            frappe.throw(f"Serial number {self.serial_no} already exists.")
