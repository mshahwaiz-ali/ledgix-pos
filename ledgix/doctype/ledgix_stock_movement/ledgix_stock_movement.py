# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LedgixStockMovement(Document):

    def validate(self):
        if not self.item:
            frappe.throw("Item is required.")
        if flt(self.quantity) <= 0:
            frappe.throw("Movement quantity must be greater than zero.")
        if self.movement_type not in {"IN", "OUT", "ADJUSTMENT"}:
            frappe.throw(f"Invalid movement type: {self.movement_type}")
        if self.valuation_rate is not None and flt(self.valuation_rate) < 0:
            frappe.throw("Valuation Rate cannot be negative.")

        # Server-created V2 movements pass an explicit valuation snapshot. For a
        # maintenance-created movement, preserve the current average rather than
        # letting a blank valuation silently become an unknown receipt cost.
        if self.valuation_rate is None and self.item:
            self.valuation_rate = flt(
                frappe.db.get_value("Ledgix Item", self.item, "cost_price") or 0
            )

    def before_insert(self):
        if not self.movement_date:
            self.movement_date = frappe.utils.now_datetime()

    def on_submit(self):
        self.update_stock()

    def on_cancel(self):
        if self.movement_type == "ADJUSTMENT":
            frappe.throw(
                "Stock Adjustment cannot be cancelled safely because previous quantity snapshot is not stored. Create a corrective adjustment instead."
            )

        self.update_stock(reverse=True)

        # Cancelling an earlier OUT or IN can change the quantity base used by
        # later receipts. Replay the remaining ledger rather than attempting an
        # unsafe algebraic reversal of the latest average cost.
        from ledgix_saas.services.stock import rebuild_item_average_cost
        rebuild_item_average_cost(self.item, exclude_movement=self.name)

    def update_stock(self, reverse=False):
        from ledgix_saas.api.stock_identity import get_locked_current_stock

        item_doc = frappe.get_doc("Ledgix Item", self.item)
        quantity = flt(self.quantity)
        current_stock = get_locked_current_stock(self.item)

        if reverse:
            if self.movement_type == "IN":
                if quantity > current_stock:
                    frappe.throw(
                        f"Cannot cancel stock IN for {self.item}. Current stock is {current_stock:g}, required reversal is {quantity:g}."
                    )
                item_doc.current_stock = current_stock - quantity
            elif self.movement_type == "OUT":
                item_doc.current_stock = current_stock + quantity
        else:
            if self.movement_type == "IN":
                valuation_rate = max(flt(self.valuation_rate), 0)
                new_stock = current_stock + quantity
                old_cost = flt(item_doc.cost_price)
                item_doc.cost_price = (
                    ((current_stock * old_cost) + (quantity * valuation_rate)) / new_stock
                    if new_stock > 0
                    else valuation_rate
                )
                item_doc.current_stock = new_stock
            elif self.movement_type == "OUT":
                if quantity > current_stock:
                    frappe.throw(
                        f"Stock movement would make {self.item} negative. Available stock: {current_stock:g}."
                    )
                item_doc.current_stock = current_stock - quantity
            elif self.movement_type == "ADJUSTMENT":
                item_doc.current_stock = quantity
                if self.valuation_rate is not None:
                    item_doc.cost_price = max(flt(self.valuation_rate), 0)

        item_doc.update_stock_status()
        item_doc.flags.allow_stock_update = True
        item_doc.flags.allow_cost_update = True
        item_doc.save(ignore_permissions=True)
