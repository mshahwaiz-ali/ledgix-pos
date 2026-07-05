# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class LedgixSalesReturn(Document):

    def validate(self):
        self.validate_return_quantities()
        self.enforce_original_sale_item_financials()
        self.calculate_totals()
        self.apply_return_tax_snapshot()

        if self.original_sale_has_stock_impact():
            from ledgix_saas.api.stock_identity import normalize_sales_return_serials, validate_sales_return_serial_numbers
            normalize_sales_return_serials(self)
            validate_sales_return_serial_numbers(self)

    def on_submit(self):
        if self.original_sale_has_stock_impact():
            self.create_stock_movements()

            from ledgix_saas.api.stock_identity import restore_sale_return_fifo_allocations, restore_sales_return_serials
            restore_sale_return_fifo_allocations(self)
            restore_sales_return_serials(self)

        self.queue_fbr_submission_after_return_work()

    def on_cancel(self):
        self.cancel_stock_movements()

        if self.original_sale_has_stock_impact():
            from ledgix_saas.api.stock_identity import reverse_sales_return_fifo_allocations, reverse_sales_return_serials
            reverse_sales_return_fifo_allocations(self)
            reverse_sales_return_serials(self)

    def validate_return_quantities(self):

        if not self.original_sale:
            return

        original_sale = frappe.get_doc("Ledgix Sale", self.original_sale)

        sold_qty_by_row = {}
        sold_item_by_row = {}
        sold_qty_by_item = {}

        for row in original_sale.items:
            sold_qty_by_row[row.name] = flt(row.quantity)
            sold_item_by_row[row.name] = row.item
            sold_qty_by_item[row.item] = flt(sold_qty_by_item.get(row.item)) + flt(row.quantity)

        for row in self.items:
            original_sale_item_row = getattr(row, "original_sale_item_row", None)

            if original_sale_item_row:
                if original_sale_item_row not in sold_qty_by_row:
                    frappe.throw("Return row does not belong to the original sale.")

                if row.item != sold_item_by_row.get(original_sale_item_row):
                    frappe.throw("Return item does not match the original sale row.")

                already_returned_qty = frappe.db.sql("""
                    SELECT COALESCE(SUM(ri.quantity), 0)
                    FROM `tabLedgix Sales Return Item` ri
                    INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
                    WHERE r.original_sale = %s
                      AND r.docstatus = 1
                      AND (
                          ri.original_sale_item_row = %s
                          OR (ri.item = %s AND (ri.original_sale_item_row IS NULL OR ri.original_sale_item_row = ''))
                      )
                      AND r.name != %s
                """, (self.original_sale, original_sale_item_row, row.item, self.name))[0][0]
                sold_qty = sold_qty_by_row.get(original_sale_item_row, 0)
            else:
                already_returned_qty = frappe.db.sql("""
                    SELECT COALESCE(SUM(ri.quantity), 0)
                    FROM `tabLedgix Sales Return Item` ri
                    INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
                    WHERE r.original_sale = %s
                      AND r.docstatus = 1
                      AND ri.item = %s
                      AND (ri.original_sale_item_row IS NULL OR ri.original_sale_item_row = '')
                      AND r.name != %s
                """, (self.original_sale, row.item, self.name))[0][0]
                sold_qty = sold_qty_by_item.get(row.item, 0)

            allowed_qty = flt(sold_qty) - flt(already_returned_qty)

            if flt(row.quantity) > allowed_qty:
                frappe.throw(
                    f"Return quantity for item {row.item} cannot exceed remaining returnable quantity ({allowed_qty})."
                )

    def enforce_original_sale_item_financials(self):
        if not self.original_sale:
            return

        original_sale = frappe.get_doc("Ledgix Sale", self.original_sale)
        original_rows = {row.name: row for row in original_sale.items}

        for row in self.items:
            original_sale_item_row = getattr(row, "original_sale_item_row", None)
            if not original_sale_item_row:
                continue

            original_row = original_rows.get(original_sale_item_row)
            if not original_row:
                frappe.throw("Return row does not belong to the original sale.")

            if row.item != original_row.item:
                frappe.throw("Return item does not match the original sale row.")

            row.rate = flt(getattr(original_row, "rate", 0))

            if hasattr(row, "cost_price"):
                row.cost_price = flt(getattr(original_row, "cost_price", 0))
            if hasattr(row, "profit_per_unit"):
                row.profit_per_unit = flt(getattr(original_row, "profit_per_unit", 0))
            if hasattr(row, "item_total_profit"):
                row.item_total_profit = flt(row.quantity) * flt(getattr(original_row, "profit_per_unit", 0))

    def original_sale_has_stock_impact(self):
        if not self.original_sale:
            return False

        return bool(frappe.db.exists(
            "Ledgix Stock Movement",
            {
                "reference_doctype": "Ledgix Sale",
                "reference_name": self.original_sale,
                "docstatus": 1
            }
        ))

    def create_stock_movements(self):

        if not self.original_sale:
            return

        if not self.original_sale_has_stock_impact():
            return

        for row in self.items:
            existing_movement = frappe.db.exists(
                "Ledgix Stock Movement",
                {
                    "reference_doctype": "Ledgix Sales Return",
                    "reference_name": self.name,
                    "item": row.item,
                    "movement_type": "IN",
                    "quantity": row.quantity,
                    "docstatus": ["!=", 2]
                }
            )

            if existing_movement:
                continue

            movement = frappe.new_doc("Ledgix Stock Movement")

            movement.item = row.item
            movement.quantity = row.quantity
            movement.movement_type = "IN"
            movement.reference_doctype = "Ledgix Sales Return"
            movement.reference_name = self.name
            movement.reference_note = f"Return against {self.original_sale}"

            from ledgix_saas.api.stock_ops import apply_movement_source

            apply_movement_source(movement, "Return")

            movement.insert(ignore_permissions=True)
            movement.submit()

    def cancel_stock_movements(self):

        movements = frappe.get_all(
            "Ledgix Stock Movement",
            filters={
                "reference_doctype": "Ledgix Sales Return",
                "reference_name": self.name,
                "docstatus": 1
            },
            pluck="name"
        )

        for movement_name in movements:
            movement = frappe.get_doc("Ledgix Stock Movement", movement_name)
            movement.cancel()

    def calculate_totals(self):

        total_amount = 0
        total_profit_reversal = 0

        for row in self.items:

            row.amount = flt(row.quantity) * flt(row.rate)

            total_amount += flt(row.amount)
            total_profit_reversal += flt(row.item_total_profit)

        self.total_amount = total_amount
        self.total_profit_reversal = total_profit_reversal


    # ============================================================
    # TAX SNAPSHOT REVERSAL
    # ============================================================

    def apply_return_tax_snapshot(self):
        self.set("tax_details", [])

        self.tax_amount = 0
        self.grand_total = flt(self.total_amount)

        if not self.original_sale:
            return

        original_sale = frappe.get_doc("Ledgix Sale", self.original_sale)

        if not getattr(original_sale, "tax_details", None):
            return

        original_qty_map = {}
        original_qty_by_row = {}
        for sale_item in original_sale.items:
            original_qty_map[sale_item.item] = original_qty_map.get(sale_item.item, 0) + flt(sale_item.quantity)
            original_qty_by_row[sale_item.name] = flt(sale_item.quantity)

        total_return_tax = 0
        inclusive_mode = False

        for return_item in self.items:
            returned_qty = flt(return_item.quantity)

            original_sale_item_row = getattr(return_item, "original_sale_item_row", None)
            if original_sale_item_row:
                original_qty = flt(original_qty_by_row.get(original_sale_item_row))
                matching_tax_rows = [
                    tax_row for tax_row in original_sale.tax_details
                    if getattr(tax_row, "sale_item_row", None) == original_sale_item_row
                ]
            else:
                original_qty = flt(original_qty_map.get(return_item.item))
                matching_tax_rows = [
                    tax_row for tax_row in original_sale.tax_details
                    if tax_row.item == return_item.item
                ]

            if not original_qty or not returned_qty:
                continue

            return_ratio = returned_qty / original_qty

            for tax_row in matching_tax_rows:
                price_includes_tax = int(flt(getattr(tax_row, "price_includes_tax", 0)))

                if price_includes_tax:
                    inclusive_mode = True

                returned_gross_amount = flt(getattr(tax_row, "gross_amount", 0)) * return_ratio
                returned_taxable_amount = flt(tax_row.taxable_amount) * return_ratio
                returned_tax_amount = flt(tax_row.tax_amount) * return_ratio
                returned_net_amount = flt(tax_row.net_amount) * return_ratio

                total_return_tax += returned_tax_amount

                self.append("tax_details", {
                    "sales_return": self.name,
                    "original_sale": self.original_sale,
                    "original_sale_item_row": getattr(tax_row, "sale_item_row", None),
                    "item": return_item.item,
                    "returned_qty": returned_qty,
                    "original_tax_rate": flt(tax_row.tax_rate),

                    "gross_amount": flt(returned_gross_amount, 2),
                    "taxable_amount": flt(returned_taxable_amount, 2),
                    "tax_rate": flt(tax_row.tax_rate),
                    "tax_amount": flt(returned_tax_amount, 2),
                    "net_amount": flt(returned_net_amount, 2),
                    "price_includes_tax": price_includes_tax,

                    "returned_taxable_amount": flt(returned_taxable_amount, 2),
                    "returned_tax_amount": flt(returned_tax_amount, 2),

                    "tax_category": tax_row.tax_category,
                    "hs_code": getattr(tax_row, "hs_code", None),
                    "uom_for_fbr": getattr(tax_row, "uom_for_fbr", None),
                    "sales_type": getattr(tax_row, "sales_type", None),
                    "scenario_id": getattr(tax_row, "scenario_id", None),
                    "sro_schedule_number": getattr(tax_row, "sro_schedule_number", None),
                    "sro_item_serial_number": getattr(tax_row, "sro_item_serial_number", None),
                })

        self.tax_amount = flt(total_return_tax, 2)

        if inclusive_mode:
            self.grand_total = flt(self.total_amount, 2)
        else:
            self.grand_total = flt(flt(self.total_amount) + flt(total_return_tax), 2)

    def queue_fbr_submission_after_return_work(self):
        from ledgix_saas.api.fbr_submission import queue_return_for_fbr

        try:
            queue_return_for_fbr(self.name, reason="Sales return submitted")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Ledgix FBR queue failed for return {self.name}")
