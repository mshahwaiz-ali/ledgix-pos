# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


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
        self.create_stock_movements()

        from ledgix_saas.api.stock_identity import create_stock_lots_for_purchase, create_stock_serials_for_purchase
        create_stock_lots_for_purchase(self)
        create_stock_serials_for_purchase(self)

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

        from ledgix_saas.api.stock_identity import reverse_purchase_lots, reverse_purchase_serials
        reverse_purchase_lots(self)
        reverse_purchase_serials(self)

        self.cancel_stock_movements()
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
        stock_meta = frappe.get_meta("Ledgix Stock Movement")

        for row in self.items:
            movement = frappe.new_doc("Ledgix Stock Movement")
            movement.item = row.item
            movement.movement_type = "IN"
            movement.quantity = flt(row.quantity)
            movement.movement_date = self.purchase_date or now_datetime()

            if stock_meta.has_field("reference_doctype"):
                movement.reference_doctype = self.doctype

            if stock_meta.has_field("reference_name"):
                movement.reference_name = self.name

            from ledgix_saas.api.stock_ops import apply_movement_source

            apply_movement_source(movement, "Purchase")

            movement.insert()
            movement.submit()
            item_doc = frappe.get_doc("Ledgix Item", row.item)

            old_qty = flt(item_doc.current_stock) - flt(row.quantity)
            old_cost = flt(item_doc.cost_price)

            new_qty = flt(row.quantity)
            new_rate = flt(row.rate)

            if old_qty <= 0:
                average_cost = new_rate
            else:
                average_cost = ((old_qty * old_cost) + (new_qty * new_rate)) / (old_qty + new_qty)

            item_doc.cost_price = average_cost
            item_doc.save(ignore_permissions=True)
            

    def cancel_stock_movements(self):
        stock_meta = frappe.get_meta("Ledgix Stock Movement")

        if not (
            stock_meta.has_field("reference_doctype")
            and stock_meta.has_field("reference_name")
        ):
            return

        movements = frappe.get_all(
            "Ledgix Stock Movement",
            filters={
                "reference_doctype": self.doctype,
                "reference_name": self.name,
                "docstatus": 1
            },
            pluck="name"
        )

        for movement_name in movements:
            movement = frappe.get_doc("Ledgix Stock Movement", movement_name)
            movement.cancel()

    def recalculate_item_average_costs(self):
        item_names = sorted({row.item for row in self.items if row.item})

        for item_name in item_names:
            rows = frappe.db.sql("""
                SELECT
                    COALESCE(SUM(pi.quantity), 0) AS total_qty,
                    COALESCE(SUM(pi.quantity * pi.rate), 0) AS total_cost
                FROM `tabLedgix Purchase Item` pi
                INNER JOIN `tabLedgix Purchase` p ON p.name = pi.parent
                WHERE
                    p.docstatus = 1
                    AND pi.item = %s
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
