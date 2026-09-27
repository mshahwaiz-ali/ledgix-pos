# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LedgixItem(Document):

    def before_insert(self):
        self.current_stock = 0
        self._validate_non_negative_inputs()
        self.update_stock_status()

    def after_insert(self):
        opening = flt(self.opening_stock)
        if opening > 0:
            from ledgix_saas.api.stock_ops import record_opening_stock
            record_opening_stock(self.name, opening)

    def validate(self):
        self._validate_non_negative_inputs()

        if not self.is_new():
            previous = frappe.db.get_value(
                "Ledgix Item",
                self.name,
                ["current_stock", "opening_stock", "cost_price"],
                as_dict=True,
            ) or {}

            # Quantity is owned by the stock ledger. Opening quantity is a
            # create-time seed and cannot be replayed by editing the Item master.
            if not getattr(self.flags, "allow_stock_update", False):
                self.current_stock = flt(previous.get("current_stock"))
            self.opening_stock = flt(previous.get("opening_stock"))

            # Moving-average cost is also stock-ledger owned after creation.
            if not getattr(self.flags, "allow_cost_update", False):
                self.cost_price = flt(previous.get("cost_price"))

        self.calculate_profit()
        self.update_stock_status()

    def _validate_non_negative_inputs(self):
        for fieldname, label in (
            ("opening_stock", "Opening Stock"),
            ("minimum_stock", "Minimum Stock"),
            ("cost_price", "Cost Price"),
            ("selling_price", "Fallback Selling Price"),
        ):
            if flt(self.get(fieldname)) < 0:
                frappe.throw(f"{label} cannot be negative.")

    def calculate_profit(self):
        cost = flt(self.cost_price)
        selling = flt(self.selling_price)
        self.profit_amount = selling - cost
        self.profit_margin = ((selling - cost) / cost) * 100 if cost > 0 else 0

    def update_stock_status(self):
        current_stock = flt(self.current_stock)
        minimum_stock = flt(self.minimum_stock)

        if current_stock <= 0:
            self.stock_status = "Out of Stock"
        elif current_stock <= minimum_stock:
            self.stock_status = "Low Stock"
        else:
            self.stock_status = "In Stock"
