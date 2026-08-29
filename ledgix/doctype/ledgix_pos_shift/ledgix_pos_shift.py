# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


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
        self.invoice_count = len(sales)
        self.total_sales = flt(sum(flt(row.grand_total or row.total_amount) for row in sales), 2)

        if not frappe.db.exists("DocType", "Ledgix Payment"):
            self.cash_sales = 0
            self.non_cash_sales = 0
            return

        payments = frappe.db.sql(
            """
            SELECT
                p.amount,
                p.reversal_of,
                pm.method_type
            FROM `tabLedgix Payment` p
            LEFT JOIN `tabLedgix Payment Method` pm ON pm.name = p.payment_method
            WHERE p.docstatus = 1
              AND p.pos_shift = %s
            ORDER BY p.creation ASC
            """,
            (self.name,),
            as_dict=True,
        )

        cash_sales = 0.0
        non_cash_sales = 0.0
        for payment in payments:
            sign = -1 if payment.reversal_of else 1
            net_amount = sign * flt(payment.amount)
            if payment.method_type == "Cash":
                cash_sales += net_amount
            else:
                non_cash_sales += net_amount

        self.cash_sales = flt(cash_sales, 2)
        self.non_cash_sales = flt(non_cash_sales, 2)

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
