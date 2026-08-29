# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

from ledgix_saas.services.receivables import get_customer_receivables, refresh_customer_credit_summary
from ledgix_saas.services.sales import apply_customer_snapshot, apply_item_snapshots, apply_seller_snapshot
from ledgix_saas.services.stock import cancel_reference_movements, post_sale_movements
from ledgix_saas.services.tax import apply_sale_tax_snapshot


class LedgixSale(Document):

    def before_insert(self):
        self.set_invoice_number()

    def validate(self):
        if self.docstatus == 0:
            self.status = "Draft"
            apply_customer_snapshot(self)
            apply_seller_snapshot(self)
            apply_item_snapshots(self)

        self.validate_channel_requirements()
        self.validate_stock()
        self.validate_pos_shift()
        self.calculate_totals()

        tax_result = apply_sale_tax_snapshot(self)
        for message in (tax_result.get("validation") or {}).get("warnings") or []:
            frappe.msgprint(message, indicator="orange", title="Tax Mapping")

        self.validate_tender_methods()
        self.calculate_payments()
        self.validate_payments()
        self.validate_credit()

        from ledgix_saas.api.stock_identity import normalize_sale_serials, validate_sale_serial_numbers
        normalize_sale_serials(self)
        validate_sale_serial_numbers(self)

    def before_submit(self):
        # Freeze legal seller and customer-facing item identity at the final posting
        # boundary so later master-data edits cannot change historical reprints.
        apply_seller_snapshot(self)
        apply_item_snapshots(self)

    def validate_channel_requirements(self):
        if self.sale_channel not in ("Retail", "B2B"):
            frappe.throw("Sale Channel must be Retail or B2B.")
        if self.sale_channel == "B2B" and self.customer == "Walk-in Customer":
            frappe.throw("B2B sales require a named business customer.")

    def validate_pos_shift(self):
        # Retail checkout is shift-bound. B2B back-office invoices may be created
        # without a register shift, while a B2B sale created from POS may still carry one.
        if self.sale_channel == "B2B" and not self.pos_shift:
            return

        if not self.pos_shift:
            frappe.throw("Please open a POS Shift before creating a retail sale.")

        shift = frappe.get_doc("Ledgix POS Shift", self.pos_shift)
        if shift.docstatus != 0 or shift.status != "Open":
            frappe.throw("Selected POS Shift is not open. Please open a new shift.")

    def on_submit(self):
        self.status = "Submitted"
        self.db_set("status", "Submitted", update_modified=False)

        post_sale_movements(self)

        from ledgix_saas.api.stock_identity import allocate_sale_fifo, allocate_sale_serials
        allocate_sale_fifo(self)
        allocate_sale_serials(self)

        self.post_legacy_tenders_to_payment_ledger()
        self.update_pos_shift_cash()
        refresh_customer_credit_summary(self.customer)
        self.queue_fbr_submission_after_sale_work()

    def before_cancel(self):
        payment_activity = frappe.db.sql(
            """
            SELECT pa.name
            FROM `tabLedgix Payment Allocation` pa
            INNER JOIN `tabLedgix Payment` p ON p.name = pa.parent
            WHERE pa.reference_doctype = 'Ledgix Sale'
              AND pa.reference_name = %s
              AND p.docstatus = 1
            LIMIT 1
            """,
            (self.name,),
        )
        if payment_activity:
            frappe.throw(
                "Sales with posted payment activity cannot be cancelled directly. "
                "Use Sales Return/Credit for the sale correction and the Payment reversal/refund workflow for money corrections."
            )

    def on_cancel(self):
        self.status = "Cancelled"
        self.db_set("status", "Cancelled", update_modified=False)

        from ledgix_saas.api.stock_identity import reverse_sale_fifo_allocations, reverse_sale_serial_allocations
        reverse_sale_fifo_allocations(self)
        reverse_sale_serial_allocations(self)
        cancel_reference_movements("Ledgix Sale", self.name)

        self.update_pos_shift_cash()
        refresh_customer_credit_summary(self.customer)

    def set_invoice_number(self):
        if not self.invoice_number:
            self.invoice_number = frappe.model.naming.make_autoname("INV-.#####")

    def validate_stock(self):
        for row in self.items:
            from ledgix_saas.api.stock_identity import get_locked_current_stock
            current_stock = get_locked_current_stock(row.item)
            if flt(row.quantity) > current_stock:
                frappe.throw(f"Not enough stock for item {row.item}. Available stock: {current_stock}")

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
        return payable_total if payable_total > 0 else flt(self.total_amount)

    def get_payment_method_meta(self, method):
        row = frappe.db.get_value(
            "Ledgix Payment Method",
            method,
            ["method_type", "enabled", "requires_reference", "allow_change"],
            as_dict=True,
        )
        if not row:
            frappe.throw(
                f"Payment Method {method or ''} is not configured. Run migrate or configure Payment Methods before checkout."
            )
        return row

    def validate_tender_methods(self):
        for tender in self.payments:
            if flt(tender.amount) <= 0:
                frappe.throw("Tender amount must be greater than zero.")

            method = self.get_payment_method_meta(tender.payment_method)
            if not cint(method.enabled):
                frappe.throw(f"Payment Method {tender.payment_method} is disabled.")
            if cint(method.requires_reference) and not (tender.reference_no or "").strip():
                frappe.throw(f"Reference number is required for Payment Method {tender.payment_method}.")

            tender.is_cash_payment = 1 if method.method_type == "Cash" else 0

    def calculate_payments(self):
        paid_amount = sum(flt(payment.amount) for payment in self.payments)
        payable_total = self.get_payable_total()

        self.paid_amount = paid_amount
        self.remaining_amount = max(payable_total - paid_amount, 0)
        self.change_amount = max(paid_amount - payable_total, 0)

        if self.remaining_amount <= 0 and payable_total > 0:
            self.payment_status = "Paid"
        elif paid_amount > 0:
            self.payment_status = "Partial"
        else:
            self.payment_status = "Unpaid"

    def validate_payments(self):
        payable_total = self.get_payable_total()
        paid_amount = flt(self.paid_amount)

        if self.sale_channel == "Retail":
            if paid_amount <= 0:
                frappe.throw("Paid amount is required for a retail sale.")
            if paid_amount < payable_total and not flt(getattr(self, "allow_partial_payment", 0)):
                frappe.throw("Paid amount is less than payable total. Partial payment is not enabled for this sale.")

        if paid_amount <= payable_total + 0.005:
            return

        cash_tenders = []
        non_cash_paid = 0.0
        for tender in self.payments:
            method = self.get_payment_method_meta(tender.payment_method)
            if method.method_type == "Cash":
                cash_tenders.append((tender, method))
            else:
                non_cash_paid += flt(tender.amount)

        if non_cash_paid - payable_total > 0.005:
            frappe.throw("Non-cash tender cannot exceed the payable total.")
        if not cash_tenders:
            frappe.throw("Only cash payment methods can tender more than the payable total and return change.")
        if any(not cint(method.allow_change) for _tender, method in cash_tenders):
            frappe.throw("The selected cash payment method does not allow cash change.")

    def validate_credit(self):
        if self.sale_channel != "B2B" or flt(self.remaining_amount) <= 0:
            return

        credit = get_customer_receivables(self.customer)
        available_credit = flt(credit.get("available_credit"))
        if flt(self.remaining_amount) - available_credit > 0.005:
            frappe.throw(
                f"Customer credit limit exceeded. Available credit: {available_credit:.2f}; "
                f"new receivable: {flt(self.remaining_amount):.2f}."
            )

    def post_legacy_tenders_to_payment_ledger(self):
        """Bridge finalized POS tender snapshots into the authoritative Payment ledger."""
        if not self.payments or not frappe.db.exists("DocType", "Ledgix Payment"):
            return

        from ledgix_saas.services.payments import post_payment

        remaining_to_allocate = self.get_payable_total()
        for tender in self.payments:
            tendered = flt(tender.amount)
            if tendered <= 0 or remaining_to_allocate <= 0:
                continue

            method = self.get_payment_method_meta(tender.payment_method)
            payment_amount = min(tendered, remaining_to_allocate)
            post_payment(
                customer=self.customer,
                payment_method=tender.payment_method,
                amount=payment_amount,
                amount_tendered=tendered if method.method_type == "Cash" else payment_amount,
                reference_number=getattr(tender, "reference_no", None),
                pos_shift=self.pos_shift,
                allocations=[{
                    "reference_doctype": "Ledgix Sale",
                    "reference_name": self.name,
                    "allocated_amount": payment_amount,
                }],
            )
            remaining_to_allocate -= payment_amount

    def update_pos_shift_cash(self):
        if not self.pos_shift:
            return

        shift = frappe.get_doc("Ledgix POS Shift", self.pos_shift)
        if shift.docstatus != 0:
            return

        shift.calculate_shift_summary()
        shift.calculate_expected_cash()
        shift.calculate_variance()
        shift.save(ignore_permissions=True)

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
