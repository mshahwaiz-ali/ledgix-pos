# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, flt


class LedgixPOSShift(Document):

    def before_insert(self):
        self.set_opening_details()

    def validate(self):
        self.calculate_shift_summary()
        self.calculate_expected_cash()
        self.calculate_variance()

    def on_submit(self):
        if self.status != "Closed":
            frappe.throw("Close the POS shift before submitting it.")

        if not self.closing_time:
            frappe.throw("Closing time is missing. Close the POS shift before submitting it.")

        if not self.closed_by:
            self.closed_by = frappe.session.user

        self.calculate_shift_summary()
        self.calculate_expected_cash()
        self.calculate_variance()
        self.status = "Closed"

    def on_cancel(self):
        self.status = "Cancelled"

    # ============================================================
    # OPENING SHIFT
    # ============================================================

    def set_opening_details(self):

        if not self.opening_time:
            self.opening_time = now_datetime()

        if not self.opened_by:
            self.opened_by = frappe.session.user

        self.status = "Open"

    # ============================================================
    # SHIFT CLOSING
    # ============================================================

    def close_shift(self):

        self.closing_time = now_datetime()

        if not self.closed_by:
            self.closed_by = frappe.session.user

        self.status = "Closed"

    # ============================================================
    # SHIFT SUMMARY
    # ============================================================

    def calculate_shift_summary(self):

        if not self.name:
            self.cash_sales = 0
            self.non_cash_sales = 0
            self.total_sales = 0
            self.invoice_count = 0
            return

        sales = frappe.get_all(
            "Ledgix Sale",
            filters={"pos_shift": self.name, "docstatus": 1},
            fields=["name", "grand_total", "total_amount"],
            order_by="creation asc",
        )

        cash_sales = 0
        non_cash_sales = 0

        for sale in sales:
            sale_total = flt(sale.grand_total or sale.total_amount)
            cash_tendered = 0
            non_cash_paid = 0

            payments = frappe.get_all(
                "Ledgix Sale Payment",
                filters={
                    "parent": sale.name,
                    "parenttype": "Ledgix Sale",
                    "parentfield": "payments",
                },
                fields=["payment_method", "amount"],
                order_by="idx asc",
            )

            for payment in payments:
                if payment.payment_method == "Cash":
                    cash_tendered += flt(payment.amount)
                else:
                    non_cash_paid += flt(payment.amount)

            cash_required = max(sale_total - non_cash_paid, 0)
            cash_sales += min(cash_tendered, cash_required)
            non_cash_sales += min(non_cash_paid, sale_total)

        self.cash_sales = flt(cash_sales)
        self.non_cash_sales = flt(non_cash_sales)
        self.total_sales = flt(self.cash_sales) + flt(self.non_cash_sales)
        self.invoice_count = len(sales)

    # ============================================================
    # EXPECTED CASH
    # ============================================================

    def calculate_expected_cash(self):

        self.expected_cash = (
            flt(self.opening_cash)
            + flt(self.cash_sales)
        )

    # ============================================================
    # CASH VARIANCE
    # ============================================================

    def calculate_variance(self):

        self.cash_variance = (
            flt(self.actual_cash)
            - flt(self.expected_cash)
        )
