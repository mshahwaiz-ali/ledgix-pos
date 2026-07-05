# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from ledgix_saas.api.api import is_strict_inventory_mode
from ledgix_saas.api.taxation import apply_tax_snapshot_to_sale_doc


class LedgixSale(Document):

    def before_insert(self):
        self.set_invoice_number()

    def validate(self):
        if self.docstatus == 0:
            self.status = "Draft"
        self.validate_stock()
        self.validate_pos_shift()
        self.calculate_totals()
        tax_result = apply_tax_snapshot_to_sale_doc(self)
        for message in (tax_result.get("validation") or {}).get("warnings") or []:
            frappe.msgprint(message, indicator="orange", title="Tax Mapping")
        self.calculate_payments()
        self.validate_payments()

        if is_strict_inventory_mode():
            from ledgix_saas.api.stock_identity import normalize_sale_serials, validate_sale_serial_numbers
            normalize_sale_serials(self)
            validate_sale_serial_numbers(self)

    def validate_pos_shift(self):

        if not self.pos_shift:
            frappe.throw("Please open a POS Shift before creating a sale.")

        shift = frappe.get_doc("Ledgix POS Shift", self.pos_shift)

        if shift.docstatus != 0 or shift.status != "Open":
            frappe.throw("Selected POS Shift is not open. Please open a new shift.")

    def on_submit(self):
        self.status = "Submitted"
        self.db_set("status", "Submitted", update_modified=False)

        if is_strict_inventory_mode():
            self.create_stock_movements()

            from ledgix_saas.api.stock_identity import allocate_sale_fifo, allocate_sale_serials
            allocate_sale_fifo(self)
            allocate_sale_serials(self)

        self.update_pos_shift_cash()
        self.queue_fbr_submission_after_sale_work()

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

        if is_strict_inventory_mode():
            from ledgix_saas.api.stock_identity import reverse_sale_fifo_allocations, reverse_sale_serial_allocations
            reverse_sale_fifo_allocations(self)
            reverse_sale_serial_allocations(self)
            self.cancel_stock_movements()

        self.update_pos_shift_cash()

    def set_invoice_number(self):
        if not self.invoice_number:
            self.invoice_number = frappe.model.naming.make_autoname("INV-.#####")

    def validate_stock(self):
        if not is_strict_inventory_mode():
            return

        for row in self.items:
            from ledgix_saas.api.stock_identity import get_locked_current_stock

            current_stock = get_locked_current_stock(row.item)

            if flt(row.quantity) > current_stock:
                frappe.throw(
                    f"Not enough stock for item {row.item}. Available stock: {current_stock}"
                )

    def calculate_totals(self):
        total_amount = 0
        total_profit = 0

        for row in self.items:
            row.amount = flt(row.quantity) * flt(row.rate)

            row.profit_per_unit = flt(row.rate) - flt(row.cost_price)
            row.item_total_profit = flt(row.profit_per_unit) * flt(row.quantity)

            total_amount += flt(row.amount)
            total_profit += flt(row.item_total_profit)

        self.total_amount = total_amount
        self.total_profit = total_profit


    def get_payable_total(self):
        payable_total = flt(self.grand_total)

        if payable_total > 0:
            return payable_total

        return flt(self.total_amount)


    def calculate_payments(self):
        paid_amount = 0
        payable_total = self.get_payable_total()

        for payment in self.payments:
            paid_amount += flt(payment.amount)

        self.paid_amount = paid_amount
        self.remaining_amount = payable_total - paid_amount
        self.change_amount = 0

        if self.remaining_amount < 0:
            self.change_amount = abs(self.remaining_amount)
            self.remaining_amount = 0


    def validate_payments(self):
        payable_total = self.get_payable_total()

        if flt(self.paid_amount) < payable_total and not flt(getattr(self, "allow_partial_payment", 0)):
            frappe.throw("Paid amount is less than payable total. Partial payment is not enabled for this sale.")

        if flt(self.paid_amount) <= 0:
            frappe.throw("Paid amount is required.")


    # ============================================================
    # POS SHIFT CASH UPDATE
    # ============================================================

    def update_pos_shift_cash(self):

        if not self.pos_shift:
            return

        shift = frappe.get_doc("Ledgix POS Shift", self.pos_shift)

        if shift.docstatus != 0:
            return

        shift.calculate_expected_cash()
        shift.calculate_variance()
        shift.save(ignore_permissions=True)

    def create_stock_movements(self):
        for row in self.items:
            movement = frappe.new_doc("Ledgix Stock Movement")

            movement.item = row.item
            movement.quantity = row.quantity
            movement.rate = row.cost_price
            movement.movement_type = "OUT"

            movement.reference_doctype = "Ledgix Sale"
            movement.reference_name = self.name

            from ledgix_saas.api.stock_ops import apply_movement_source

            apply_movement_source(movement, "Sale")

            movement.insert(ignore_permissions=True)
            movement.submit()

    def cancel_stock_movements(self):
        movements = frappe.get_all(
            "Ledgix Stock Movement",
            filters={
                "reference_doctype": "Ledgix Sale",
                "reference_name": self.name,
                "docstatus": 1
            },
            pluck="name"
        )

        for movement_name in movements:
            movement = frappe.get_doc("Ledgix Stock Movement", movement_name)
            movement.cancel()

    def queue_fbr_submission_after_sale_work(self):
        from ledgix_saas.api.fbr_payload import _validate_sale_fbr_readiness_internal
        from ledgix_saas.api.fbr_settings import get_fbr_settings_internal, should_submit_on_sale_submit
        from ledgix_saas.api.fbr_submission import queue_sale_for_fbr

        settings = get_fbr_settings_internal()
        if (
            settings.get("block_sale_if_fbr_fails")
            and settings.get("mode") == "Production"
            and should_submit_on_sale_submit()
        ):
            readiness = _validate_sale_fbr_readiness_internal(self.name)
            if not readiness.get("valid"):
                frappe.throw(
                    "FBR readiness failed: "
                    + "; ".join(readiness.get("errors") or ["Sale is not ready for FBR submission."])
                )

        try:
            result = queue_sale_for_fbr(self.name, reason="Sale submitted")
            if isinstance(result, dict) and result.get("status") == "Failed":
                frappe.log_error(
                    result.get("reason") or result.get("error_message") or "FBR queue failed",
                    f"Ledgix FBR queue failed for {self.name}",
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Ledgix FBR queue failed for {self.name}")
            try:
                from ledgix_saas.api.fbr_submission import mark_sale_fbr_status

                mark_sale_fbr_status(
                    self.name,
                    "Failed",
                    error_message="FBR queue failed after sale submit. Retry from Tax Center.",
                )
            except Exception:
                pass
