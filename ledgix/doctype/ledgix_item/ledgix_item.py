# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LedgixItem(Document):

    def before_insert(self):
        self.current_stock = 0
        self.update_stock_status()

    def after_insert(self):
        opening = flt(self.opening_stock)
        if opening > 0:
            from ledgix_saas.api.stock_ops import record_opening_stock

            record_opening_stock(self.name, opening)

    def validate(self):
        if not self.is_new():
            previous_stock = frappe.db.get_value("Ledgix Item", self.name, "current_stock")
            if flt(self.current_stock) != flt(previous_stock):
                self.current_stock = flt(previous_stock)

        self.calculate_profit()
        self.update_stock_status()

    def calculate_profit(self):
        cost = self.cost_price or 0
        selling = self.selling_price or 0

        self.profit_amount = selling - cost

        if cost > 0:
            self.profit_margin = ((selling - cost) / cost) * 100
        else:
            self.profit_margin = 0

    def update_stock_status(self):

        current_stock = self.current_stock or 0
        minimum_stock = self.minimum_stock or 0

        if current_stock <= 0:
            self.stock_status = "Out of Stock"

        elif current_stock <= minimum_stock:
            self.stock_status = "Low Stock"

        else:
            self.stock_status = "In Stock"