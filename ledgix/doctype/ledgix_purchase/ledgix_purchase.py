# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from ledgix_saas.services.stock import (
    cancel_reference_movements,
    post_purchase_movements,
    update_purchase_average_costs,
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
        update_purchase_average_costs(self)

        from ledgix_saas.api.stock_identity import create_stock_lots_for_purchase, create_stock_serials_for_purchase
        create_stock_lots_for_purchase(self)
        create_stock_serials_for_purchase(self)

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

        from ledgix_saas.api.stock_identity import reverse_purchase_lots, reverse_purchase_serials
        reverse_purchase_lots(self)
        reverse_purchase_serials(self)

        cancel_reference_movements("Ledgix Purchase", self.name)
        self.recalculate_item_average_costs()

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
        update_purchase_average_costs(self)

    def cancel_stock_movements(self):
        cancel_reference_movements("Ledgix Purchase", self.name)

    def recalculate_item_average_costs(self):
        item_names = sorted({row.item for row in self.items if row.item})
        for item_name in item_names:
            rows = frappe.db.sql("""
                SELECT
                    COALESCE(SUM(pi.quantity), 0) AS total_qty,
                    COALESCE(SUM(pi.quantity * pi.rate), 0) AS total_cost
                FROM `tabLedgix Purchase Item` pi
                INNER JOIN `tabLedgix Purchase` p ON p.name = pi.parent
                WHERE p.docstatus = 1 AND pi.item = %s
            """, (item_name,), as_dict=True)[0]

            total_qty = flt(rows.total_qty)
            item_doc = frappe.get_doc("Ledgix Item", item_name)
            if total_qty > 0:
                item_doc.cost_price = flt(rows.total_cost) / total_qty
            elif flt(item_doc.current_stock) <= 0:
                item_doc.cost_price = 0
            else:
                frappe.logger("ledgix").info(
                    "Skipped resetting cost_price for %s because current stock remains after purchase cancellation.",
                    item_name,
                )
                continue
            item_doc.save(ignore_permissions=True)
