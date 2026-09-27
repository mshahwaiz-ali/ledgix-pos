# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from ledgix_saas.services.stock import (
    cancel_reference_movements,
    post_purchase_movements,
    rebuild_item_average_cost,
)


class LedgixPurchase(Document):

    def validate(self):
        if self.docstatus == 0:
            self.status = "Draft"
        self.calculate_totals()

        from ledgix_saas.api.stock_identity import normalize_purchase_serials, validate_purchase_serial_numbers
        normalize_purchase_serials(self)
        validate_purchase_serial_numbers(self)

    def on_submit(self):
        self.status = "Submitted"
        self.db_set("status", "Submitted", update_modified=False)
        post_purchase_movements(self)

        from ledgix_saas.api.stock_identity import create_stock_lots_for_purchase, create_stock_serials_for_purchase
        create_stock_lots_for_purchase(self)
        create_stock_serials_for_purchase(self)

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

        from ledgix_saas.api.stock_identity import reverse_purchase_lots, reverse_purchase_serials
        reverse_purchase_lots(self)
        reverse_purchase_serials(self)

        # Cancelling each submitted Stock Movement reverses quantity and rebuilds
        # moving-average valuation from the remaining movement ledger.
        cancel_reference_movements("Ledgix Purchase", self.name)

    def calculate_totals(self):
        total_amount = 0
        total_profit = 0
        for row in self.items:
            row.amount = flt(row.quantity) * flt(row.rate)
            total_amount += flt(row.amount)
            if hasattr(row, "item_total_profit"):
                total_profit += flt(row.item_total_profit)
        self.total_amount = total_amount
        self.total_profit = total_profit

    def create_stock_movements(self):
        # Compatibility wrapper for existing callers; authority lives in services.stock.
        post_purchase_movements(self)

    def cancel_stock_movements(self):
        cancel_reference_movements("Ledgix Purchase", self.name)

    def recalculate_item_average_costs(self):
        """Compatibility wrapper around the authoritative stock-ledger replay."""
        for item_name in sorted({row.item for row in self.items if row.item}):
            rebuild_item_average_cost(item_name)
